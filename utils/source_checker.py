import requests
import os
import time

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

def is_code_verified(addr, chain_id=1):
    try:
        res = requests.get(ETHERSCAN_URL, params={
            "chainid": chain_id,
            "module": "contract",
            "action": "getsourcecode",
            "address": addr,
            "apikey": ETHERSCAN_API_KEY
        })

        result = res.json().get("result", [{}])[0]
        source = result.get("SourceCode", "")
        abi = result.get("ABI", "")

        if source.strip() and "not verified" not in abi.lower():
            return True
        else:
            return False
    except Exception as e:
        print(f"[!] Etherscan error on {addr}: {e}")
        return False