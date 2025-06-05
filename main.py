# main.py

import sys
from datetime import datetime
from utils.node_finder import get_working_public_nodes
from utils.block_watcher import watch_new_contracts
from utils.source_checker import is_code_verified
from utils.slither_analyzer import run_slither, parse_slither_report

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

            if not is_code_verified(addr, 1):  # 1 = mainnet
                print(f"{RESET}[{timestamp}] UNVERIFIED {addr} | {balance/1e18:,.2f} ETH{RESET}")
                continue

            print(f"{GREEN}[{timestamp}] ✔ VERIFIED {addr} | {balance/1e18:,.2f} ETH{RESET}")
            # Run Slither on the verified contract
            report_path = run_slither("mainnet",addr)
            if not report_path:
                print(f"{RED}   ❌ Slither failed for {addr}{RESET}")
                continue

            issues = parse_slither_report(addr)
            if not issues:
                print(f"{GREEN}   ✅ No high‐impact issues found{RESET}")
            else:
                print(f"{RED}   🚨 High‐impact issues: {issues}{RESET}")

    except KeyboardInterrupt:
        print(f"\n{YELLOW}✋ Stopping watcher. Goodbye!{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
