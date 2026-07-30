"""Full analysis pipeline for the RoleFit AI web UI.

Input: setup form (project fields) + members list.
Output: one JSON payload the frontend renders (devs, project, tasks, labs,
fit matrix, default assignments). All GitHub numbers come from the REST API,
never from the LLM.
"""
import json
import re

from .github_fetcher import fetch_developer
from .llm import MODEL_FAST, MODEL_SMART, call_json
from .repo_fetcher import fetch_extra_files, fetch_repo_context
from .schemas import (GitHubData, RepoReadPlan, UIDevProfile, UIMatchResult,
                      UIProjectAnalysis)

HUES = [285, 175, 230, 40, 330, 130, 20, 260]

UI_DEV_SYSTEM = """Bạn là chuyên gia đánh giá năng lực lập trình viên để phân công vai trò trong team.

QUY TẮC CHỐNG BỊA (bắt buộc):
- Mỗi skill PHẢI có evidence trỏ về dữ liệu cụ thể được cung cấp: tên repo, thống kê ngôn ngữ GitHub,
  commit message — hoặc ghi 'self-reported' nếu chỉ do người đó tự khai.
- KHÔNG đưa vào skill không có trong dữ liệu.
- level (0-100): >=80 chỉ khi bằng chứng GitHub mạnh và nhất quán; skill self-reported đơn thuần tối đa 65.
- Nếu GitHub gần như trống, dựa vào tự khai nhưng level thận trọng và summary nói rõ thiếu dữ liệu.
- strengths, missing, learning_path, summary viết tiếng Việt; tên công nghệ giữ tiếng Anh.
- learning_path bám vào skill muốn học (wantLearn) và missing của chính người này."""

UI_PROJECT_SYSTEM = """Bạn là kỹ sư trưởng phân tích dự án phần mềm để lập danh sách đầu việc (Task Graph).

QUY TẮC:
- Chỉ kết luận từ dữ liệu được cung cấp (README, thư viện, cấu trúc source, backlog, roadmap). Không bịa công nghệ.
- Thông tin mỏng -> confidence="low" + clarifying_questions (câu hỏi cho chủ dự án), KHÔNG đoán im lặng.
- tasks: 4-8 đầu việc phủ vòng đời dự án, mô tả tiếng Việt, tên công nghệ tiếng Anh.
- required_skills PHẢI là tên công nghệ/tool CỤ THỂ xuất hiện trong repo (VD: Python, Streamlit, OpenAI API,
  Git, Markdown) — KHÔNG dùng danh mục chung chung kiểu "Frontend Development", "Testing", "Technical Writing".
  Mỗi task 1-3 skill, chỉ skill thật sự cần.
- Nếu được cung cấp danh sách "Kỹ năng nhóm đang có": khi một kỹ năng của nhóm dùng được cho task,
  hãy dùng ĐÚNG tên đó (giữ nguyên chính tả) để hệ thống so khớp được.
- summary: tóm tắt bài lab 2-4 câu tiếng Việt (đề bài yêu cầu gì, sản phẩm cuối là gì).
  objectives: 3-6 mục tiêu chính. Cả hai CHỈ lấy từ tài liệu được cung cấp — thiếu thì ghi ngắn và hạ confidence.
- estimate_days thực tế cho team học viên 3-5 người."""

REPO_DECIDE_SYSTEM = """Bạn là AI agent chuẩn bị dữ liệu để phân tích một dự án phần mềm.
Bạn được xem README và danh sách file trong repo. Nhiệm vụ: quyết định README (+ dependency files đã tự lấy)
đã đủ để hiểu dự án chưa. Nếu chưa đủ, chọn TỐI ĐA 6 file đáng đọc thêm — ưu tiên file .md tài liệu
(docs/, spec, lab, đề bài, hướng dẫn, kiến trúc), file cấu hình quan trọng. KHÔNG chọn file code dài,
ảnh, hay file khoá (lock). Chỉ chọn path có thật trong danh sách."""

