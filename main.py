# main.py

import sys
from datetime import datetime
from utils.node_finder import get_working_public_nodes
from utils.block_watcher import watch_new_contracts
from utils.source_checker import is_code_verified
from utils.slither_analyzer import run_slither, parse_slither_report
from utils.false_positive_filter import has_modifier_guard, is_nonpublic

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

            # 2) Run Slither against the newly-verified address
            print(f"{CYAN}   🔎 Running Slither on mainnet:{addr}{RESET}")
            succeeded = run_slither("mainnet", addr)
            if not succeeded:
                print(f"{RED}   ❌ Slither failed for {addr}{RESET}")
                continue

            # 3) Parse Slither’s JSON to get high-impact, medium/high-confidence findings
            findings = parse_slither_report(addr)
            if not findings:
                print(f"{GREEN}   ✅ No high-impact issues found by Slither{RESET}\n")
                continue

            # 4) For each Slither finding, check visibility and guards
            #    Adjust this path to wherever Slither saved the flattened source
            source_dir = f"crtyic-export/etherscan-contracts/{addr}"

            for check_name, function_name in findings:
                if not function_name:
                    print(f"   🔶 Skipped: Slither flagged {check_name} but no function name found.")
                    continue

                # 4.1) If function is private or internal, skip
                if is_nonpublic(source_dir, function_name):
                    print(f"   🟢 Skipped {function_name} ({check_name}) — it’s private/internal, not externally callable.")
                    continue

                # 4.2) If it has onlyOwner/onlyAdmin guard, skip
                if has_modifier_guard(source_dir, function_name):
                    print(f"   🟡 Skipped {function_name} ({check_name}) — found onlyOwner/onlyAdmin guard.")
                    continue

                # 4.3) Otherwise, it’s a real exposed high-impact call
                print(f"{RED}   🚨 Slither flagged [{check_name}] in {function_name} — no guard, visible to public!{RESET}")

            # blank line before next contract
            print()

    except KeyboardInterrupt:
        print(f"\n{YELLOW}✋ Stopping watcher. Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
