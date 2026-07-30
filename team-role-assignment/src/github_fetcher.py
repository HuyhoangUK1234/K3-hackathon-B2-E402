"""Flow 1 data collection — plain GitHub REST API calls, no AI.

All numbers shown to the user come from here, never from the LLM.

Sau bước lấy user + danh sách repo (bắt buộc tuần tự), mọi call còn lại
(languages × 8, commits × 4, search × 2) chạy song song qua src/gh_http —
cùng session, cùng ETag cache.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .gh_http import API, TIMEOUT, get, get_json  # noqa: F401  (API/TIMEOUT re-export)
from .gh_http import headers as _headers          # noqa: F401  (dùng lại ở nơi khác)
from .schemas import GitHubData

MAX_PARALLEL = 8


def _search_count(query: str) -> int:
    """Count via GitHub search API; returns 0 on any failure (rate limit etc.).

    Search có quota riêng (30/phút) nên để TTL dài hơn: con số này đổi rất chậm.
    """
    data = get_json("/search/issues", {"q": query, "per_page": 1}, ttl=3600)
    try:
        return int(data.get("total_count", 0)) if data else 0
    except (AttributeError, TypeError, ValueError):
        return 0


def fetch_developer(username: str, max_repos: int = 8, max_commits: int = 30) -> GitHubData:
    """Fetch public profile, top repos (by push date), languages and recent commit messages."""
    username = username.strip().lstrip("@")
    if not username:
        return GitHubData(username="", error="Không nhập GitHub username")

    user_r = get(f"/users/{username}")
    if not user_r["ok"]:
        if user_r["status"] == 404:
            return GitHubData(username=username,
                              error=f"Không tìm thấy user GitHub '{username}'")
        return GitHubData(username=username, error=f"Lỗi gọi GitHub API: {user_r['error']}")
    user = user_r["data"]

    repos_r = get(f"/users/{username}/repos",
                  {"sort": "pushed", "per_page": max_repos, "type": "owner"})
    if not repos_r["ok"]:
        return GitHubData(username=username, error=f"Lỗi gọi GitHub API: {repos_r['error']}")
    all_repos = repos_r["data"] or []

    repos = [r for r in all_repos if not r.get("fork")]
    if not repos:
        # student pattern: fork the course repo and push work there —
        # forks are still their activity when they own nothing else
        repos = all_repos

    top_repos = [{
        "name": r["name"],
        "description": r.get("description") or "",
        "language": r.get("language") or "",
        "stars": r.get("stargazers_count", 0),
        "topics": r.get("topics", []),
    } for r in repos]

    commit_repos = repos[:4]      # commits from the 4 most recently pushed repos

    def _languages(repo: dict) -> dict:
        return get_json(repo["languages_url"]) or {}

    def _commits(repo: dict, filter_author: bool) -> tuple[int, list[str]]:
        params = {"per_page": 100}
        if filter_author:
            params["author"] = username
        items = get_json(f"/repos/{username}/{repo['name']}/commits", params)
        if not isinstance(items, list):
            return 0, []
        msgs = []
        for c in items[: max_commits // 3 + 1]:
            msg = c.get("commit", {}).get("message", "").split("\n")[0]
            if msg:
                msgs.append(f"[{repo['name']}] {msg}")
        return len(items), msgs

    # Toàn bộ phần còn lại độc lập nhau -> bắn song song một lượt.
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        f_langs = [pool.submit(_languages, r) for r in repos]
        f_commits = [pool.submit(_commits, r, True) for r in commit_repos]
        f_pr = pool.submit(_search_count, f"author:{username} type:pr")
        f_issue = pool.submit(_search_count, f"author:{username} type:issue")

        languages: Counter = Counter()
        for f in f_langs:
            for lang, n_bytes in f.result().items():
                languages[lang] += n_bytes

        commit_count = 0
        commit_messages: list[str] = []
        for f in f_commits:
            n, msgs = f.result()
            commit_count += n
            commit_messages.extend(msgs)

        if commit_count == 0 and commit_repos:
            # commits often carry an unlinked git email; fall back to counting all
            # commits in the user's own repos (still their repos, weaker signal)
            f_all = [pool.submit(_commits, r, False) for r in commit_repos]
            for f in f_all:
                n, msgs = f.result()
                commit_count += n
                commit_messages.extend(msgs)

        pr_count, issue_count = f_pr.result(), f_issue.result()

    return GitHubData(
        username=username,
        display_name=user.get("name") or username,
        public_repos=user.get("public_repos", 0),
        languages=dict(languages.most_common(10)),
        top_repos=top_repos,
        recent_commit_messages=commit_messages[:max_commits],
        commit_count=commit_count,
        pr_count=pr_count,
        issue_count=issue_count,
    )
