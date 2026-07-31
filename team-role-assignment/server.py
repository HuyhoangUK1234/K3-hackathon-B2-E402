"""FastAPI server: serves the AI Lab Team UI and the analysis/chat/ticket endpoints."""
import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from src.pipeline import analyze_all, analyze_match, analyze_prepare, chat_reply

load_dotenv()

app = FastAPI(title="AI Lab Team")
STATIC = Path(__file__).parent / "static"
DATA = Path(__file__).parent / "data"
SEED = Path(__file__).parent / "seed"
DATA.mkdir(exist_ok=True)
_io_lock = Lock()


def _coaches() -> list[dict]:
    """Tài khoản Lab Coach từ seed/labcoach.json. Không có file -> danh sách rỗng."""
    f = SEED / "labcoach.json"
    if not f.exists():
        return []
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [{"id": str(c.get("id", "")).strip(), "name": c.get("name") or ""}
            for c in raw if str(c.get("id", "")).strip()]


def _find_coach(coach_id) -> dict | None:
    key = str(coach_id or "").strip()
    return next((c for c in _coaches() if c["id"] == key), None) if key else None


def _load(name: str) -> list:
    f = DATA / name
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def _save(name: str, items: list):
    with _io_lock:
        (DATA / name).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def _now() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


class AnalyzeRequest(BaseModel):
    setup: dict
    members: list[dict]


class MatchRequest(BaseModel):
    draftId: str
    volunteers: dict = {}      # {skill_id: developer_id} — nhóm chốt ai nhận học kỹ năng thiếu


class ChatRequest(BaseModel):
    message: str
    state_summary: str = ""
    history: list[dict] = []        # [{role: user|assistant, content: str}] — bộ nhớ hội thoại


class TicketCreate(BaseModel):
    groupId: str = ""
    studentName: str = ""
    labName: str = ""
    issue: str
    priority: str = "medium"


class TicketUpdate(BaseModel):
    status: str | None = None       # pending | resolved
    coachResponse: str | None = None
    coachId: str | int | None = None  # phải khớp seed/labcoach.json


class GroupUpdate(BaseModel):
    status: str | None = None       # Analyzed | Approved | Needs Revision
    coachFeedback: str | None = None
    assignments: dict | None = None  # student may re-drag tasks; persist
    taskStatus: dict | None = None   # {taskId: todo|doing|done} — bảng việc kiểu Jira mini


def _group_summary(g: dict) -> dict:
    payload = g.get("payload", {})
    devs = payload.get("devs", [])
    assignments = g.get("assignments") or payload.get("assignments", {})
    fit_matrix = payload.get("fitMatrix", {})
    tasks = {t["id"]: t for t in payload.get("tasks", [])}
    # avg fit over assigned pairs
    scores = [fit_matrix.get(tid, {}).get(did, {}).get("score")
              for tid, did in assignments.items() if did]
    scores = [s for s in scores if isinstance(s, (int, float))]
    avg_fit = round(sum(scores) / len(scores), 1) if scores else 0
    # balance: share of estimate days per dev
    load = {d["id"]: 0.0 for d in devs}
    total = 0.0
    for tid, did in assignments.items():
        days = tasks.get(tid, {}).get("estimateDays", 0) or 0
        total += days
        if did in load:
            load[did] += days
    if total > 0 and load:
        shares = [v / total for v in load.values()]
        mean = sum(shares) / len(shares)
        var = sum((s - mean) ** 2 for s in shares) / len(shares)
        cv = (var ** 0.5) / mean if mean else 1
        balance = max(0, round(100 * (1 - cv), 1))
    else:
        balance = 0
    return {
        "id": g["id"], "createdAt": g.get("createdAt", ""),
        "projectName": payload.get("project", {}).get("name", ""),
        "repoUrl": g.get("setup", {}).get("repoUrl", ""),
        "memberCount": len(devs),
        "memberNames": [d["name"] for d in devs],
        "taskCount": len(tasks),
        "avgFitScore": avg_fit, "balanceRatio": balance,
        "status": g.get("status", "Analyzed"),
        "coachFeedback": g.get("coachFeedback", ""),
    }


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "openai_key": bool(os.getenv("OPENAI_API_KEY", "").strip()),
            "github_token": bool(os.getenv("GITHUB_TOKEN", "").strip())}


