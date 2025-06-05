from utils.node_finder import get_working_public_nodes
from utils.block_watcher import watch_new_contracts
from utils.source_checker import is_code_verified

def main():
    # 1) Find a handful of fast, non‐rate‐limited RPC endpoints
    print("Finding node endpoints to use...")
    rpc_endpoints = get_working_public_nodes(burst=50, top_n=3, timeout=1)
    if not rpc_endpoints:
        print("No reliable RPC endpoints available.")
        return

    print(f"Found {len(rpc_endpoints)} (https) node endpoints to use")
    # 2) Start watching from the latest block
    for addr, balance in watch_new_contracts(rpc_endpoints):
        verified = is_code_verified(addr, 1)  # 1 = mainnet
        status = "VERIFIED" if verified else "UNVERIFIED"
        print(f"[NEW] {status} {addr} | {balance/1e18:.2f} ETH")

if __name__ == "__main__":
    main()
