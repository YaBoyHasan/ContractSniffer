# utils/node_finder.py

import requests
import time
import json
from threading import Thread, Lock
from queue import Queue, Empty
from bs4 import BeautifulSoup
from web3 import Web3

ETH_NODES_URL = "https://ethereumnodes.com/"

# 1. Scrape all HTTPS/HTTP endpoints from ethereumnodes.com
def _get_https_nodes():
    resp = requests.get(ETH_NODES_URL, timeout=5)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    nodes = []
    for li in soup.select("ul > li"):
        name_tag = li.select_one(".top h2")
        ep_tag   = li.select_one("input.endpoint")
        if not (name_tag and ep_tag):
            continue

        name = name_tag.get_text(strip=True)
        url  = ep_tag["value"].strip()
        if url.startswith("https://") or url.startswith("http://"):
            nodes.append((name, url))
    return nodes

# 2. Single-request latency check
def _measure_latency(name, url, timeout=5):
    """
    Returns (name, url, latency_ms) or (name, url, None) on failure.
    """
    try:
        w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": timeout}))
        start = time.monotonic()
        _ = w3.eth.block_number
        elapsed = (time.monotonic() - start) * 1000
        return (name, url, int(elapsed))
    except Exception:
        return (name, url, None)

# 3. Burst / rate-limit probing
def _probe_rate_limit(name, url, burst=50, timeout=5, rpc_method="eth_blockNumber"):
    """
    Sends up to `burst` rapid JSON-RPC calls (method=rpc_method, no params),
    stops on HTTP error or JSON-RPC error, or after `burst` successes.
    Returns (name, url, latency_ms, success_count, total_time_sec).
    """
    # First, measure latency once
    _, _, latency_ms = _measure_latency(name, url, timeout)

    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "method": rpc_method,
        "params": [],
        "id": 1
    }

    session = requests.Session()
    session.headers.update(headers)
    start = time.monotonic()
    success_count = 0

    for i in range(1, burst + 1):
        payload["id"] = i
        try:
            resp = session.post(url, data=json.dumps(payload), timeout=timeout)
            if resp.status_code != 200:
                break
            js = resp.json()
            if "error" in js:
                break
            success_count += 1
        except Exception:
            break

    total = time.monotonic() - start
    return (name, url, latency_ms, success_count, total)

def _worker_latency(queue, results, lock):
    while True:
        try:
            name, url = queue.get_nowait()
        except Empty:
            return
        res = _measure_latency(name, url)
        with lock:
            results.append(res)
        queue.task_done()

def _worker_rate(queue, results, lock, burst, timeout):
    while True:
        try:
            name, url = queue.get_nowait()
        except Empty:
            return
        res = _probe_rate_limit(name, url, burst, timeout)
        with lock:
            results.append(res)
        queue.task_done()

def get_working_public_nodes(burst: int = 50,
                             top_n: int = 5,
                             timeout: int = 5) -> list[tuple[str, str]]:
    """
    Finds free HTTPS Ethereum RPC endpoints, ranks them by single-call latency,
    then probes the top `top_n` for rate-limit capacity using a `burst` of rapid calls.

    Returns a list of (name, url) for all endpoints that passed the full burst (i.e., success_count == burst).
    """
    # 1) scrape all HTTPS nodes
    all_nodes = _get_https_nodes()
    if not all_nodes:
        raise RuntimeError("No HTTPS nodes found on ethereumnodes.com")

    # 2) measure latency for each node (multithreaded)
    latency_results = []
    lat_lock = Lock()
    latency_queue = Queue()
    for item in all_nodes:
        latency_queue.put(item)

    threads = []
    for _ in range(min(10, len(all_nodes))):
        t = Thread(target=_worker_latency, args=(latency_queue, latency_results, lat_lock))
        t.daemon = True
        t.start()
        threads.append(t)
    latency_queue.join()

    # filter out nodes that failed latency
    responsive = [(n, u, ms) for n, u, ms in latency_results if ms is not None]
    if not responsive:
        raise RuntimeError("No responsive nodes found.")

    # sort by fastest → slowest
    responsive.sort(key=lambda x: x[2])
    # pick top N (by default, 5)
    top_nodes = [(n, u) for n, u, _ in responsive][:top_n]

    # 3) probe rate-limit on top_nodes
    rate_queue = Queue()
    for item in top_nodes:
        rate_queue.put(item)

    rate_results = []
    rate_lock = Lock()
    threads = []
    for _ in range(len(top_nodes)):
        t = Thread(
            target=_worker_rate,
            args=(rate_queue, rate_results, rate_lock, burst, timeout)
        )
        t.daemon = True
        t.start()
        threads.append(t)
    rate_queue.join()

    # 4) collect those that passed the full burst (success_count == burst)
    working = []
    for name, url, latency_ms, succ, total_time in rate_results:
        if succ == burst:
            working.append((name, url))

    return working