@app.get("/api/skills")
def list_skills():
    """Danh mục kỹ năng chuẩn (seed/skills.json) — UI cho chọn tag thay vì gõ tay."""
    from src.skills import as_options
    return _graph_call(as_options)


def _persist_group(setup: dict, members: list, payload: dict) -> dict:
    group = {
        "id": f"G{int(time.time()) % 1000000}",
        "createdAt": _now(),
        "setup": setup,
        "members": members,
        "payload": payload,
        "status": "Analyzed",
        "coachFeedback": "",
    }
    groups = _load("groups.json")
    groups.append(group)
    _save("groups.json", groups)
    payload["groupId"] = group["id"]
    payload["createdAt"] = group["createdAt"]
    payload["status"] = group["status"]
    payload["coachFeedback"] = ""
    return payload


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Chạy một lượt cả 3 luồng (giữ cho script/test cũ)."""
    if not req.members:
        return JSONResponse(status_code=400, content={"error": "Cần ít nhất 1 thành viên."})
    try:
        payload = analyze_all(req.setup, req.members)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    return _persist_group(req.setup, req.members, payload)


@app.post("/api/analyze/prepare")
def analyze_prepare_step(req: AnalyzeRequest):
    """Luồng 1+2. Trả về hồ sơ + đầu việc + danh sách kỹ năng nhóm còn thiếu.

    Chưa tốn lượt matching: người dùng còn được chốt ai nhận học chỗ thiếu.
    """
    if not req.members:
        return JSONResponse(status_code=400, content={"error": "Cần ít nhất 1 thành viên."})
    try:
        draft = analyze_prepare(req.setup, req.members)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    draft_id = f"DR{int(time.time()) % 1000000}"
    drafts = _load("drafts.json")[-19:]          # giữ 20 bản nháp gần nhất là đủ
    drafts.append({"id": draft_id, "createdAt": _now(), "setup": req.setup,
                   "members": req.members, "draft": draft})
    _save("drafts.json", drafts)
    return {"draftId": draft_id, **draft}


@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: str):
    """Lấy lại bản nháp để F5 giữa chừng không mất màn chốt kỹ năng."""
    entry = next((d for d in _load("drafts.json") if d["id"] == draft_id), None)
    if entry is None:
        return JSONResponse(status_code=404, content={"error": "Bản nháp không còn."})
    return {"draftId": entry["id"], **entry["draft"]}


@app.post("/api/analyze/match")
def analyze_match_step(req: MatchRequest):
    """Luồng 3 trên bản nháp đã chuẩn bị, có kèm quyết định ai học kỹ năng thiếu."""
    entry = next((d for d in _load("drafts.json") if d["id"] == req.draftId), None)
    if entry is None:
        return JSONResponse(status_code=404, content={
            "error": "Bản nháp đã hết hạn hoặc server vừa khởi động lại — chạy phân tích lại."})
    try:
        payload = analyze_match(entry["draft"], req.volunteers)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    return _persist_group(entry["setup"], entry["members"], payload)


@app.get("/api/groups")
def list_groups():
    return [_group_summary(g) for g in reversed(_load("groups.json"))]


@app.get("/api/groups/{group_id}")
def get_group(group_id: str):
    for g in _load("groups.json"):
        if g["id"] == group_id:
            payload = dict(g["payload"])
            if g.get("assignments"):
                payload["assignments"] = g["assignments"]
            payload["taskStatus"] = g.get("taskStatus") or {}
            payload["groupId"] = g["id"]
            payload["createdAt"] = g.get("createdAt", "")
            payload["status"] = g.get("status", "Analyzed")
            payload["coachFeedback"] = g.get("coachFeedback", "")
            return payload
    return JSONResponse(status_code=404, content={"error": "Không tìm thấy nhóm."})


@app.patch("/api/groups/{group_id}")
def update_group(group_id: str, req: GroupUpdate):
    groups = _load("groups.json")
    for g in groups:
        if g["id"] == group_id:
            if req.status is not None:
                g["status"] = req.status
            if req.coachFeedback is not None:
                g["coachFeedback"] = req.coachFeedback
            if req.assignments is not None:
                g["assignments"] = req.assignments
            if req.taskStatus is not None:
                g["taskStatus"] = req.taskStatus
            _save("groups.json", groups)
            return {"ok": True, "group": _group_summary(g)}
    return JSONResponse(status_code=404, content={"error": "Không tìm thấy nhóm."})


@app.get("/api/tickets")
def list_tickets(group_id: str = ""):
    tickets = _load("tickets.json")
    if group_id:
        tickets = [t for t in tickets if t.get("groupId") == group_id]
    return list(reversed(tickets))


@app.post("/api/tickets")
def create_ticket(req: TicketCreate):
    if not req.issue.strip():
        return JSONResponse(status_code=400, content={"error": "Cần mô tả vấn đề."})
    tickets = _load("tickets.json")
    ticket = {
        "id": f"TK-{len(tickets) + 101}",
        "groupId": req.groupId,
        "studentName": req.studentName,
        "labName": req.labName,
        "issue": req.issue.strip(),
        "priority": req.priority,
        "status": "pending",
        "coachResponse": "",
        "createdAt": _now(),
    }
    tickets.append(ticket)
    _save("tickets.json", tickets)
    return ticket


@app.get("/api/coaches")
def list_coaches():
    """Tài khoản Lab Coach dùng để đăng nhập (demo, không mật khẩu)."""
    return _coaches()


# ---------------- seed/students.json — học viên tự khai blocker/định hướng ----------------

class LabEntryCreate(BaseModel):
    """Một lượt tự khai. Định danh bằng MSSV hoặc GitHub login, ít nhất một cái."""
    mssv: str = ""
    github: str = ""
    name: str = ""
    blockers: list[str] = []
    intentions: list[str] = []


def _students_file() -> Path:
    return SEED / "students.json"


def _load_students() -> list:
    f = _students_file()
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _save_students(items: list):
    with _io_lock:
        _students_file().write_text(json.dumps(items, ensure_ascii=False, indent=4),
                                    encoding="utf-8")


def _gh_login(url: str) -> str:
    """https://github.com/VanTienDL -> vantiendl (so khớp không phân biệt hoa thường)."""
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    tail = u.split("github.com", 1)[1].lstrip("/:") if "github.com" in u else u
    return tail.split("/")[0].lower()


