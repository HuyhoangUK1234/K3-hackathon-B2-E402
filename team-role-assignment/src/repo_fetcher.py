"""Fetch project context straight from a GitHub repo URL — README, file tree,
dependency files, and any extra docs the AI decides it needs.
"""
import base64
import re

import requests

from .github_fetcher import API, TIMEOUT, _headers

MAX_FILE_BYTES = 40_000
DEP_FILENAMES = {"requirements.txt", "package.json", "pom.xml", "build.gradle",
                 "pyproject.toml", "go.mod", "Cargo.toml", "composer.json", "Gemfile"}


def parse_repo_url(url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/?#]|$)", url.strip())
    return (m.group(1), m.group(2)) if m else None


def _get_file(owner: str, repo: str, path: str) -> str:
    resp = requests.get(f"{API}/repos/{owner}/{repo}/contents/{path}",
                        headers=_headers(), timeout=TIMEOUT)
    if not resp.ok:
        return ""
    data = resp.json()
    if isinstance(data, dict) and data.get("encoding") == "base64":
        try:
            raw = base64.b64decode(data["content"])[:MAX_FILE_BYTES]
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""


def fetch_repo_context(url: str) -> dict:
    """Returns {readme, tree (list of paths), dep_files {path: content}, error}."""
    parsed = parse_repo_url(url)
    if not parsed:
        return {"error": f"URL repo không hợp lệ: {url}", "readme": "", "tree": [], "dep_files": {}}
    owner, repo = parsed
    try:
        info = requests.get(f"{API}/repos/{owner}/{repo}", headers=_headers(), timeout=TIMEOUT)
        if info.status_code == 404:
            return {"error": f"Không tìm thấy repo {owner}/{repo} (private hoặc sai tên)",
                    "readme": "", "tree": [], "dep_files": {}}
        if info.status_code == 403:
            return {"error": "GitHub API rate limit — thêm GITHUB_TOKEN vào .env",
                    "readme": "", "tree": [], "dep_files": {}}
        info.raise_for_status()
        branch = info.json().get("default_branch", "main")

        readme = ""
        r = requests.get(f"{API}/repos/{owner}/{repo}/readme", headers=_headers(), timeout=TIMEOUT)
        if r.ok and r.json().get("encoding") == "base64":
            readme = base64.b64decode(r.json()["content"])[:MAX_FILE_BYTES].decode("utf-8", errors="replace")

        tree: list[str] = []
        t = requests.get(f"{API}/repos/{owner}/{repo}/git/trees/{branch}",
                         params={"recursive": "1"}, headers=_headers(), timeout=TIMEOUT)
        if t.ok:
            tree = [n["path"] for n in t.json().get("tree", []) if n.get("type") == "blob"]

        # dependency files are grabbed automatically, no LLM decision needed
        dep_files = {}
        for path in tree:
            fname = path.rsplit("/", 1)[-1]
            if fname in DEP_FILENAMES and path.count("/") <= 2 and len(dep_files) < 4:
                content = _get_file(owner, repo, path)
                if content:
                    dep_files[path] = content[:4000]

        return {"owner": owner, "repo": repo, "readme": readme, "tree": tree,
                "dep_files": dep_files, "error": None}
    except requests.RequestException as e:
        return {"error": f"Lỗi gọi GitHub API: {e}", "readme": "", "tree": [], "dep_files": {}}


def fetch_extra_files(owner: str, repo: str, paths: list[str], max_files: int = 6) -> dict[str, str]:
    out = {}
    for p in paths[:max_files]:
        content = _get_file(owner, repo, p)
        if content:
            out[p] = content
    return out
