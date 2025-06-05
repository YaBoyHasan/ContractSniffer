# utils/slither_analyzer.py

import subprocess
import json
import os
import re

# Make sure these two functions exist in utils/false_positive_filter.py:
#    is_nonpublic(source_dir, function_name) → bool
#    has_modifier_guard(source_dir, function_name) → bool
#    has_manual_owner_check(source_dir, function_name) → bool

from utils.false_positive_filter import (
    is_nonpublic,
    has_modifier_guard,
    has_manual_owner_check,
)


def run_slither(chain_slug: str, address: str) -> bool:
    """
    Invokes Slither on chain_slug:address, but only detects the high-value patterns.
    Returns True if Slither completed (even with warnings), False on subprocess error.
    """
    print(f"[🔎] Running Slither on {chain_slug}:{address}")

    cmd = [
        "slither",
        f"{chain_slug}:{address}",
        "--detect", "arbitrary-send-eth,reentrancy-eth,incorrect-return",
        "--exclude-detectors", "solidity-safemath,arithmetic",
        "--exclude-paths", r".*SafeMath\.sol|.*openzeppelin/.*|.*libraries/.*",
        "--solc-args", "--via-ir --optimize --allow-paths C:/Users/haych/Desktop/ContractSniffer",
        "--json", f"slither-reports/{address}.json",
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except Exception as e:
        print(f"[❌] Slither subprocess error for {address}: {e}")
        return False

    if proc.stderr:
        print(f"[⚠️] Slither reported issues or warnings for {address}")
    else:
        print(f"[✅] Slither ran clean (no issues) for {address}")

    return True


def parse_slither_report(address: str) -> list[tuple[str,str]]:
    """
    Original parser: collects all (check_name, function_name) where
    impact == high and confidence == high|medium.
    """
    path = f"slither-reports/{address}.json"
    if not os.path.isfile(path):
        return []

    data = json.load(open(path, "r"))
    findings: list[tuple[str,str]] = []
    for det in data.get("results", {}).get("detectors", []):
        check_name = det.get("check", "").lower()
        impact     = det.get("impact", "").lower()
        confidence = det.get("confidence", "").lower()

        if impact == "high" and confidence in ("high", "medium"):
            function = None
            for el in det.get("elements", []):
                if el.get("type") == "function":
                    function = el.get("name")
                    break
            findings.append((check_name, function))
    return findings


def find_true_arbitrary_send_vulns(address: str) -> list[str]:
    """
    1) Loads Slither JSON from 'slither-reports/<address>.json'
    2) Keeps only (check_name, fn) where check_name == "arbitrary-send-eth"
    3) Applies three filters:
         a) is_nonpublic()      → skip if fn is private/internal
         b) has_modifier_guard()→ skip if fn has onlyOwner/onlyAdmin
         c) has_manual_owner_check() → skip if fn has require(msg.sender == owner)
    Returns a list of function names that survived all filters (i.e. truly
    public arbitrary-send-eth drains).
    """

    path = f"slither-reports/{address}.json"
    if not os.path.isfile(path):
        return []

    # Step 1: grab all high-impact, medium/high-confidence findings
    raw_findings = parse_slither_report(address)

    # Build the source directory path where the flattened .sol files live:
    source_dir = f"crtyic-export/etherscan-contracts/{address}"

    true_vulns: list[str] = []
    for check_name, fn in raw_findings:
        # Only care about arbitrary-send-eth
        if check_name != "arbitrary-send-eth":
            continue

        # If Slither didn’t give us a function name, skip
        if not fn:
            continue

        # 2a) skip private/internal
        if is_nonpublic(source_dir, fn):
            continue

        # 2b) skip if has an onlyOwner or onlyAdmin modifier
        if has_modifier_guard(source_dir, fn):
            continue

        # 2c) skip if there’s an in‐body `require(msg.sender == owner)`
        if has_manual_owner_check(source_dir, fn):
            continue

        # At this point, fn is truly public and unguarded.  Bingo.
        true_vulns.append(fn)

    return true_vulns
