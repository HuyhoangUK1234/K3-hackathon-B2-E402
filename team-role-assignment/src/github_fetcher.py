"""Flow 1 data collection — plain GitHub REST API calls, no AI.

All numbers shown to the user come from here, never from the LLM.
"""
import os
from collections import Counter

import requests
from dotenv import load_dotenv

from .schemas import GitHubData

load_dotenv()

API = "https://api.github.com"
TIMEOUT = 15


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _search_count(query: str) -> int:
    """Count via GitHub search API; returns 0 on any failure (rate limit etc.)."""
    try:
        resp = requests.get(f"{API}/search/issues", params={"q": query, "per_page": 1},
                            headers=_headers(), timeout=TIMEOUT)
        if resp.ok:
            return int(resp.json().get("total_count", 0))
    except requests.RequestException:
        pass
    return 0


def fetch_developer(username: str, max_repos: int = 8, max_commits: int = 30) -> GitHubData:
    """Fetch public profile, top repos (by push date), languages and recent commit messages."""
    username = username.strip().lstrip("@")
    try:
        user_resp = requests.get(f"{API}/users/{username}", headers=_headers(), timeout=TIMEOUT)
        if user_resp.status_code == 404:
            return GitHubData(username=username, error=f"Không tìm thấy user GitHub '{username}'")
        if user_resp.status_code == 403:
            return GitHubData(username=username, error="GitHub API bị rate limit — thêm GITHUB_TOKEN vào .env")
        user_resp.raise_for_status()
        user = user_resp.json()

        repos_resp = requests.get(
            f"{API}/users/{username}/repos",
            params={"sort": "pushed", "per_page": max_repos, "type": "owner"},
            headers=_headers(), timeout=TIMEOUT,
        )
        repos_resp.raise_for_status()
        all_repos = repos_resp.json()
        repos = [r for r in all_repos if not r.get("fork")]
        if not repos:
            # student pattern: fork the course repo and push work there —
            # forks are still their activity when they own nothing else
            repos = all_repos

        languages: Counter = Counter()
        top_repos = []
        for r in repos:
            top_repos.append({
                "name": r["name"],
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "stars": r.get("stargazers_count", 0),
                "topics": r.get("topics", []),
            })
            lang_resp = requests.get(r["languages_url"], headers=_headers(), timeout=TIMEOUT)
            if lang_resp.ok:
                for lang, n_bytes in lang_resp.json().items():
                    languages[lang] += n_bytes

        def _collect_commits(filter_author: bool) -> tuple[int, list[str]]:
            count, msgs = 0, []
            for r in repos[:4]:  # commits from the 4 most recently pushed repos
                params = {"per_page": 100}
                if filter_author:
                    params["author"] = username
                c_resp = requests.get(f"{API}/repos/{username}/{r['name']}/commits",
                                      params=params, headers=_headers(), timeout=TIMEOUT)
                if c_resp.ok:
                    items = c_resp.json()
                    count += len(items)
                    for c in items[: max_commits // 3 + 1]:
                        msg = c.get("commit", {}).get("message", "").split("\n")[0]
                        if msg:
                            msgs.append(f"[{r['name']}] {msg}")
            return count, msgs

        commit_count, commit_messages = _collect_commits(filter_author=True)
        if commit_count == 0:
            # commits often carry an unlinked git email; fall back to counting all
            # commits in the user's own repos (still their repos, weaker signal)
            commit_count, commit_messages = _collect_commits(filter_author=False)

        pr_count = _search_count(f"author:{username} type:pr")
        issue_count = _search_count(f"author:{username} type:issue")

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
    except requests.RequestException as e:
        return GitHubData(username=username, error=f"Lỗi gọi GitHub API: {e}")
