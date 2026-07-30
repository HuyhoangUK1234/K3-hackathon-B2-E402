"""Chạy golden set qua LLM thật và chấm tự động các check kiểm được bằng máy.

Run:  python scripts/run_eval.py          # cần OPENAI_API_KEY trong .env
Chấm: mỗi case PASS/FAIL theo expected trong eval/golden_set.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dev_analyzer import analyze_developer
from src.matcher import match
from src.project_analyzer import analyze_project
from src.schemas import DeveloperProfile, GitHubData, Skill

results: list[tuple[str, bool, str]] = []


def record(case_id: str, ok: bool, detail: str):
    results.append((case_id, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {case_id}: {detail}")


# ---- Project flow cases ----

def run_p01():
    tg = analyze_project(
        "# Shop Online\nWeb bán hàng. Frontend React, backend FastAPI, PostgreSQL, deploy Docker.",
        "fastapi\nuvicorn\nsqlalchemy\npsycopg2",
    )
    stack = " ".join(tg.tech_stack).lower()
    ok = (tg.confidence in ("medium", "high")
          and all(t.lower() in stack for t in ["react", "fastapi", "postgres"])
          and len(tg.tasks) >= 4
          and not any(t in stack for t in ["kubernetes", "tensorflow"]))
    record("P01", ok, f"confidence={tg.confidence}, stack={tg.tech_stack}, tasks={len(tg.tasks)}")


def run_p02():
    tg = analyze_project("App quản lý công việc.", "")
    ok = tg.confidence == "low" and len(tg.clarifying_questions) >= 2
    record("P02", ok, f"confidence={tg.confidence}, questions={len(tg.clarifying_questions)}")


# ---- Developer flow cases (synthetic GitHubData, no network) ----

def run_d01():
    gh = GitHubData(username="dev1", display_name="Dev 1", public_repos=3,
                    languages={"Python": 500000},
                    top_repos=[{"name": "data-tool", "description": "ETL tool", "language": "Python",
                                "stars": 2, "topics": []}],
                    recent_commit_messages=["[data-tool] add pandas pipeline"])
    p = analyze_developer(gh, self_skills="Java", learning_readiness=3, years_experience=2)
    java = [s for s in p.skills if s.name.lower() == "java"]
    every_evidence = all(s.evidence.strip() for s in p.skills)
    ok = (every_evidence and java
          and "self" in java[0].evidence.lower()
          and java[0].level in ("beginner", "intermediate"))
    record("D01", ok, f"java={java[0].model_dump() if java else 'MISSING'}, all_evidence={every_evidence}")


def run_d02():
    gh = GitHubData(username="dev2", display_name="Dev 2", public_repos=2,
                    languages={"JavaScript": 300000},
                    top_repos=[{"name": "todo-app", "description": "", "language": "JavaScript",
                                "stars": 0, "topics": []}],
                    recent_commit_messages=["[todo-app] fix button"])
    p = analyze_developer(gh, self_skills="", learning_readiness=3, years_experience=1)
    names = {s.name.lower() for s in p.skills}
    banned = {"rust", "go", "kubernetes"}
    ok = not (names & banned)
    record("D02", ok, f"skills={sorted(names)}")


# ---- Matching cases (synthetic profiles) ----

def _profile(name: str, skill: str, evidence: str) -> DeveloperProfile:
    return DeveloperProfile(
        github_username=name, display_name=name,
        skills=[Skill(name=skill, level="advanced", evidence=evidence)],
        strengths=[skill], wants_to_learn=[], learning_readiness=3,
        years_experience=3, suggested_roles=["Backend" if "java" in skill.lower() else "Frontend"],
        summary=f"{name} mạnh {skill}.",
    )


def run_m01_m02():
    devs = [
        _profile("an", "Java/Spring Boot", "[shop-api] 34 commits Spring Boot"),
        _profile("binh", "React", "[web-ui] 50 commits React"),
    ]
    from src.schemas import ProjectTask, TaskGraph
    tg = TaskGraph(
        project_type="Web", scale="small", tech_stack=["Java", "React", "PyTorch"],
        modules=["api", "ui", "ai"],
        tasks=[
            ProjectTask(name="Backend API", description="REST API", required_skills=["Java", "Spring Boot"],
                        difficulty="high", estimate_days=10),
            ProjectTask(name="Frontend", description="UI React", required_skills=["React"],
                        difficulty="medium", estimate_days=8),
            ProjectTask(name="AI Model", description="Train model PyTorch", required_skills=["Python", "PyTorch"],
                        difficulty="high", estimate_days=12),
        ],
        confidence="high",
    )
    mr = match(devs, tg)
    pairs = {a.developer.lower(): a.task for a in mr.assignments}
    m01_ok = (pairs.get("an") == "Backend API" and pairs.get("binh") == "Frontend"
              and all(a.reasons for a in mr.assignments))
    record("M01", m01_ok, f"pairs={pairs}")
    m02_ok = any("ai model" in t.lower() for t in mr.unassigned_tasks) and len(mr.warnings) >= 1
    record("M02", m02_ok, f"unassigned={mr.unassigned_tasks}, warnings={len(mr.warnings)}")


if __name__ == "__main__":
    for fn in (run_p01, run_p02, run_d01, run_d02, run_m01_m02):
        try:
            fn()
        except Exception as e:
            record(fn.__name__, False, f"EXCEPTION: {e}")
    n_pass = sum(1 for _, ok, _ in results if ok)
    print(f"\n== {n_pass}/{len(results)} PASS ==")
    sys.exit(0 if n_pass == len(results) else 1)