UI_MATCH_SYSTEM = """Bạn là trưởng nhóm kỹ thuật phân công công việc.

MỤC TIÊU (theo thứ tự):
1. Tối đa fit giữa người và task dựa trên evidence trong hồ sơ.
2. Cân bằng workload — RÀNG BUỘC CỨNG:
   - Nếu số task >= số developer thì MỖI developer phải nhận ít nhất 1 task
     (trừ người có hồ sơ skill hoàn toàn rỗng — người đó nhận task dễ nhất kèm warning).
   - Không ai nhận quá ~40% tổng estimate_days. Thà giao task cho người fit thấp hơn một chút
     (kèm skills_to_learn) còn hơn dồn việc cho 1-2 người.
3. Nếu chênh fit nhỏ (<10 điểm), ưu tiên người có wantLearn khớp task và readiness cao — ghi skills_to_learn.

QUY TẮC:
- reason PHẢI trích dẫn evidence cụ thể từ hồ sơ (số commit, repo, ngôn ngữ, tự khai). Không bịa.
- fit_score: 90+ khớp hoàn toàn bằng chứng mạnh; 70-89 khớp phần lớn; 50-69 phải học thêm đáng kể;
  <50 không giao — đưa task vào unassigned_task_ids kèm warning.
- Dùng đúng task_id và developer_id được cung cấp.
- skill_coverage: BẮT BUỘC 1 dòng cho MỖI kỹ năng khác nhau trong required_skills của mọi task.
  So khớp NGỮ NGHĨA chứ không chỉ trùng tên: JavaScript/HTML/CSS che được việc dựng UI web;
  Python che được Streamlit ở mức "gần có"; Jupyter Notebook gợi ý quen data/eval.
  QUY TẮC CỨNG: thư viện/framework của một ngôn ngữ mà nhóm đã mạnh ngôn ngữ đó
  (VD: requests, PyYAML, Streamlit, OpenAI API với người mạnh Python; React với người mạnh JavaScript)
  thì status ÍT NHẤT là "gần có" — covered_by ghi người mạnh ngôn ngữ nền. "thiếu" chỉ dành cho
  kỹ năng không ai có nền tảng liên quan (VD: Kubernetes khi cả nhóm chỉ làm web frontend).
  - status "có": có người sở hữu đúng skill hoặc tương đương mạnh -> covered_by ghi tên + evidence.
  - status "gần có": có người có nền tảng liên quan, học nhanh được -> covered_by ghi tên + nền tảng, note gợi ý ai nên học.
  - status "thiếu": cả nhóm không có nền tảng liên quan -> note nói rõ rủi ro/cách xử lý.
- reason, warnings, workload_notes, note tiếng Việt; tên công nghệ tiếng Anh."""


def parse_name_from_repo(url: str) -> str:
    from .repo_fetcher import parse_repo_url
    p = parse_repo_url(url)
    return p[1] if p else ""


def _initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return "??"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def _time_label(days: float) -> str:
    if days >= 7:
        weeks = days / 7
        return f"{int(weeks)} tuần" if weeks == int(weeks) else f"{weeks:.1f} tuần"
    return f"{int(days)} ngày" if days == int(days) else f"{days} ngày"


DIFF_VI = {"low": "Thấp", "medium": "Trung bình", "high": "Cao"}


def _overlap_score(task: dict, dev: dict) -> int:
    names = {s.lower() for s in dev["skills"]}
    overlap = sum(1 for s in task["skills"] if s.lower() in names)
    return min(95, 50 + overlap * 15 + int(dev.get("readiness", 5)))


