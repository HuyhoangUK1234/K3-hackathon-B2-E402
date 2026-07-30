"""Union vector nhóm + đo mức phủ so với vector lab + xếp nhóm.

Không LLM, không mạng — toán thuần trên dict. Test được offline.

Union dùng MAX chứ không phải tổng: một người biết Python là đủ phủ yêu cầu
Python; 4 người cùng yếu không cộng lại thành một người giỏi.
"""
from itertools import combinations

SPOF_MARGIN = 0.15          # người thứ 2 kém hơn người dẫn đầu quá mức này -> 1 điểm tựa duy nhất
GAP_THRESHOLD = 0.6         # phủ dưới 60% yêu cầu của trục -> tính là thiếu

W_SPOF = 0.15               # phạt mỗi trục chỉ 1 người gánh
W_INTEREST = 0.10           # thưởng khi có người muốn học đúng trục đang thiếu
W_IMBALANCE = 0.20          # phạt nhóm lệch quá nhiều so với nhóm khác


def team_vector(members: list[dict]) -> dict[str, float]:
    """Union = max theo từng trục."""
    out: dict[str, float] = {}
    for m in members:
        for skill, val in m["vector"].items():
            if val > out.get(skill, 0.0):
                out[skill] = val
    return out


def coverage(members: list[dict], lab_vec: dict[str, float]) -> dict:
    """Nhóm phủ được bao nhiêu phần yêu cầu của lab.

    ratio = Σ w[s] × min(1, team[s]/w[s])  /  Σ w[s]
    """
    weights = {s: w for s, w in lab_vec.items() if w > 0}
    if not weights:
        return {"coverage": 0.0, "per_skill": [], "gaps": [], "carried_by": {},
                "single_point_of_failure": [], "note": "Lab chưa có vector yêu cầu."}

    team = team_vector(members)
    total_w = sum(weights.values())
    earned = 0.0
    per_skill, gaps, spof = [], [], []
    carried_by: dict[str, str] = {}

    for skill, w in sorted(weights.items(), key=lambda x: -x[1]):
        ranked = sorted(members, key=lambda m: -m["vector"].get(skill, 0.0))
        best = ranked[0] if ranked else None
        best_val = best["vector"].get(skill, 0.0) if best else 0.0
        second = ranked[1]["vector"].get(skill, 0.0) if len(ranked) > 1 else 0.0

        filled = min(1.0, best_val / w) if w else 0.0
        earned += w * filled

        row = {
            "skill": skill, "required": round(w, 3),
            "team_best": round(best_val, 3),
            "filled": round(filled, 3),
            "best_member": best["name"] if best and best_val > 0 else None,
            "backup": round(second, 3),
        }
        per_skill.append(row)

        if best_val > 0:
            carried_by[skill] = f"{best['name']} ({best_val:.2f})"
        if filled < GAP_THRESHOLD:
            interested = [m["name"] for m in members
                          if skill in m.get("interests", []) or skill in m.get("open_blockers", [])]
            closest = best["name"] if best and best_val > 0 else None
            gaps.append({"skill": skill, "required": round(w, 3),
                         "team_best": round(best_val, 3),
                         "closest": closest, "interested": interested})
        elif best_val > 0 and second < best_val - SPOF_MARGIN:
            spof.append(skill)

    return {
        "coverage": round(earned / total_w, 4),
        "per_skill": per_skill,
        "gaps": gaps,
        "carried_by": carried_by,
        "single_point_of_failure": spof,
        "members": [{"name": m["name"], "mssv": m["mssv"],
                     "strength": round(sum(m["vector"].values()), 3)} for m in members],
    }


def team_score(members: list[dict], lab_vec: dict[str, float], mean_strength: float) -> tuple[float, dict]:
    """Điểm xếp nhóm: phủ cao, ít điểm tựa đơn, có người muốn học chỗ thiếu, không lệch."""
    cov = coverage(members, lab_vec)
    interest_hits = sum(1 for g in cov["gaps"] if g["interested"])
    strength = sum(sum(m["vector"].values()) for m in members) / max(1, len(members))
    imbalance = abs(strength - mean_strength) / max(0.01, mean_strength)

    score = (cov["coverage"]
             - W_SPOF * len(cov["single_point_of_failure"]) / max(1, len(lab_vec))
             + W_INTEREST * interest_hits / max(1, len(cov["gaps"]) or 1)
             - W_IMBALANCE * min(1.0, imbalance))
    return round(score, 4), cov


def form_teams(students: list[dict], lab_vec: dict[str, float], team_size: int = 5,
               top_n: int = 5) -> dict:
    """Duyệt toàn bộ tổ hợp C(n, size). n<=25 chạy dưới 1 giây, không cần optimizer."""
    n = len(students)
    if n < team_size:
        return {"error": f"Chỉ có {n} học viên, không đủ cho nhóm {team_size} người.",
                "candidates": []}

    mean_strength = sum(sum(s["vector"].values()) for s in students) / max(1, n)
    scored = []
    for combo in combinations(students, team_size):
        score, cov = team_score(list(combo), lab_vec, mean_strength)
        scored.append({"score": score, "coverage": cov["coverage"],
                       "members": [m["name"] for m in combo],
                       "mssv": [m["mssv"] for m in combo],
                       "gaps": [g["skill"] for g in cov["gaps"]],
                       "single_point_of_failure": cov["single_point_of_failure"]})
    scored.sort(key=lambda x: -x["score"])
    from math import comb
    return {"evaluated": comb(n, team_size), "candidates": scored[:top_n]}


def partition_cohort(students: list[dict], lab_vec: dict[str, float],
                     team_size: int = 5) -> dict:
    """Chia CẢ cohort thành nhiều nhóm: chọn nhóm tốt nhất, bỏ ra, lặp lại.

    Greedy — không tối ưu toàn cục, nhưng dễ giải thích và đủ dùng ở quy mô lớp.
    """
    remaining = list(students)
    teams = []
    while len(remaining) >= team_size:
        res = form_teams(remaining, lab_vec, team_size, top_n=1)
        if not res.get("candidates"):
            break
        best = res["candidates"][0]
        picked = [s for s in remaining if s["mssv"] in best["mssv"]]
        teams.append({**best, "detail": coverage(picked, lab_vec)})
        remaining = [s for s in remaining if s["mssv"] not in best["mssv"]]
    leftover = [{"name": s["name"], "mssv": s["mssv"]} for s in remaining]
    return {"teams": teams, "leftover": leftover}
