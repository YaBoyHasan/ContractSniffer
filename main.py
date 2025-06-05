# main.py

import sys
import time
from datetime import datetime
from utils.node_finder import get_working_public_nodes
from utils.block_watcher import watch_new_contracts
from utils.source_checker import is_code_verified

# ANSI color codes
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
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

        # **Wrap the entire watch loop in try/except so Ctrl+C is caught here**
        for addr, balance in watch_new_contracts(rpc_endpoints):
            # If user pressed Ctrl+C, a KeyboardInterrupt will jump to the except below
            timestamp = datetime.utcnow().strftime("%H:%M:%S UTC")
            if is_code_verified(addr, 1):  # 1 = mainnet                
                print(
                    f"{GREEN}[{timestamp}] ✔  VERIFIED {addr} | {balance/1e18:,.2f} ETH{RESET}"
                )
            else:
                print(
                    f"{RESET}[{timestamp}] UNVERIFIED {addr} | {balance/1e18:,.2f} ETH{RESET}"
                )

    except KeyboardInterrupt:
        # This catches Ctrl+C anywhere inside the for‐loop or inside get_working_public_nodes
        print(f"\n{YELLOW}✋ Stopping watcher. Goodbye!{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