def _next_lab_name(labs: list) -> str:
    """lab1, lab2 đã có -> lab3. Tên lạ thì bỏ qua khi tính số lớn nhất."""
    biggest = 0
    for e in labs or []:
        m = re.match(r"^lab\s*(\d+)$", str(e.get("name", "")).strip(), re.I)
        if m:
            biggest = max(biggest, int(m.group(1)))
    return f"lab{biggest + 1}"


@app.get("/api/students")
def list_students_seed():
    """Danh sách học viên trong seed — UI dùng để biết ai đã có hồ sơ."""
    return [{"id": s.get("id"), "name": s.get("name", ""), "mssv": str(s.get("MSSV", "")),
             "github": s.get("github", ""), "login": _gh_login(s.get("github", "")),
             "labs": [e.get("name") for e in (s.get("labs") or [])]}
            for s in _load_students()]


@app.post("/api/students/labs")
def add_student_lab(req: LabEntryCreate):
    """Thêm một lab mới (tên tăng dần) kèm blocker + định hướng học viên tự khai.

    repo_url để trống, report/group_report để rỗng — sẽ điền sau khi có bài nộp.
    Không tìm thấy học viên thì tạo hồ sơ mới với id kế tiếp.
    """
    blockers = [b.strip() for b in req.blockers if b and b.strip()]
    intentions = [i.strip() for i in req.intentions if i and i.strip()]
    if not blockers and not intentions:
        return JSONResponse(status_code=400,
                            content={"error": "Cần ít nhất 1 khó khăn hoặc 1 định hướng."})

    mssv = str(req.mssv or "").strip()
    login = _gh_login(req.github)
    if not mssv and not login:
        return JSONResponse(status_code=400,
                            content={"error": "Cần MSSV hoặc GitHub username để biết ghi cho ai."})

    students = _load_students()
    target = next((s for s in students
                   if (mssv and str(s.get("MSSV", "")).strip() == mssv)
                   or (login and _gh_login(s.get("github", "")) == login)), None)
    created = False
    if target is None:
        next_id = max([int(s.get("id", 0) or 0) for s in students], default=0) + 1
        target = {"id": next_id, "name": req.name or login or mssv, "MSSV": mssv,
                  "github": f"https://github.com/{req.github.strip()}" if login else "",
                  "labs": []}
        students.append(target)
        created = True

    entry = {
        "name": _next_lab_name(target.get("labs")),
        "repo_url": "",
        "report": [],
        "group_report": [],
        "blockers": blockers,
        "intentions": intentions,
    }
    target.setdefault("labs", []).append(entry)
    _save_students(students)
    return {"ok": True, "created": created, "student": {
        "id": target["id"], "name": target["name"], "mssv": target.get("MSSV", "")},
        "lab": entry}


