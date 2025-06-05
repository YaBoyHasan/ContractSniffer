# main.py

import sys
from datetime import datetime
from utils.node_finder import get_working_public_nodes
from utils.block_watcher import watch_new_contracts
from utils.source_checker import is_code_verified

# Import the two Slither‐related helpers:
#   run_slither(...) → runs Slither and dumps JSON
#   find_true_arbitrary_send_vulns(...) → returns only unguarded arbitrary-send-eth functions
from utils.slither_analyzer import run_slither, find_true_arbitrary_send_vulns

# ANSI color codes
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
RESET  = "\033[0m"

def main():
    try:
        print(f"{CYAN}🔍 Finding node endpoints to use...{RESET}")
        rpc_endpoints = get_working_public_nodes(burst=50, top_n=5, timeout=1)
        if not rpc_endpoints:
            print(f"{YELLOW}⚠️  No reliable RPC endpoints available.{RESET}")
            return

        print(f"{GREEN}✅ Found {len(rpc_endpoints)} HTTPS node endpoints to use{RESET}\n")
        print(f"{CYAN}⏳ Listening for new contracts… (Ctrl+C to exit){RESET}\n")

        for addr, balance in watch_new_contracts(rpc_endpoints):
            timestamp = datetime.utcnow().strftime("%H:%M:%S UTC")

            # 1) Only proceed if the contract's source is verified on Etherscan
            if not is_code_verified(addr, 1):  # 1 = mainnet
                print(f"{RESET}[{timestamp}] UNVERIFIED {addr} | {balance/1e18:,.2f} ETH{RESET}")
                continue

            print(f"{GREEN}[{timestamp}] ✔ VERIFIED {addr} | {balance/1e18:,.2f} ETH{RESET}")

            # 2) Run Slither on this address (produces slither-reports/<addr>.json)
            print(f"{CYAN}   🔎 Running Slither on mainnet:{addr}{RESET}")
            succeeded = run_slither("mainnet", addr)
            if not succeeded:
                print(f"{RED}   ❌ Slither failed for {addr}{RESET}")
                continue

            # 3) Now fetch only the “true” arbitrary-send-eth drains:
            vulns = find_true_arbitrary_send_vulns(addr)
            if not vulns:
                # None survived our “public & unguarded” filters → no real drain
                print(f"{GREEN}   ✅ No unguarded ETH-drain functions found{RESET}\n")
                continue

            # 4) Print a PROFIT ALERT for each drainable function
            for fn in vulns:
                print(f"{RED}💥 PROFIT ALERT: {addr} is drainable via {fn}(){RESET}")

            # blank line before next contract
            print()

    except KeyboardInterrupt:
        print(f"\n{YELLOW}✋ Stopping watcher. Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
