"""Tầng HTTP dùng chung cho mọi call GitHub.

Ba thứ tiết kiệm được so với gọi `requests.get` trực tiếp:

1. Session tái dùng — giữ connection pool, không bắt tay TCP+TLS lại mỗi request.
   Đây là phần lớn thời gian của một chuỗi ~18 request nhỏ.
2. ETag / If-None-Match — GitHub trả 304 khi nội dung không đổi, và **304 không bị
   trừ vào rate limit**. Repo không có commit mới thì crawl lại gần như miễn phí.
3. TTL cache trên đĩa — trong khoảng TTL thì không chạm mạng luôn.

An toàn khi gọi từ nhiều thread: Session của requests dùng được, ghi cache có lock.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API = "https://api.github.com"
TIMEOUT = 15
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "http_cache"
DEFAULT_TTL = int(os.getenv("GITHUB_CACHE_TTL", "600"))   # giây; 0 = luôn revalidate

_session: requests.Session | None = None
_session_lock = threading.Lock()
_cache_lock = threading.Lock()

# thống kê 1 lần chạy — để biết tiết kiệm được bao nhiêu request
STATS = {"net": 0, "not_modified": 0, "ttl_hit": 0, "error": 0}
RATE = {"limit": None, "remaining": None, "reset": None, "resource": ""}


def headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.headers.update(headers())
                # đủ chỗ cho các call song song trong 1 thành viên
                adapter = requests.adapters.HTTPAdapter(pool_connections=16,
                                                        pool_maxsize=32, max_retries=0)
                s.mount("https://", adapter)
                _session = s
    return _session


def reset_session():
    """Dùng khi đổi token giữa chừng."""
    global _session
    with _session_lock:
        if _session is not None:
            _session.close()
        _session = None


# ---------- cache trên đĩa ----------

def _key(url: str, params: dict | None) -> str:
    raw = url + "?" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_file(k: str) -> Path:
    return CACHE_DIR / f"{k}.json"


def _read_cache(k: str) -> dict | None:
    f = _cache_file(k)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(k: str, entry: dict):
    with _cache_lock:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            _cache_file(k).write_text(json.dumps(entry, ensure_ascii=False),
                                      encoding="utf-8")
        except OSError:
            pass


def _track_rate(resp: requests.Response):
    rem = resp.headers.get("X-RateLimit-Remaining")
    if rem is None:
        return
    RATE.update({
        "limit": resp.headers.get("X-RateLimit-Limit"),
        "remaining": rem,
        "reset": resp.headers.get("X-RateLimit-Reset"),
        "resource": resp.headers.get("X-RateLimit-Resource", ""),
    })


# ---------- API chính ----------

def get(path: str, params: dict | None = None, ttl: int | None = None) -> dict:
    """GET GitHub, trả {ok, status, data, source, error}.

    path: '/repos/o/r' (nối vào API) hoặc URL đầy đủ.
    source: 'ttl' (không chạm mạng) | '304' (không trừ quota) | 'net' | 'error'
    """
    url = path if path.startswith("http") else f"{API}{path}"
    ttl = DEFAULT_TTL if ttl is None else ttl
    k = _key(url, params)
    cached = _read_cache(k)

    if cached and ttl > 0 and (time.time() - cached.get("fetched_at", 0)) < ttl:
        STATS["ttl_hit"] += 1
        return {"ok": True, "status": cached.get("status", 200),
                "data": cached.get("data"), "source": "ttl", "error": ""}

    req_headers = {}
    if cached and cached.get("etag"):
        req_headers["If-None-Match"] = cached["etag"]     # 304 không bị trừ quota
    elif cached and cached.get("last_modified"):
        req_headers["If-Modified-Since"] = cached["last_modified"]

    try:
        resp = session().get(url, params=params, headers=req_headers or None,
                             timeout=TIMEOUT)
    except requests.RequestException as e:
        STATS["error"] += 1
        if cached:      # mạng lỗi mà có bản cũ thì dùng tạm còn hơn trả rỗng
            return {"ok": True, "status": cached.get("status", 200),
                    "data": cached.get("data"), "source": "stale", "error": str(e)}
        return {"ok": False, "status": 0, "data": None, "source": "error", "error": str(e)}

    _track_rate(resp)

    if resp.status_code == 304 and cached:
        STATS["not_modified"] += 1
        cached["fetched_at"] = time.time()
        _write_cache(k, cached)
        return {"ok": True, "status": 200, "data": cached.get("data"),
                "source": "304", "error": ""}

    STATS["net"] += 1
    if not resp.ok:
        return {"ok": False, "status": resp.status_code, "data": None,
                "source": "net", "error": _explain(resp)}

    try:
        data = resp.json()
    except ValueError:
        return {"ok": False, "status": resp.status_code, "data": None,
                "source": "net", "error": "Response không phải JSON"}

    _write_cache(k, {"url": url, "status": resp.status_code, "data": data,
                     "etag": resp.headers.get("ETag", ""),
                     "last_modified": resp.headers.get("Last-Modified", ""),
                     "fetched_at": time.time()})
    return {"ok": True, "status": resp.status_code, "data": data,
            "source": "net", "error": ""}


def _explain(resp: requests.Response) -> str:
    if resp.status_code == 404:
        return "404 không tìm thấy"
    if resp.status_code in (403, 429):
        if resp.headers.get("X-RateLimit-Remaining") == "0":
            reset = resp.headers.get("X-RateLimit-Reset")
            when = ""
            if reset:
                left = max(0, int(reset) - int(time.time()))
                when = f", còn {left // 60} phút {left % 60}s nữa mới reset"
            return (f"GitHub API hết quota ({resp.headers.get('X-RateLimit-Resource','core')})"
                    f"{when} — thêm GITHUB_TOKEN vào .env nếu chưa có")
        return "403 bị chặn (repo private hoặc thiếu quyền)"
    return f"HTTP {resp.status_code}"


def get_json(path: str, params: dict | None = None, ttl: int | None = None):
    """Chỉ cần data, lỗi trả None."""
    r = get(path, params, ttl)
    return r["data"] if r["ok"] else None


def stats_line() -> str:
    s = STATS
    saved = s["not_modified"] + s["ttl_hit"]
    line = (f"GitHub: {s['net']} request thật, {s['not_modified']} lần 304 "
            f"(không trừ quota), {s['ttl_hit']} lần dùng cache, tiết kiệm {saved}")
    if RATE["remaining"] is not None:
        line += f" | quota còn {RATE['remaining']}/{RATE['limit']}"
    return line