def _rebalance(devs: list[dict], tasks: list[dict], assignments: dict, fit_matrix: dict) -> list[str]:
    """Ensure every dev with a non-empty profile gets >=1 task when tasks >= devs."""
    notes: list[str] = []
    if len(tasks) < len(devs):
        return notes
    task_by_id = {t["id"]: t for t in tasks}
    counts = {d["id"]: 0 for d in devs}
    for did in assignments.values():
        if did in counts:
            counts[did] += 1
    for d in devs:
        if counts[d["id"]] > 0 or not d["skills"]:
            continue
        donor_id = max(counts, key=counts.get)
        if counts[donor_id] <= 1:
            continue
        donor_tasks = [tid for tid, did in assignments.items() if did == donor_id]
        best_tid = max(donor_tasks, key=lambda tid: _overlap_score(task_by_id[tid], d))
        donor_name = next(x["name"] for x in devs if x["id"] == donor_id)
        assignments[best_tid] = d["id"]
        counts[donor_id] -= 1
        counts[d["id"]] += 1
        score = _overlap_score(task_by_id[best_tid], d)
        fit_matrix.setdefault(best_tid, {})[d["id"]] = {
            "score": score,
            "reason": (f"Điều chỉnh tự động để cân bằng workload: chuyển từ {donor_name} "
                       f"(đang nhận nhiều việc nhất) sang {d['name']}. "
                       f"Fit ước tính theo độ trùng skill + readiness {d.get('readiness', 5)}/10."),
            "skillsToLearn": [s for s in task_by_id[best_tid]["skills"]
                              if s.lower() not in {k.lower() for k in d["skills"]}],
        }
        notes.append(f"Đã chuyển '{task_by_id[best_tid]['name']}' từ {donor_name} sang {d['name']} "
                     f"để ai cũng có việc (guardrail cân bằng).")
    return notes


def profile_developer(gh: GitHubData, self_reported: dict) -> UIDevProfile:
    """Flow 1 LLM step — same prompt the app uses; also called by eval."""
    payload = {"github_data": gh.model_dump(), "self_reported": self_reported}
    return call_json(
        MODEL_FAST, UI_DEV_SYSTEM,
        "Dữ liệu lập trình viên (GitHub thật + tự khai):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nXây dựng hồ sơ UIDevProfile.",
        UIDevProfile,
    )


def analyze_project_ui(proj_input: str) -> UIProjectAnalysis:
    """Flow 2 LLM step — same prompt the app uses; also called by eval."""
    return call_json(MODEL_FAST, UI_PROJECT_SYSTEM,
                     proj_input + "\n\nPhân tích và trả về UIProjectAnalysis.", UIProjectAnalysis)


def match_ui(match_payload: dict) -> UIMatchResult:
    """Flow 3 LLM step — same prompt the app uses; also called by eval."""
    return call_json(MODEL_SMART, UI_MATCH_SYSTEM,
                     "Dữ liệu team và task:\n" + json.dumps(match_payload, ensure_ascii=False)
                     + "\n\nPhân công và trả về UIMatchResult.", UIMatchResult, temperature=0.3)


