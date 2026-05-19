#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "requests[socks]"]
# ///
"""
AnySearch 搜索脚本
POST https://api.anysearch.com/v1/search
代理池支持 http/https/socks4/socks5，全量并发探测取第一个可用，全失败后直连兜底
"""

import sys
import json
import os
import urllib.request
import ssl
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
import threading

import requests

# ─── 配置 ────────────────────────────────────────────────────────────────────

SEARCH_API = "https://api.anysearch.com/v1/search"
PROXY_LIST_URL = os.environ.get(
    "ANYSEARCH_PROXY_LIST_URL",
    "https://cdn.jsdelivr.net/gh/parserpp/ip_ports/proxyinfo.json",
)
PROBE_TIMEOUT = 5    # 单个代理探测超时（秒）
REQUEST_TIMEOUT = 15

API_KEY = os.environ.get("ANYSEARCH_API_KEY", "")

# ─── 代理加载 ────────────────────────────────────────────────────────────────

def _parse_proxy_line(line: str) -> str | None:
    """支持格式：socks5://IP:PORT、http://IP:PORT、裸 IP:PORT（默认 http）"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    line = line.split("#")[0].strip()
    if not line:
        return None
    if "://" in line:
        return line
    return f"http://{line}"


def load_proxies() -> list[str]:
    """加载并按 response_time 升序排列代理，支持 JSON（proxyinfo.json）和纯文本两种格式"""
    env_proxies = os.environ.get("ANYSEARCH_PROXIES", "")
    if env_proxies:
        return [p.strip() for p in env_proxies.split(",") if p.strip()]

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(PROXY_LIST_URL, headers={"User-Agent": "Mozilla/5.0"})
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        with opener.open(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        # 尝试按 JSON 格式解析（proxyinfo.json 结构）
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                all_entries = []
                for entries in data.values():
                    if isinstance(entries, list):
                        all_entries.extend(entries)
                # 按 response_time 升序排列，最快的排前面
                all_entries.sort(key=lambda x: x.get("response_time", 9999))
                proxies = []
                for e in all_entries:
                    host = e.get("host", "")
                    port = e.get("port", "")
                    ptype = e.get("type", "http")
                    if host and port:
                        proxies.append(f"{ptype}://{host}:{port}")
                sys.stderr.write(f"[代理] 加载 {len(proxies)} 条（已按 response_time 排序）\n")
                return proxies
        except (json.JSONDecodeError, AttributeError):
            pass

        # 纯文本格式：每行一条
        proxies = [p for line in raw.splitlines() if (p := _parse_proxy_line(line))]
        sys.stderr.write(f"[代理] 加载 {len(proxies)} 条（文本格式）\n")
        return proxies

    except Exception as e:
        sys.stderr.write(f"[代理列表加载失败] {e}\n")
        return []


# ─── 代理探测：全量并发，找到第一个可用立即返回 ──────────────────────────────

def _probe_proxy(proxy: str, found: threading.Event) -> str | None:
    """向 API 发真实 POST，能拿到有效 JSON 且 found 未触发则返回代理地址"""
    if found.is_set():
        return None
    try:
        resp = requests.post(
            SEARCH_API,
            json={"query": "test", "max_results": 1},
            headers={"Content-Type": "application/json", "User-Agent": "AnySearch-Skill/1.0"},
            proxies={"http": proxy, "https": proxy},
            timeout=PROBE_TIMEOUT,
            verify=False,
        )
        resp.json()
        return proxy
    except Exception:
        return None


def find_first_live_proxy(all_proxies: list[str]) -> str | None:
    """全量并发探测，第一个成功的代理立即返回，其余取消等待"""
    if not all_proxies:
        return None

    sys.stderr.write(f"[探测] 并发检测全部 {len(all_proxies)} 个代理...\n")
    found = threading.Event()
    winner: list[str] = []

    with ThreadPoolExecutor(max_workers=min(len(all_proxies), 50)) as pool:
        futures: dict[Future, str] = {
            pool.submit(_probe_proxy, p, found): p for p in all_proxies
        }
        for future in as_completed(futures):
            result = future.result()
            if result and not found.is_set():
                found.set()
                winner.append(result)
                break  # 拿到第一个，不再等其他

    if winner:
        sys.stderr.write(f"[探测] 找到可用代理: {winner[0]}\n")
        return winner[0]

    sys.stderr.write(f"[探测] 全部 {len(all_proxies)} 个均不可用\n")
    return None


# ─── HTTP 请求 ───────────────────────────────────────────────────────────────

def _make_headers() -> dict:
    h = {"Content-Type": "application/json", "User-Agent": "AnySearch-Skill/1.0"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


def do_search_request(query: str, max_results: int = 10, proxy: str | None = None) -> dict:
    resp = requests.post(
        SEARCH_API,
        json={"query": query, "max_results": max_results},
        headers=_make_headers(),
        proxies={"http": proxy, "https": proxy} if proxy else None,
        timeout=REQUEST_TIMEOUT,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()


# ─── 402 配额耗尽：自动获取注册账户凭据 ──────────────────────────────────────

def try_extract_auto_credentials(body: str) -> None:
    global API_KEY
    try:
        data = json.loads(body)
        ak = (
            data.get("api_key")
            or data.get("credentials", {}).get("api_key")
            or data.get("data", {}).get("api_key")
        )
        if ak:
            API_KEY = ak
            sys.stderr.write("[自动账户] 获取到 api_key，将用于后续请求\n")
    except Exception:
        pass


# ─── 搜索结果规范化 ──────────────────────────────────────────────────────────

def normalize_results(raw: dict) -> list[dict]:
    """响应结构: {"code":0,"data":{"results":[{"title","url","description","content"}]}}"""
    data = raw.get("data") or raw
    items = (data.get("results") or data.get("items") or []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or ""
        url = item.get("url") or item.get("link") or ""
        snippet = item.get("description") or str(item.get("content") or item.get("snippet") or "")[:500]
        if title or url:
            results.append({"title": str(title).strip(), "url": str(url).strip(), "snippet": str(snippet).strip()})
    return results


# ─── 主搜索逻辑 ──────────────────────────────────────────────────────────────

def search(query: str, max_results: int = 10) -> dict:
    all_proxies = load_proxies()
    proxy = find_first_live_proxy(all_proxies)

    def _attempt(p: str | None) -> dict | None:
        label = p or "直连"
        try:
            sys.stderr.write(f"[请求] {label}\n")
            raw = do_search_request(query, max_results=max_results, proxy=p)
            return {"query": query, "results": normalize_results(raw), "error": None, "via": label}
        except requests.HTTPError as e:
            body = e.response.text if e.response else ""
            sys.stderr.write(f"[HTTP {e.response.status_code if e.response else '?'}] {label}: {body[:200]}\n")
            if e.response and e.response.status_code == 402:
                try_extract_auto_credentials(body)
            return None
        except Exception as e:
            sys.stderr.write(f"[失败] {label}: {e}\n")
            return None

    # 优先用探测到的代理，失败则直连兜底
    if proxy:
        result = _attempt(proxy)
        if result:
            return result

    result = _attempt(None)
    if result:
        return result

    return {"query": query, "results": [], "error": "所有请求均失败，见 stderr", "via": None}


# ─── 入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)
    if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
        sys.stderr = open(sys.stderr.fileno(), mode="w", encoding="utf-8", buffering=1, closefd=False)

    if len(sys.argv) < 2:
        print(json.dumps({"error": "用法: search.py <搜索关键词> [max_results]", "results": []}, ensure_ascii=False))
        sys.exit(1)

    query_parts = sys.argv[1:]
    max_r = 10
    if query_parts[-1].isdigit():
        max_r = int(query_parts[-1])
        query_parts = query_parts[:-1]

    query = " ".join(query_parts)
    result = search(query, max_results=max_r)
    print(json.dumps(result, ensure_ascii=False, indent=2))
