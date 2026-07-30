"""Fetch project context straight from a GitHub repo URL — README, file tree,
dependency files, and any extra docs the AI decides it needs.

Đi qua src/gh_http nên có sẵn session tái dùng + ETag cache. Các file dependency
và file phụ được lấy song song.
"""
import base64
import re
from concurrent.futures import ThreadPoolExecutor

from .gh_http import get, get_json

MAX_FILE_BYTES = 40_000
MAX_PARALLEL = 6
DEP_FILENAMES = {"requirements.txt", "package.json", "pom.xml", "build.gradle",
                 "pyproject.toml", "go.mod", "Cargo.toml", "composer.json", "Gemfile"}


def parse_repo_url(url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/?#]|$)", url.strip())
    return (m.group(1), m.group(2)) if m else None


def _decode(data) -> str:
    if isinstance(data, dict) and data.get("encoding") == "base64":
        try:
            return base64.b64decode(data["content"])[:MAX_FILE_BYTES].decode("utf-8", "replace")
        except Exception:
            return ""
    return ""


def _get_file(owner: str, repo: str, path: str) -> str:
    return _decode(get_json(f"/repos/{owner}/{repo}/contents/{path}"))


def fetch_repo_context(url: str) -> dict:
    """Returns {readme, tree (list of paths), dep_files {path: content}, error}."""
    empty = {"readme": "", "tree": [], "dep_files": {}}
    parsed = parse_repo_url(url)
    if not parsed:
        return {"error": f"URL repo không hợp lệ: {url}", **empty}
    owner, repo = parsed

    info = get(f"/repos/{owner}/{repo}")
    if not info["ok"]:
        if info["status"] == 404:
            return {"error": f"Không tìm thấy repo {owner}/{repo} (private hoặc sai tên)", **empty}
        return {"error": f"Lỗi gọi GitHub API: {info['error']}", **empty}
    branch = info["data"].get("default_branch", "main")

    # README và cây file không phụ thuộc nhau
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_readme = pool.submit(get_json, f"/repos/{owner}/{repo}/readme")
        f_tree = pool.submit(get_json, f"/repos/{owner}/{repo}/git/trees/{branch}",
                             {"recursive": "1"})
        readme = _decode(f_readme.result())
        tree_data = f_tree.result()

    tree = ([n["path"] for n in tree_data.get("tree", []) if n.get("type") == "blob"]
            if isinstance(tree_data, dict) else [])

    # dependency files are grabbed automatically, no LLM decision needed
    dep_paths = [p for p in tree
                 if p.rsplit("/", 1)[-1] in DEP_FILENAMES and p.count("/") <= 2][:4]
    dep_files = {}
    if dep_paths:
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
            for path, content in zip(dep_paths,
                                     pool.map(lambda p: _get_file(owner, repo, p), dep_paths)):
                if content:
                    dep_files[path] = content[:4000]

    return {"owner": owner, "repo": repo, "readme": readme, "tree": tree,
            "dep_files": dep_files, "error": None}


def fetch_extra_files(owner: str, repo: str, paths: list[str], max_files: int = 6) -> dict[str, str]:
    picked = paths[:max_files]
    if not picked:
        return {}
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        results = pool.map(lambda p: _get_file(owner, repo, p), picked)
    return {p: c for p, c in zip(picked, results) if c}
