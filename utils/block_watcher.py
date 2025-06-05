# utils/block_watcher.py

import itertools
import time
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed
from web3 import Web3, HTTPProvider

def _make_round_robin_w3_list(rpc_entries, timeout=10):
    """
    Accepts a list of either:
      - "https://..." strings
      - or ("Name", "https://...") tuples

    Returns a cycle() iterator of Web3 instances, one per URL.
    """
    w3_list = []
    for entry in rpc_entries:
        # If it’s a tuple (name, url), grab the url
        if isinstance(entry, tuple) and len(entry) == 2:
            url = entry[1]
        else:
            url = entry

        # Create a Web3 over HTTPProvider(url)
        w3 = Web3(HTTPProvider(url, request_kwargs={"timeout": timeout}))
        w3_list.append(w3)

    return itertools.cycle(w3_list)


def watch_new_contracts(rpc_entries, from_block=None, poll_interval=2, max_workers=None):
    """
    Generator that yields (contract_address, balance_wei) for any newly‐seen contract
    whose balance > 0.1 ETH.

    Parameters:
      rpc_entries   – list of either URL‐strings or (name, url) tuples
      from_block    – if None, starts from latest block at call time; else start from that block number
      poll_interval – seconds to wait between polling for new blocks (uses HTTP calls)
      max_workers   – number of threads for per‐block parallel work. Defaults to len(rpc_entries)*2.

    Internally:
      • Rotates through all provided RPC URLs in round‐robin fashion, to spread the JSON‐RPC load.
      • Uses get_block(..., full_transactions=False) to only fetch tx‐hashes.
      • Spawns a small ThreadPoolExecutor to get_receipt/additional calls in parallel.
      • Keeps a seen_contracts set (thread‐safe) so each contract is reported only once ever.
    """
    if not rpc_entries:
        raise ValueError("`rpc_entries` must be a non‐empty list of URLs or (name,url) tuples.")

    # Build a round‐robin iterator of Web3 instances
    rr_w3 = _make_round_robin_w3_list(rpc_entries)

    # Default worker count: 2 threads per RPC endpoint
    if max_workers is None:
        max_workers = len(rpc_entries) * 2

    seen_contracts = set()

    # Determine starting block number
    w3_first = next(rr_w3)
    try:
        latest = w3_first.eth.block_number
    except Exception as e:
        raise RuntimeError(f"Unable to fetch latest block from any RPC: {e}")

    current = from_block if (from_block is not None) else latest

    # Main polling loop
    while True:
        w3_poll = next(rr_w3)
        try:
            latest = w3_poll.eth.block_number
        except Exception:
            # If one endpoint fails, wait and try again
            time.sleep(poll_interval)
            continue

        if latest <= current:
            # No new blocks yet
            time.sleep(poll_interval)
            continue

        # Process each new block in range(current+1 .. latest)
        for block_number in range(current + 1, latest + 1):
            w3_block = next(rr_w3)
            try:
                block = w3_block.eth.get_block(block_number, full_transactions=False)
            except Exception:
                # Skip this block if the call fails
                continue

            tx_hashes = block.transactions  # only a list of tx‐hashes
            if not tx_hashes:
                continue

            # Parallelize per‐transaction work: receipt → code → balance
            with ThreadPoolExecutor(max_workers=max_workers) as exe:
                futures = [
                    exe.submit(_process_tx, tx_hash, rr_w3, seen_contracts)
                    for tx_hash in tx_hashes
                ]

                for fut in as_completed(futures):
                    result = fut.result()
                    if result is not None:
                        # result is (addr_checksum, balance_wei)
                        yield result

        # Update the “current” pointer so we don’t re‐scan these blocks
        current = latest


def _process_tx(tx_hash, rr_w3, seen_contracts):
    """
    For a single tx_hash:
      • get_transaction_receipt
      • determine contractAddress or receipt.to
      • if not seen, get_code → get_balance
      • if code != b"" and balance > 0.1 ETH, add to seen_contracts and return (address, balance)
      • otherwise return None
    """
    w3 = next(rr_w3)
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception:
        return None

    # If it’s a contract creation, use receipt.contractAddress; else use receipt.to
    addr = None
    if receipt.contractAddress:
        addr = Web3.to_checksum_address(receipt.contractAddress)
    elif receipt.to:
        addr = Web3.to_checksum_address(receipt.to)

    if not addr:
        return None

    # Skip if already seen
    with _seen_lock():
        if addr in seen_contracts:
            return None
        # Temporarily mark as seen so parallel threads don’t re-add
        seen_contracts.add(addr)

    # Fetch code; if empty, it’s not a contract
    w3_code = next(rr_w3)
    try:
        code = w3_code.eth.get_code(addr)
    except Exception:
        # On error, un‐mark and bail
        with _seen_lock():
            seen_contracts.discard(addr)
        return None

    if code == b"":
        with _seen_lock():
            seen_contracts.discard(addr)
        return None

    # Fetch balance
    w3_bal = next(rr_w3)
    try:
        balance = w3_bal.eth.get_balance(addr)
    except Exception:
        with _seen_lock():
            seen_contracts.discard(addr)
        return None

    # Only report if > 0.1 ETH
    if balance > int(0.1 * 1e18):
        return (addr, balance)

    # If balance too low, remove so that a later deposit can re-trigger
    with _seen_lock():
        seen_contracts.discard(addr)
    return None


# Module‐level lock to protect seen_contracts
_seen_lock_obj = Lock()
def _seen_lock():
    return _seen_lock_obj
