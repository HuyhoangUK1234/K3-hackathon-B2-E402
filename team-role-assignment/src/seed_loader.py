"""Đọc và validate 3 file seed: skills.json, labs.json, students.json.

Quy ước dùng chung cho mọi field kiểu "nội dung":
    - giá trị bắt đầu bằng http  -> URL, tầng crawl sẽ fetch
    - ngược lại                  -> coi là text/markdown viết thẳng
    - list rỗng / null           -> không có
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed"


class SeedError(Exception):
    """Seed sai cấu trúc — dừng ngay, không đoán."""


def _read_json(name: str):
    f = SEED / name
    if not f.exists():
        raise SeedError(f"Thiếu file {f}")
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SeedError(f"{name} không phải JSON hợp lệ: {e}") from e


def load_skills() -> dict[str, dict]:
    """{skill_id: {label, description}} — trục cố định của mọi vector."""
    raw = _read_json("skills.json")
    skills = {k: v for k, v in raw.items() if not k.startswith("_")}
    if not skills:
        raise SeedError("skills.json rỗng")
    for sid, meta in skills.items():
        if not isinstance(meta, dict) or "label" not in meta:
            raise SeedError(f"skills.json: '{sid}' phải là object có 'label'")
    return skills


def load_labs() -> dict[str, dict]:
    """{lab_name: {repo_url, description[], depends_on[]}} giữ nguyên thứ tự file."""
    raw = _read_json("labs.json")
    if not isinstance(raw, list):
        raise SeedError("labs.json phải là array")
    labs: dict[str, dict] = {}
    for i, item in enumerate(raw):
        name = (item.get("name") or "").strip()
        if not name:
            raise SeedError(f"labs.json[{i}] thiếu 'name'")
        if name in labs:
            raise SeedError(f"labs.json: lab '{name}' bị trùng")
        desc = item.get("description") or []
        labs[name] = {
            "name": name,
            "repo_url": (item.get("repo_url") or "").strip(),
            "description": [desc] if isinstance(desc, str) else list(desc),
            "depends_on": list(item.get("depends_on") or []),
        }
    for name, lab in labs.items():
        for dep in lab["depends_on"]:
            if dep not in labs:
                raise SeedError(f"lab '{name}' depends_on '{dep}' không tồn tại")
    _check_no_cycle(labs)
    return labs


def _check_no_cycle(labs: dict[str, dict]):
    """depends_on tạo vòng thì kế thừa yêu cầu sẽ lặp vô hạn."""
    state: dict[str, int] = {}   # 0 = đang duyệt, 1 = xong

    def visit(name: str, path: list[str]):
        if state.get(name) == 1:
            return
        if state.get(name) == 0:
            raise SeedError("depends_on tạo vòng lặp: " + " -> ".join(path + [name]))
        state[name] = 0
        for dep in labs[name]["depends_on"]:
            visit(dep, path + [name])
        state[name] = 1

    for name in labs:
        visit(name, [])


def load_students(labs: dict[str, dict]) -> list[dict]:
    """Danh sách học viên; mỗi lab entry được join sang labs.json."""
    raw = _read_json("students.json")
    if not isinstance(raw, list):
        raise SeedError("students.json phải là array")
    students = []
    seen_mssv = set()
    for i, s in enumerate(raw):
        mssv = str(s.get("MSSV") or "").strip()
        if not mssv:
            raise SeedError(f"students.json[{i}] thiếu MSSV")
        if mssv in seen_mssv:
            raise SeedError(f"MSSV trùng: {mssv}")
        seen_mssv.add(mssv)
        entries = []
        for e in s.get("labs") or []:
            lab_name = (e.get("name") or "").strip()
            if lab_name not in labs:
                raise SeedError(
                    f"{s.get('name')} có lab '{lab_name}' không có trong labs.json")
            entries.append({
                "lab": lab_name,
                "repo_url": (e.get("repo_url") or "").strip(),
                "report": list(e.get("report") or []),
                "group_report": list(e.get("group_report") or []),
                "blockers": list(e.get("blockers") or []),
                "intentions": list(e.get("intentions") or []),
            })
        students.append({
            "id": s.get("id"),
            "mssv": mssv,
            "name": s.get("name") or mssv,
            "github": (s.get("github") or "").strip(),
            "github_login": _login_from_url(s.get("github") or ""),
            "labs": entries,
        })
    return students


def _login_from_url(url: str) -> str:
    """https://github.com/VanTienDL -> VanTienDL. Rỗng nếu không parse được."""
    u = url.strip().rstrip("/")
    if not u:
        return ""
    if "github.com" not in u:
        return u          # người dùng điền thẳng username
    tail = u.split("github.com", 1)[1].lstrip("/:")
    return tail.split("/")[0] if tail else ""


def load_all() -> dict:
    skills = load_skills()
    labs = load_labs()
    students = load_students(labs)
    return {"skills": skills, "labs": labs, "students": students}


def lab_order(labs: dict[str, dict]) -> list[str]:
    """Thứ tự topo theo depends_on — lab nền trước, lab kế thừa sau."""
    out: list[str] = []
    done: set[str] = set()

    def visit(name: str):
        if name in done:
            return
        for dep in labs[name]["depends_on"]:
            visit(dep)
        done.add(name)
        out.append(name)

    for name in labs:
        visit(name)
    return out


if __name__ == "__main__":
    import sys
    # console Windows mặc định cp1252 -> vỡ khi in tiếng Việt
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = load_all()
    print(f"skills   : {len(data['skills'])} trục")
    print(f"labs     : {', '.join(lab_order(data['labs']))}")
    print(f"students : {len(data['students'])}")
    for s in data["students"]:
        labs_done = ", ".join(e["lab"] for e in s["labs"]) or "(chưa có lab)"
        print(f"  - {s['name']} ({s['mssv']}) @{s['github_login']} : {labs_done}")
