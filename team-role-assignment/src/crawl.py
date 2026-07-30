"""Thu bằng chứng thô từ GitHub cho mỗi (student, lab) và cho mỗi lab.

Không có AI ở file này — mọi con số ra từ REST API. Kết quả ghi .cache/ để
lần chạy sau không tốn request.

Chi phí: 1 request commit cho mỗi (student, lab) + 1 request cho mỗi file
markdown. README của repo lab dùng chung nên cache theo repo trong 1 lần chạy.
"""
import base64
import json
import re
from pathlib import Path

from .gh_http import get_json as _get_json

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "seed" / ".cache"
MAX_FILE_BYTES = 40_000
MAX_COMMITS = 100

_repo_cache: dict[str, dict] = {}      # cache trong 1 lần chạy, tránh gọi lại


# ---------- parse URL ----------

def parse_repo_url(url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/?#]|$)", url.strip())
    return (m.group(1), m.group(2)) if m else None


def parse_blob_url(url: str) -> tuple[str, str, str, str] | None:
    """https://github.com/o/r/blob/main/docs/a.md -> (o, r, 'main', 'docs/a.md')."""
    m = re.search(r"github\.com/([\w.-]+)/([\w.-]+)/blob/([^/]+)/(.+?)(?:[?#]|$)", url.strip())
    return (m.group(1), m.group(2), m.group(3), m.group(4)) if m else None


# ---------- fetch nguyên liệu ----------

def fetch_file(owner: str, repo: str, path: str, ref: str = "") -> str:
    params = {"ref": ref} if ref else None
    data = _get_json(f"/repos/{owner}/{repo}/contents/{path}", params)
    if isinstance(data, dict) and data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"])[:MAX_FILE_BYTES].decode("utf-8", "replace")
        except Exception:
            return ""
    return ""


def fetch_readme(owner: str, repo: str) -> str:
    data = _get_json(f"/repos/{owner}/{repo}/readme")
    if isinstance(data, dict) and data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"])[:MAX_FILE_BYTES].decode("utf-8", "replace")
        except Exception:
            return ""
    return ""


def fetch_doc(entry: str) -> dict:
    """Nhận 1 phần tử của report/description. Trả {source, text, ok}.

    Ba dạng đầu vào:
      - .../blob/<ref>/<path>  -> đọc đúng file đó
      - link repo (kèm hoặc không kèm #readme) -> đọc README của repo
      - text thường -> dùng luôn, không gọi mạng
    """
    e = (entry or "").strip()
    if not e:
        return {"source": "", "text": "", "ok": False}
    if not e.lower().startswith("http"):
        return {"source": "inline", "text": e, "ok": True}

    blob = parse_blob_url(e)
    if blob:
        owner, repo, ref, path = blob
        text = fetch_file(owner, repo, path, ref)
        return {"source": e, "text": text, "ok": bool(text)}

    parsed = parse_repo_url(e)
    if parsed:
        text = fetch_readme(*parsed)
        return {"source": e + " (README)", "text": text, "ok": bool(text)}
    return {"source": e, "text": "", "ok": False}


def fetch_commits(owner: str, repo: str, author: str) -> dict:
    """Commit của đúng người này trên đúng repo lab này.

    Lọc theo author trước. Ra 0 thì đếm lại toàn bộ commit của repo — email git
    chưa link GitHub là case thật, nhưng phải đánh dấu để hạ tin cậy sau này.
    """
    def _call(with_author: bool):
        params = {"per_page": MAX_COMMITS}
        if with_author:
            params["author"] = author
        data = _get_json(f"/repos/{owner}/{repo}/commits", params)
        if not isinstance(data, list):
            return None
        msgs = [c.get("commit", {}).get("message", "").split("\n")[0] for c in data]
        dates = [c.get("commit", {}).get("author", {}).get("date", "") for c in data]
        return {
            "count": len(data),
            "messages": [m for m in msgs if m][:30],
            "first_at": min([d for d in dates if d], default=""),
            "last_at": max([d for d in dates if d], default=""),
        }

    if author:
        got = _call(True)
        if got is None:
            return {"count": 0, "messages": [], "attribution": "error",
                    "first_at": "", "last_at": ""}
        if got["count"] > 0:
            got["attribution"] = "author-filter"
            return got

    got = _call(False) or {"count": 0, "messages": [], "first_at": "", "last_at": ""}
    got["attribution"] = "all-commits" if got["count"] else "none"
    return got


def fetch_repo_meta(url: str) -> dict:
    """Metadata + cây file + README của 1 repo. Cache theo URL trong 1 lần chạy."""
    if url in _repo_cache:
        return _repo_cache[url]
    parsed = parse_repo_url(url)
    if not parsed:
        out = {"ok": False, "error": f"URL repo không hợp lệ: {url}"}
        _repo_cache[url] = out
        return out
    owner, repo = parsed
    info = _get_json(f"/repos/{owner}/{repo}")
    if not isinstance(info, dict) or "full_name" not in info:
        out = {"ok": False, "error": f"Không đọc được repo {owner}/{repo} (private / sai tên / rate limit)"}
        _repo_cache[url] = out
        return out
    branch = info.get("default_branch", "main")
    tree_data = _get_json(f"/repos/{owner}/{repo}/git/trees/{branch}", {"recursive": "1"})
    tree = ([n["path"] for n in tree_data.get("tree", []) if n.get("type") == "blob"]
            if isinstance(tree_data, dict) else [])
    langs = _get_json(f"/repos/{owner}/{repo}/languages") or {}
    out = {
        "ok": True, "owner": owner, "repo": repo, "full_name": info["full_name"],
        "default_branch": branch, "is_fork": info.get("fork", False),
        "languages": langs, "tree": tree[:300], "readme": fetch_readme(owner, repo),
    }
    _repo_cache[url] = out
    return out


# ---------- gom theo (student, lab) ----------

def crawl_student_lab(student: dict, entry: dict) -> dict:
    """Toàn bộ bằng chứng thô của 1 học viên trong 1 lab."""
    login = student["github_login"]
    repo_url = entry["repo_url"]
    out = {
        "mssv": student["mssv"], "name": student["name"], "lab": entry["lab"],
        "github_login": login, "repo_url": repo_url,
        "repo_ok": False, "repo_error": "", "languages": {}, "tree": [],
        "commits": {"count": 0, "messages": [], "attribution": "none"},
        "reports": [], "group_reports": [],
        "blockers": entry["blockers"], "intentions": entry["intentions"],
    }
    if repo_url:
        meta = fetch_repo_meta(repo_url)
        if meta.get("ok"):
            out.update({"repo_ok": True, "languages": meta["languages"],
                        "tree": meta["tree"][:80]})
            out["commits"] = fetch_commits(meta["owner"], meta["repo"], login)
            # không khai report -> README của repo lab chính là báo cáo
            if not entry["report"] and meta["readme"]:
                out["reports"].append({"source": repo_url + " (README)",
                                       "text": meta["readme"], "ok": True})
        else:
            out["repo_error"] = meta.get("error", "")

    for u in entry["report"]:
        out["reports"].append(fetch_doc(u))
    for u in entry["group_report"]:
        out["group_reports"].append(fetch_doc(u))

    out["has_report"] = any(r["ok"] for r in out["reports"])
    out["has_group_report"] = any(r["ok"] for r in out["group_reports"])
    return out


def crawl_lab(lab: dict) -> dict:
    """Tài liệu đề bài của 1 lab: các file trong description + README repo lab."""
    out = {"lab": lab["name"], "repo_url": lab["repo_url"], "docs": [],
           "repo_ok": False, "tree": []}
    if lab["repo_url"]:
        meta = fetch_repo_meta(lab["repo_url"])
        if meta.get("ok"):
            out["repo_ok"] = True
            out["tree"] = meta["tree"][:120]
            if not lab["description"] and meta["readme"]:
                out["docs"].append({"source": lab["repo_url"] + " (README)",
                                    "text": meta["readme"], "ok": True})
    for entry in lab["description"]:
        out["docs"].append(fetch_doc(entry))
    out["has_docs"] = any(d["ok"] for d in out["docs"])
    return out


# ---------- cache ----------

def cache_path(kind: str, *parts: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    safe = "__".join(re.sub(r"[^\w.-]", "_", p) for p in parts)
    return CACHE / f"{kind}__{safe}.json"


def read_cache(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def write_cache(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
