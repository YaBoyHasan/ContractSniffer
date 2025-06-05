import subprocess
import json
import os

def run_slither(chain_slug, address):
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

def parse_slither_report(address):
    path = f"slither-reports/{address}.json"
    if not os.path.isfile(path):
        return []

    data = json.load(open(path))
    findings = []
    for det in data.get("results", {}).get("detectors", []):
        check_name = det.get("check", "").lower()
        impact     = det.get("impact", "").lower()
        confidence = det.get("confidence", "").lower()

        if impact == "high" and confidence in ("high", "medium"):
            # find function name
            function = None
            for el in det.get("elements", []):
                if el.get("type") == "function":
                    function = el.get("name")
                    break
            findings.append((check_name, function))
    return findings  # list of tuples
