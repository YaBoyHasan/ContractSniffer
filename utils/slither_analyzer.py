import subprocess
import json
import os

def run_slither(chain_slug, address):
    print(f"[🔎] Running Slither on {chain_slug}:{address}")

    cmd = [
        "slither",
        f"{chain_slug}:{address}",
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

    # On Windows, Slither often returns a large non-zero code even when it compiles/finds issues
    # So we treat *any* return code as “analysis succeeded,” and only inspect stderr if needed
    if proc.stderr:
        print(f"[⚠️] Slither reported issues or warnings for {address}")
    else:
        print(f"[✅] Slither ran clean (no issues) for {address}")

    return True

def parse_slither_report(address):
    path = f"slither-reports/{address}.json"
    if not os.path.isfile(path):
        return False

    data = json.load(open(path))
    for det in data.get("results", {}).get("detectors", []):
        check_name = det.get("check", "").lower()
        impact     = det.get("impact", "").lower()
        confidence = det.get("confidence", "").lower()

        # Find the first element whose "type" == "function"
        function = None
        for el in det.get("elements", []):
            if el.get("type") == "function":
                # this gives you something like "collectFees(address[])"
                function = el.get("name")
                break

        # Only pick truly high‐impact, medium/high‐confidence findings
        if impact == "high" and (confidence == "high" or confidence == "medium"):
            print(f"---> [F:{function}] [V:{check_name}] [I:{impact}] [C:{confidence}]")
            return True

    return False

