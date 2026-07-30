"""Test offline tầng toán: union, coverage, tăng trưởng, xếp nhóm.

Không cần API key, không cần mạng. Chạy: python scripts/test_coverage.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.coverage import coverage, form_teams, team_vector          # noqa: E402
from src.vectors import accumulate_student, lab_required            # noqa: E402


def dev(name, vector, interests=(), mssv=None):
    return {"name": name, "mssv": mssv or name, "vector": vector,
            "interests": list(interests), "open_blockers": []}


def test_union_is_max():
    a = dev("A", {"python": 0.8, "git-github": 0.2})
    b = dev("B", {"python": 0.3, "documentation": 0.6})
    t = team_vector([a, b])
    assert t["python"] == 0.8, t          # không cộng thành 1.1
    assert t["documentation"] == 0.6
    assert t["git-github"] == 0.2
    print("[OK] union = max, không cộng dồn giữa người")


def test_growth_diminishing():
    """Học lại kỹ năng cũ -> dài thêm, giảm dần, không vượt 1."""
    recs = [
        {"lab": "lab1", "gains": {"git-github": 0.30}, "interests": [], "blocked": []},
        {"lab": "lab2", "gains": {"git-github": 0.40}, "interests": [], "blocked": []},
        {"lab": "lab3", "gains": {"git-github": 0.40}, "interests": [], "blocked": []},
    ]
    acc = accumulate_student(recs, ["lab1", "lab2", "lab3"])
    hist = [h["after"] for h in acc["history"]["git-github"]]
    assert hist == [0.3, 0.58, 0.748], hist
    step1, step2, step3 = hist[0], hist[1] - hist[0], hist[2] - hist[1]
    assert step1 > step2 > step3, (step1, step2, step3)
    assert hist[-1] < 1.0
    print(f"[OK] tăng trưởng giảm dần: {hist} (bước {step1:.2f} > {step2:.2f} > {step3:.2f})")


def test_growth_new_axis():
    """Kỹ năng mới ở lab sau -> trục đang 0 nay khác 0 = thêm chiều."""
    recs = [
        {"lab": "lab1", "gains": {"python": 0.4}, "interests": [], "blocked": []},
        {"lab": "lab2", "gains": {"python": 0.2, "business-analysis": 0.35},
         "interests": [], "blocked": []},
    ]
    acc = accumulate_student(recs, ["lab1", "lab2"])
    assert set(acc["vector"]) == {"python", "business-analysis"}
    assert len(acc["history"]["python"]) == 2         # trục cũ dài thêm
    assert len(acc["history"]["business-analysis"]) == 1   # trục mới xuất hiện
    print(f"[OK] thêm chiều: lab1 1 trục -> lab2 {len(acc['vector'])} trục")


def test_lab_inherits_prereq():
    """lab2 phủ lab1: trục lab1 xuất hiện trong lab2 với hệ số 0.5."""
    labs = {
        "lab1": {"name": "lab1", "depends_on": []},
        "lab2": {"name": "lab2", "depends_on": ["lab1"]},
        "lab3": {"name": "lab3", "depends_on": ["lab2"]},
    }
    declared = {
        "lab1": {"weights": {"python": 1.0, "api-integration": 1.0}},
        "lab2": {"weights": {"business-analysis": 1.0, "documentation": 1.0}},
        "lab3": {"weights": {"ai-agent-design": 1.0}},
    }
    r2 = lab_required("lab2", labs, declared, {})["vector"]
    assert r2["business-analysis"] == 1.0
    assert r2["python"] == 0.5, r2                    # kế thừa 1 bậc
    r3 = lab_required("lab3", labs, declared, {})["vector"]
    assert r3["documentation"] == 0.5                 # 1 bậc từ lab2
    assert r3["python"] == 0.25, r3                   # 2 bậc từ lab1
    print(f"[OK] kế thừa: lab2.python={r2['python']} lab3.python={r3['python']}")


def test_lab_learns_from_cohort():
    """Đề bài không nói git, nhưng cả cohort đều commit -> lab tự thêm trục."""
    labs = {"lab1": {"name": "lab1", "depends_on": []}}
    declared = {"lab1": {"weights": {"python": 1.0}}}
    gains = [
        {"gains": {"python": 0.5, "git-github": 0.4}},
        {"gains": {"python": 0.4, "git-github": 0.3}},
        {"gains": {"python": 0.3, "git-github": 0.25}},
        {"gains": {"python": 0.3, "notebook-jupyter": 0.3}},
    ]
    from src.vectors import lab_observed
    skills = {k: {} for k in ["python", "git-github", "notebook-jupyter"]}
    obs = lab_observed(gains, skills)
    assert obs["git-github"] == 0.60, obs             # 4/4 -> đa số
    assert obs["notebook-jupyter"] == 0.35, obs       # 1/4 -> thiểu số
    req = lab_required("lab1", labs, declared, {"lab1": obs})
    assert "git-github" in req["source"]["observed_only"]
    print(f"[OK] lab học từ cohort: thêm {req['source']['observed_only']}")


def test_coverage_and_gaps():
    lab_vec = {"python": 1.0, "business-analysis": 1.0, "documentation": 0.6}
    members = [
        dev("An", {"python": 0.9, "documentation": 0.5}),
        dev("Binh", {"python": 0.4, "business-analysis": 0.1}, interests=["business-analysis"]),
    ]
    cov = coverage(members, lab_vec)
    gap_skills = [g["skill"] for g in cov["gaps"]]
    assert "business-analysis" in gap_skills
    assert "python" not in gap_skills
    ba = next(g for g in cov["gaps"] if g["skill"] == "business-analysis")
    assert "Binh" in ba["interested"]
    assert "python" in cov["single_point_of_failure"]     # 0.9 vs 0.4
    assert 0 < cov["coverage"] < 1
    print(f"[OK] coverage={cov['coverage']:.2f} gap={gap_skills} spof={cov['single_point_of_failure']}")


def test_full_coverage():
    lab_vec = {"python": 1.0, "documentation": 0.5}
    members = [dev("A", {"python": 1.0, "documentation": 0.9}),
               dev("B", {"python": 0.95, "documentation": 0.85})]
    cov = coverage(members, lab_vec)
    assert cov["coverage"] == 1.0, cov["coverage"]
    assert not cov["gaps"]
    assert not cov["single_point_of_failure"]            # có người dự phòng
    print("[OK] phủ đủ -> coverage=1.0, không gap, không điểm tựa đơn")


def test_form_teams():
    lab_vec = {"python": 1.0, "business-analysis": 1.0, "ui-frontend": 1.0}
    pool = [
        dev("py1", {"python": 0.8}, mssv="m1"),
        dev("py2", {"python": 0.7}, mssv="m2"),
        dev("ba1", {"business-analysis": 0.8}, mssv="m3"),
        dev("ui1", {"ui-frontend": 0.8}, mssv="m4"),
        dev("py3", {"python": 0.6}, mssv="m5"),
    ]
    res = form_teams(pool, lab_vec, team_size=3, top_n=3)
    best = res["candidates"][0]
    assert res["evaluated"] == 10
    assert set(best["members"]) & {"ba1"} and set(best["members"]) & {"ui1"}
    print(f"[OK] xếp nhóm: duyệt {res['evaluated']} tổ hợp, "
          f"tốt nhất {best['members']} coverage={best['coverage']:.2f}")


def test_empty_profile():
    lab_vec = {"python": 1.0}
    cov = coverage([dev("trống", {})], lab_vec)
    assert cov["coverage"] == 0.0
    assert cov["gaps"][0]["closest"] is None
    print("[OK] hồ sơ rỗng -> coverage 0, không bịa người gánh")


TESTS = [test_union_is_max, test_growth_diminishing, test_growth_new_axis,
         test_lab_inherits_prereq, test_lab_learns_from_cohort,
         test_coverage_and_gaps, test_full_coverage, test_form_teams,
         test_empty_profile]

if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} PASS")
    sys.exit(1 if failed else 0)