@app.patch("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, req: TicketUpdate):
    """Chỉ Lab Coach có trong seed/labcoach.json mới đổi được ticket.

    Đóng ticket thì ghi lại ai đóng (resolvedBy) và lúc nào — mở lại thì xoá dấu vết đó.
    """
    coach = _find_coach(req.coachId)
    if coach is None:
        return JSONResponse(status_code=403, content={
            "error": f"coachId '{req.coachId}' không có trong seed/labcoach.json — "
                     f"chỉ Lab Coach mới cập nhật được ticket."})

    tickets = _load("tickets.json")
    for t in tickets:
        if t["id"] != ticket_id:
            continue
        if req.status in ("pending", "resolved"):
            t["status"] = req.status
            if req.status == "resolved":
                t["resolvedBy"] = coach["id"]
                t["resolvedByName"] = coach["name"]
                t["resolvedAt"] = _now()
            else:                       # mở lại -> không còn ai đứng tên đã xong
                t["resolvedBy"] = None
                t["resolvedByName"] = ""
                t["resolvedAt"] = ""
        if req.coachResponse is not None:
            t["coachResponse"] = req.coachResponse
            t["respondedBy"] = coach["id"]
            t["respondedByName"] = coach["name"]
            t["respondedAt"] = _now()
        _save("tickets.json", tickets)
        return t
    return JSONResponse(status_code=404, content={"error": "Không tìm thấy ticket."})


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return {"reply": chat_reply(req.message, req.state_summary, req.history)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ---------------- Skill graph (seed/.cache) ----------------

class CoverageRequest(BaseModel):
    mssv: list[str]
    lab: str


class TeamSuggestRequest(BaseModel):
    lab: str
    team_size: int = 5
    top_n: int = 5
    partition: bool = False        # True = chia cả cohort thành nhiều nhóm


def _graph_call(fn, *a, **kw):
    """Cache chưa dựng -> 409 kèm câu lệnh cần chạy; lỗi seed -> 400."""
    from src.graph_api import GraphNotBuilt
    from src.seed_loader import SeedError
    try:
        return fn(*a, **kw)
    except GraphNotBuilt as e:
        return JSONResponse(status_code=409, content={"error": str(e)})
    except SeedError as e:
        return JSONResponse(status_code=400, content={"error": f"Seed sai: {e}"})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/graph/labs")
def graph_labs():
    from src.graph_api import list_labs
    return _graph_call(list_labs)


@app.get("/api/graph/students")
def graph_students():
    from src.graph_api import list_students
    return _graph_call(list_students)


@app.get("/api/graph/students/{mssv}")
def graph_student(mssv: str):
    from src.graph_api import student_detail
    return _graph_call(student_detail, mssv)


@app.get("/api/graph/labs/{lab_name}")
def graph_lab(lab_name: str):
    from src.graph_api import load_lab
    return _graph_call(load_lab, lab_name)


@app.post("/api/graph/coverage")
def graph_coverage(req: CoverageRequest):
    """Nhập nhóm MSSV -> nhóm này phủ bao nhiêu % yêu cầu lab."""
    from src.graph_api import team_coverage
    return _graph_call(team_coverage, req.mssv, req.lab)


@app.post("/api/graph/suggest-teams")
def graph_suggest_teams(req: TeamSuggestRequest):
    """Duyệt tổ hợp cohort -> nhóm phủ tốt nhất cho lab."""
    from src.graph_api import suggest_teams
    return _graph_call(suggest_teams, req.lab, req.team_size, req.top_n, req.partition)
