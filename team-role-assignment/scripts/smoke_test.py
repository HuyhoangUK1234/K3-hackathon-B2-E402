"""Offline smoke test: schemas validate, modules import, GitHub fetcher works (no OpenAI call).

Run:  python scripts/smoke_test.py [github_username]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.schemas import (Assignment, DeveloperProfile, GitHubData, MatchResult,
                         ProjectTask, Skill, TaskGraph)


def test_schemas():
    p = DeveloperProfile(
        github_username="alice", display_name="Alice",
        skills=[Skill(name="Python", level="advanced", evidence="[repo x] 40 commits")],
        strengths=["backend"], wants_to_learn=["MLOps"], learning_readiness=4,
        years_experience=3, suggested_roles=["Backend"], summary="ok",
    )
    tg = TaskGraph(
        project_type="Web", scale="small", tech_stack=["React"], modules=["auth"],
        tasks=[ProjectTask(name="API", description="d", required_skills=["Python"],
                           difficulty="high", estimate_days=5)],
        confidence="low", clarifying_questions=["DB nào?"],
    )
    mr = MatchResult(
        assignments=[Assignment(developer="alice", task="API", fit_score=90,
                                reasons=["40 commits Python repo x"])],
        workload_notes="ok", unassigned_tasks=[], warnings=[],
    )
    # round-trip qua JSON như LLM sẽ trả về
    assert DeveloperProfile.model_validate_json(p.model_dump_json())
    assert TaskGraph.model_validate_json(tg.model_dump_json())
    assert MatchResult.model_validate_json(mr.model_dump_json())
    print("[OK] schemas: validate + JSON round-trip")


def test_imports():
    import src.dev_analyzer, src.llm, src.matcher, src.project_analyzer  # noqa: F401
    print("[OK] imports: all modules load")


def test_github(username: str):
    from src.github_fetcher import fetch_developer
    gh = fetch_developer(username)
    if gh.error:
        print(f"[WARN] github: {gh.error}")
    else:
        assert isinstance(gh, GitHubData)
        print(f"[OK] github: {gh.username} — {gh.public_repos} repos, "
              f"langs={list(gh.languages)[:3]}, {len(gh.recent_commit_messages)} commits")


if __name__ == "__main__":
    test_schemas()
    test_imports()
    if len(sys.argv) > 1:
        test_github(sys.argv[1])
    print("SMOKE TEST PASSED")