def analyze_all(setup: dict, members: list[dict]) -> dict:
    """Run the 3 flows and assemble the UI payload. Raises on LLM/config errors."""
    # ---- Flow 1: per-member GitHub fetch + LLM profile ----
    devs = []
    gh_errors = []
    for i, m in enumerate(members):
        username = (m.get("github") or "").strip()
        gh = fetch_developer(username) if username else GitHubData(username="", error="Không nhập GitHub username")
        if gh.error:
            gh_errors.append(f"{m.get('name') or username}: {gh.error}")
        profile = profile_developer(gh, {
            "name": m.get("name", ""),
            "languages": m.get("languages", ""),
            "frameworks": m.get("frameworks", ""),
            "wants_to_learn": m.get("wantLearn", ""),
            "readiness_1_to_10": m.get("readiness", 5),
            "years_experience": m.get("experienceYears", 0),
        })
        name = m.get("name") or gh.display_name or username or f"Thành viên {i+1}"
        devs.append({
            "id": f"d{i+1}",
            "name": name,
            "initials": _initials(name),
            "github": username,
            "hue": HUES[i % len(HUES)],
            "roleSuited": profile.role_suited,
            "experienceYears": m.get("experienceYears", 0),
            "readiness": m.get("readiness", 5),
            "languages": m.get("languages") or ", ".join(list(gh.languages)[:4]),
            "frameworks": m.get("frameworks", ""),
            "wantLearn": m.get("wantLearn", ""),
            "githubStats": {"commits": gh.commit_count, "prs": gh.pr_count, "issues": gh.issue_count},
            "strengths": profile.strengths,
            "missing": profile.missing,
            "learningPath": profile.learning_path,
            "summary": profile.summary,
            "skills": {s.name: s.level for s in profile.skills},
            "skillEvidence": {s.name: s.evidence for s in profile.skills},
        })

    # ---- Flow 2: project analysis ----
    # Agent step: user gave only a repo URL -> read README + tree ourselves,
    # then let the LLM decide which extra docs it still needs.
    readme = (setup.get("readme") or "").strip()
    deps = (setup.get("deps") or "").strip()
    structure = (setup.get("structure") or "").strip()
    extra_docs = ""
    sources_read: list[str] = []
    repo_url = (setup.get("repoUrl") or "").strip()

    if repo_url and not readme:
        ctx = fetch_repo_context(repo_url)
        if ctx["error"]:
            gh_errors.append(f"Repo: {ctx['error']}")
        else:
            if ctx["readme"]:
                readme = ctx["readme"]
                sources_read.append("README.md")
            for path, content in ctx["dep_files"].items():
                deps += f"\n--- {path} ---\n{content}"
                sources_read.append(path)
            if not structure and ctx["tree"]:
                structure = "\n".join(ctx["tree"][:80])

            # candidates the agent may ask to read
            candidates = [p for p in ctx["tree"]
                          if p.lower().endswith((".md", ".rst", ".txt"))
                          and "license" not in p.lower() and p != "README.md"][:100]
            if candidates:
                plan = call_json(
                    MODEL_FAST, REPO_DECIDE_SYSTEM,
                    "=== README (rút gọn) ===\n" + readme[:4000]
                    + "\n\n=== Dependency files đã tự lấy ===\n" + (", ".join(ctx["dep_files"]) or "(không có)")
                    + "\n\n=== Danh sách file có thể đọc thêm ===\n" + "\n".join(candidates)
                    + "\n\nQuyết định theo RepoReadPlan.",
                    RepoReadPlan,
                )
                if not plan.enough and plan.files_to_read:
                    valid = [p for p in plan.files_to_read if p in candidates]
                    extra = fetch_extra_files(ctx["owner"], ctx["repo"], valid)
                    for path, content in extra.items():
                        extra_docs += f"\n\n=== File: {path} ===\n{content[:12000]}"
                        sources_read.append(path)

    proj_input = (
        "=== Tên dự án ===\n" + (setup.get("projectName") or "(chưa đặt tên)")
        + "\n=== GitHub repo ===\n" + (repo_url or "(không có)")
        + "\n=== README / tài liệu yêu cầu ===\n" + (readme or "(trống)")
        + "\n=== Thư viện ===\n" + (deps or "(không có)")
        + "\n=== Cấu trúc source ===\n" + (structure or "(không có)")
        + "\n=== Kiến trúc ===\n" + (setup.get("architecture") or "(không rõ)")
        + "\n=== Backlog ===\n" + (setup.get("backlog") or "(không có)")
        + "\n=== Roadmap ===\n" + (setup.get("roadmap") or "(không có)")
        + ("\n\n=== Tài liệu bổ sung AI tự đọc từ repo ===" + extra_docs if extra_docs else "")
    )
    team_skills = sorted({sk for d in devs for sk in d["skills"]})
    if team_skills:
        proj_input += "\n\n=== Kỹ năng nhóm đang có (dùng đúng tên này khi khớp) ===\n" + ", ".join(team_skills)
    proj = analyze_project_ui(proj_input)

    tasks = []
    labs = []
    for i, t in enumerate(proj.tasks):
        tid = f"t{i+1}"
        tasks.append({
            "id": tid, "name": t.name, "skills": t.required_skills,
            "difficulty": DIFF_VI[t.difficulty], "time": _time_label(t.estimate_days),
            "estimateDays": t.estimate_days, "labId": f"lab{i+1}",
        })
        labs.append({
            "id": f"lab{i+1}", "name": f"Lab {i+1} — {t.name}", "description": t.description,
            "requiredSkills": t.required_skills, "difficulty": DIFF_VI[t.difficulty],
            "time": _time_label(t.estimate_days),
        })

    backlog = [{"title": ln.strip(), "module": "Backlog"}
               for ln in (setup.get("backlog") or "").split("\n") if ln.strip()]
    roadmap = []
    for i, ln in enumerate([x.strip() for x in (setup.get("roadmap") or "").split("\n") if x.strip()]):
        m2 = re.match(r"^(sprint\s*\d+|phase\s*\d+|giai đoạn\s*\d+)\s*:?\s*(.*)$", ln, re.I)
        roadmap.append({"phase": m2.group(1).title() if m2 else f"Sprint {i+1}",
                        "goal": m2.group(2) if m2 else ln})

    project = {
        "name": setup.get("projectName") or (parse_name_from_repo(repo_url) if repo_url else "") or "Dự án chưa đặt tên",
        "description": readme[:180] or "—",
        "summary": proj.summary,
        "objectives": proj.objectives,
        "sourcesRead": sources_read,
        "type": proj.project_type, "scale": proj.scale,
        "architecture": setup.get("architecture") or "—",
        "techStack": proj.tech_stack, "modules": proj.modules,
        "backlog": backlog, "roadmap": roadmap,
        "confidence": proj.confidence, "clarifyingQuestions": proj.clarifying_questions,
    }

    # ---- Flow 3: matching ----
    match_payload = {
        "developers": [{
            "id": d["id"], "name": d["name"], "roleSuited": d["roleSuited"],
            "experienceYears": d["experienceYears"], "readiness": d["readiness"],
            "wantLearn": d["wantLearn"], "skills": d["skills"],
            "skillEvidence": d["skillEvidence"], "githubStats": d["githubStats"],
            "strengths": d["strengths"],
        } for d in devs],
        "tasks": [{"id": t["id"], "name": t["name"], "required_skills": t["skills"],
                   "difficulty": t["difficulty"], "estimate_days": t["estimateDays"]} for t in tasks],
    }
    mr = match_ui(match_payload)

    valid_dev = {d["id"] for d in devs}
    valid_task = {t["id"] for t in tasks}
    fit_matrix: dict = {}
    assignments = {t["id"]: None for t in tasks}
    for a in mr.assignments:
        if a.task_id in valid_task and a.developer_id in valid_dev:
            fit_matrix.setdefault(a.task_id, {})[a.developer_id] = {
                "score": a.fit_score, "reason": a.reason, "skillsToLearn": a.skills_to_learn,
            }
            assignments[a.task_id] = a.developer_id

    # Deterministic guardrail — the LLM sometimes ignores the balance constraint:
    # if there are at least as many tasks as devs, every dev (with a non-empty
    # profile) must end up with >=1 task. Move the best-overlapping task from
    # the most loaded dev.
    rebalance_notes = _rebalance(devs, tasks, assignments, fit_matrix)

    return {
        "devs": devs, "project": project, "tasks": tasks, "labs": labs,
        "fitMatrix": fit_matrix, "assignments": assignments,
        "warnings": mr.warnings + gh_errors + rebalance_notes,
        "workloadNotes": mr.workload_notes,
        "unassignedTaskIds": [t for t in mr.unassigned_task_ids if t in valid_task],
        "skillCoverage": [c.model_dump() for c in mr.skill_coverage],
    }


def chat_reply(message: str, state_summary: str) -> str:
    """Grounded chat about the current assignment state."""
    from .llm import client
    resp = client().chat.completions.create(
        model=MODEL_FAST,
        temperature=0.3,
        max_tokens=300,
        messages=[
            {"role": "system", "content":
                "Bạn là trợ lý AI trong app phân công vai trò team (RoleFit AI). "
                "Trả lời NGẮN GỌN (tối đa 3-4 câu) bằng tiếng Việt, CHỈ dựa trên dữ liệu trạng thái được cung cấp. "
                "Không biết thì nói không có dữ liệu — không đoán. "
                "Không xếp hạng 'ai giỏi hơn ai' — chỉ nói về mức phù hợp người-việc.\n\n"
                "=== Trạng thái hiện tại ===\n" + state_summary},
            {"role": "user", "content": message},
        ],
    )
    return resp.choices[0].message.content or "Xin lỗi, mình chưa trả lời được."
