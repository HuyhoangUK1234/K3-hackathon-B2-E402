"""Đọc vector đã dựng từ seed/.cache/ và phục vụ 2 câu hỏi:

  1. Cho sẵn nhóm MSSV -> nhóm này phủ được bao nhiêu % yêu cầu lab?
  2. Cho cả cohort     -> xếp nhóm nào phủ tốt nhất?

Không gọi LLM, không gọi mạng. Cache thiếu thì báo chạy scripts/build_graphs.py.
"""
from .coverage import coverage, form_teams, partition_cohort
from .crawl import cache_path, read_cache
from .seed_loader import lab_order, load_all


class GraphNotBuilt(Exception):
    """Chưa có cache — cần chạy scripts/build_graphs.py trước."""


def load_profiles() -> list[dict]:
    """Vector tích luỹ của mọi học viên có trong seed."""
    seed = load_all()
    out = []
    missing = []
    for s in seed["students"]:
        prof = read_cache(cache_path("profile", s["mssv"]))
        if prof is None:
            missing.append(s["name"])
            continue
        out.append(prof)
    if not out:
        raise GraphNotBuilt(
            "Chưa dựng vector học viên. Chạy: python scripts/build_graphs.py")
    if missing:
        for p in out:
            p.setdefault("_warnings", []).append(
                "Chưa có vector: " + ", ".join(missing))
    return out


def load_lab(lab_name: str) -> dict:
    req = read_cache(cache_path("lab", lab_name))
    if req is None:
        raise GraphNotBuilt(
            f"Chưa dựng vector lab '{lab_name}'. "
            f"Chạy: python scripts/build_graphs.py --lab {lab_name}")
    return req


def list_labs() -> list[dict]:
    seed = load_all()
    out = []
    for name in lab_order(seed["labs"]):
        req = read_cache(cache_path("lab", name))
        out.append({
            "name": name,
            "built": req is not None,
            "skill_count": len(req["vector"]) if req else 0,
            "summary": req.get("summary", "") if req else "",
            "confidence": req.get("confidence", "") if req else "",
            "depends_on": seed["labs"][name]["depends_on"],
        })
    return out


def list_students() -> list[dict]:
    return [{"mssv": p["mssv"], "name": p["name"], "github": p.get("github", ""),
             "labs_done": p.get("labs_done", []),
             "skill_count": len(p["vector"]),
             "strength": round(sum(p["vector"].values()), 3)}
            for p in load_profiles()]


def team_coverage(mssv_list: list[str], lab_name: str) -> dict:
    """Câu hỏi 1 — nhập 4-5 mã học viên, ra tỉ lệ phủ + chỗ thiếu."""
    profiles = {p["mssv"]: p for p in load_profiles()}
    members, not_found = [], []
    for m in mssv_list:
        key = str(m).strip()
        if key in profiles:
            members.append(profiles[key])
        else:
            not_found.append(key)
    if not members:
        return {"error": "Không tìm thấy học viên nào trong danh sách MSSV.",
                "not_found": not_found}

    req = load_lab(lab_name)
    cov = coverage(members, req["vector"])
    return {
        "lab": lab_name,
        "lab_summary": req.get("summary", ""),
        "lab_confidence": req.get("confidence", ""),
        "lab_skill_count": len(req["vector"]),
        "not_found": not_found,
        **cov,
    }


def suggest_teams(lab_name: str, team_size: int = 5, top_n: int = 5,
                  partition: bool = False) -> dict:
    """Câu hỏi 2 — xếp nhóm phủ tốt nhất cho lab."""
    profiles = load_profiles()
    req = load_lab(lab_name)
    if partition:
        res = partition_cohort(profiles, req["vector"], team_size)
    else:
        res = form_teams(profiles, req["vector"], team_size, top_n)
    return {"lab": lab_name, "lab_summary": req.get("summary", ""),
            "pool_size": len(profiles), **res}


def student_detail(mssv: str) -> dict:
    """Vector + lịch sử tăng trưởng của 1 học viên."""
    for p in load_profiles():
        if p["mssv"] == str(mssv).strip():
            return p
    return {"error": f"Không tìm thấy MSSV {mssv}"}
