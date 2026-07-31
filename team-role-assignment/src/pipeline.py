"""Full analysis pipeline for the RoleFit AI web UI.

Input: setup form (project fields) + members list.
Output: one JSON payload the frontend renders (devs, project, tasks, labs,
fit matrix, default assignments). All GitHub numbers come from the REST API,
never from the LLM.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from .github_fetcher import fetch_developer
from .llm import MODEL_FAST, MODEL_SMART, call_json
from .repo_fetcher import fetch_extra_files, fetch_repo_context
from .schemas import (GitHubData, RepoReadPlan, UIDevProfile, UIMatchResult,
                      UIProjectAnalysis, UISkill)
from .skills import canon, canon_list, catalog, label, menu_for_prompt

HUES = [285, 175, 230, 40, 330, 130, 20, 260]
MAX_MEMBER_WORKERS = 6      # số thành viên phân tích song song

UI_DEV_SYSTEM = """Bạn là chuyên gia đánh giá năng lực lập trình viên để phân công vai trò trong team.

QUY TẮC CHỐNG BỊA (bắt buộc):
- Mỗi skill PHẢI có evidence trỏ về dữ liệu cụ thể được cung cấp: tên repo, thống kê ngôn ngữ GitHub,
  commit message — hoặc ghi 'self-reported' nếu chỉ do người đó tự khai.
- KHÔNG đưa vào skill không có trong dữ liệu.
- skills[].name PHẢI là id lấy ĐÚNG trong "Danh mục kỹ năng chuẩn" bên dưới, không đặt tên mới.
  Công nghệ cụ thể (React, FastAPI, Next.js...) quy về trục tương ứng và nhắc tên đó trong evidence.
- CHỈ chọn một trục khi dữ liệu nêu ĐÍCH DANH ngôn ngữ/thư viện/việc thuộc trục đó.
  Suy diễn bắc cầu là BỊA và bị cấm: biết Python KHÔNG suy ra backend-api hay data-handling;
  có repo web KHÔNG suy ra database; commit nhiều KHÔNG suy ra debugging.
- Công nghệ tự khai KHÔNG có trục tương ứng (VD: Java, Unity, Rust) thì GIỮ NGUYÊN tên gốc làm name
  và ghi evidence 'self-reported' — không được bỏ đi, cũng không được ép sang trục gần đúng.
- level (0-100): >=80 chỉ khi bằng chứng GitHub mạnh và nhất quán; skill self-reported đơn thuần tối đa 65.
- Nếu GitHub gần như trống, dựa vào tự khai nhưng level thận trọng và summary nói rõ thiếu dữ liệu.
- strengths, missing, learning_path, summary viết tiếng Việt; tên công nghệ giữ tiếng Anh.
- learning_path bám vào skill muốn học (wantLearn) và missing của chính người này."""

UI_PROJECT_SYSTEM = """Bạn là kỹ sư trưởng phân tích dự án phần mềm để lập danh sách đầu việc (Task Graph).

QUY TẮC:
- Chỉ kết luận từ dữ liệu được cung cấp (README, thư viện, cấu trúc source, backlog, roadmap). Không bịa công nghệ.
- Thông tin mỏng -> confidence="low" + clarifying_questions (câu hỏi cho chủ dự án), KHÔNG đoán im lặng.
- tasks: 4-8 đầu việc phủ vòng đời dự án, mô tả tiếng Việt, tên công nghệ tiếng Anh.
- required_skills PHẢI là id lấy ĐÚNG trong "Danh mục kỹ năng chuẩn" được cung cấp (VD: python, backend-api,
  api-integration). TUYỆT ĐỐI không đặt tên mới, không viết tên framework (Next.js, Streamlit) vào đây —
  framework thì chọn trục tương ứng (Next.js -> ui-frontend, FastAPI -> backend-api).
  Mỗi task 1-3 id, chỉ kỹ năng thật sự cần. Công nghệ cụ thể của repo thì nhắc trong description.
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
4. Nếu payload có "volunteers": nhóm ĐÃ CHỐT ai nhận học kỹ năng còn thiếu. Task cần kỹ năng đó
   phải giao cho đúng người ấy (trừ khi làm họ vượt trần khối lượng), fit_score chấm theo năng lực
   thật chứ không cộng điểm ảo, reason nói rõ "nhóm phân công người này học <kỹ năng>",
   và liệt kê kỹ năng đó trong skills_to_learn.

QUY TẮC:
- reason PHẢI trích dẫn evidence cụ thể từ hồ sơ (số commit, repo, ngôn ngữ, tự khai). Không bịa.
- fit_score: 90+ khớp hoàn toàn bằng chứng mạnh; 70-89 khớp phần lớn; 50-69 phải học thêm đáng kể;
  <50 không giao — đưa task vào unassigned_task_ids kèm warning.
- Dùng đúng task_id và developer_id được cung cấp.
- skill_coverage: BẮT BUỘC 1 dòng cho MỖI kỹ năng khác nhau trong required_skills của mọi task.
  Trường "skill" ghi ĐÚNG id đã cho, không đổi tên.
  Mỗi developer có "skillAxes" = mức thành thạo trên chính các trục đó — dùng nó để chấm.
  QUY TẮC CỨNG: trục nền tảng gần kề đã mạnh thì status ÍT NHẤT là "gần có"
  (python mạnh -> backend-api / data-handling / llm-app-dev gần có; ui-frontend mạnh -> presentation-demo;
  api-integration mạnh -> llm-app-dev). "thiếu" chỉ dành cho trục không ai có nền tảng liên quan.
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


WORKLOAD_CAP = 0.50     # không ai giữ quá 50% tổng ngày công — chốt bằng code, không nhờ prompt


def _cap_workload(devs: list[dict], tasks: list[dict], assignments: dict,
                  fit_matrix: dict, cap: float = WORKLOAD_CAP) -> list[str]:
    """Chuyển việc khỏi người đang gánh quá `cap` cho tới khi không ai vượt trần.

    Prompt đã yêu cầu cân bằng nhưng LLM vẫn vượt (case M03 trong eval), nên chặn
    ở tầng code. Mỗi lần chuyển chọn việc mà người nhận hợp nhất trong số việc của
    người đang quá tải, và chỉ chuyển khi thực sự làm giảm mức lệch.
    """
    notes: list[str] = []
    task_by_id = {t["id"]: t for t in tasks}
    days = {t["id"]: (t.get("estimateDays") or 0) for t in tasks}
    total = sum(days.get(tid, 0) for tid, did in assignments.items() if did)
    if total <= 0 or len(devs) < 2:
        return notes

    def load_of(did: str) -> float:
        return sum(days.get(tid, 0) for tid, d in assignments.items() if d == did)

    for _ in range(len(tasks) * 2):                 # trần vòng lặp: không kẹt vô hạn
        loads = {d["id"]: load_of(d["id"]) for d in devs}
        over_id = max(loads, key=loads.get)
        if loads[over_id] / total <= cap:
            break
        movable = [tid for tid, did in assignments.items() if did == over_id]
        if len(movable) <= 1:                       # còn đúng 1 việc thì không lấy nốt
            break
        receiver = min((d for d in devs if d["id"] != over_id),
                       key=lambda d: loads[d["id"]])
        rid = receiver["id"]
        # Chỉ nhận nước đi làm GIẢM mức gánh nặng nhất. Việc chia theo ngày công là
        # số nguyên lát, nhiều khi không tồn tại cách chia nào dưới trần (2 người,
        # việc to) — khi đó vẫn đi tới thế cân nhất có thể rồi cảnh báo.
        cand = []
        for tid in movable:
            new_max = max(loads[over_id] - days.get(tid, 0), loads[rid] + days.get(tid, 0),
                          *[loads[d["id"]] for d in devs if d["id"] not in (over_id, rid)] or [0])
            if new_max < loads[over_id] - 1e-9:
                cand.append((new_max, -_overlap_score(task_by_id[tid], receiver),
                             days.get(tid, 0), tid))
        if not cand:
            break
        cand.sort()
        pick = cand[0][3]
        over_name = next(x["name"] for x in devs if x["id"] == over_id)
        assignments[pick] = receiver["id"]
        score = _overlap_score(task_by_id[pick], receiver)
        fit_matrix.setdefault(pick, {})[receiver["id"]] = {
            "score": score,
            "reason": (f"Guardrail trần khối lượng {int(cap*100)}%: {over_name} đang giữ "
                       f"{loads[over_id]/total:.0%} tổng ngày công nên chuyển việc này sang "
                       f"{receiver['name']}. Fit ước tính theo độ trùng kỹ năng + readiness "
                       f"{receiver.get('readiness', 5)}/10 — nhóm nên xem lại trước khi chốt."),
            "skillsToLearn": [s for s in task_by_id[pick]["skills"]
                              if s not in (receiver.get("skills") or {})],
        }
        notes.append(f"Đã chuyển '{task_by_id[pick]['name']}' từ {over_name} sang "
                     f"{receiver['name']} vì {over_name} vượt trần {int(cap*100)}% khối lượng.")

    final = {d["id"]: load_of(d["id"]) for d in devs}
    worst_id = max(final, key=final.get)
    worst = final[worst_id] / total
    if worst > cap:
        worst_name = next(x["name"] for x in devs if x["id"] == worst_id)
        notes.append(f"Không chia được dưới trần {int(cap*100)}%: {worst_name} vẫn giữ "
                     f"{worst:.0%} khối lượng vì nhóm chỉ có {len(devs)} người và các đầu việc "
                     f"chia không đều được. Nhóm nên tách nhỏ đầu việc lớn hoặc bàn lại phạm vi.")
    return notes


FIT_OK_LEVEL = 40       # dưới mức này coi như chưa làm được việc thật trên trục đó


def _calibrate_fit(devs: list[dict], tasks: list[dict], assignments: dict,
                   fit_matrix: dict) -> tuple[list[str], list[str]]:
    """Hạ Fit Score xuống mức bằng chứng cho phép.

    Đo trên dữ liệu thật: LLM gần như không bao giờ chấm dưới 50 và hay cho 70-90
    cho những cặp mà người nhận có mức 0 trên MỌI kỹ năng việc đó cần (vd giao việc
    viết tài liệu cho người không có trục documentation vẫn 70). Điểm cao trông rất
    đáng tin nên không ai tự phát hiện — phải chặn bằng luật rõ ràng:

        không có trục nào    -> trần 45   (phải học từ đầu)
        có nhưng đều < 40    -> trần 60
        đủ mạnh một phần     -> trần 75
        đủ mạnh mọi trục     -> trần 95

    Trả về (ghi chú, danh sách task rủi ro). Không gỡ việc khỏi người nhận: bài lab
    vẫn phải có người làm — nhưng phải nói thẳng đây là việc phải học từ đầu.
    """
    notes: list[str] = []
    at_risk: list[str] = []
    dev_by = {d["id"]: d for d in devs}
    for t in tasks:
        did = assignments.get(t["id"])
        dev = dev_by.get(did) if did else None
        entry = (fit_matrix.get(t["id"]) or {}).get(did) if dev else None
        if not entry or not isinstance(entry.get("score"), int):
            continue
        req = list(t.get("skills") or [])
        levels = {s: (dev.get("skills") or {}).get(s, 0) for s in req}
        vals = list(levels.values()) or [0]
        best = max(vals)
        covered = sum(1 for v in vals if v >= FIT_OK_LEVEL)
        if best == 0:
            ceiling = 45
        elif best < FIT_OK_LEVEL:
            ceiling = 60
        elif req and covered == len(req):
            ceiling = 95
        else:
            ceiling = 75
        entry["evidenceLevels"] = levels          # UI/coach đối chiếu được ngay
        old = entry["score"]
        if old > ceiling:
            entry["score"] = ceiling
            entry["aiScore"] = old
            entry["reason"] = (entry.get("reason", "")
                               + f" [Hệ thống hạ Fit {old}→{ceiling}: mức thật của {dev['name']} "
                                 f"trên kỹ năng việc này cần là "
                               + ", ".join(f"{label(s)} {v}" for s, v in levels.items()) + ".]")
        if entry["score"] < 50:
            at_risk.append(t["id"])
            missing = [label(s) for s, v in levels.items() if v < FIT_OK_LEVEL]
            notes.append(f"'{t['name']}' giao cho {dev['name']} nhưng chưa có bằng chứng năng lực "
                         f"({', '.join(missing) or 'không trục nào'}) — cần học từ đầu hoặc nhờ Lab Coach.")
    return notes, at_risk


def profile_developer(gh: GitHubData, self_reported: dict) -> UIDevProfile:
    """Flow 1 LLM step — same prompt the app uses; also called by eval."""
    payload = {"github_data": gh.model_dump(), "self_reported": self_reported}
    prof = call_json(
        MODEL_FAST, UI_DEV_SYSTEM,
        "=== Danh mục kỹ năng chuẩn (name chỉ được lấy id ở đây) ===\n" + menu_for_prompt()
        + "\n\nDữ liệu lập trình viên (GitHub thật + tự khai):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nXây dựng hồ sơ UIDevProfile.",
        UIDevProfile,
    )
    # LLM đôi khi vẫn trả 'Next.js' thay vì id -> quy về trục chuẩn ngay tại đây,
    # gộp trùng bằng cách giữ mức cao nhất và nối evidence.
    merged: dict[str, tuple[int, str]] = {}
    for s in prof.skills:
        sid = canon(s.name) or s.name.strip()
        old = merged.get(sid)
        if old is None:
            merged[sid] = (s.level, s.evidence)
        else:
            ev = old[1] if s.evidence in old[1] else f"{old[1]}; {s.evidence}"
            merged[sid] = (max(old[0], s.level), ev)
    prof.skills = [UISkill(name=sid, level=lv, evidence=ev)
                   for sid, (lv, ev) in merged.items()]

    # Guardrail: người dùng tự khai gì thì phải còn nguyên trong hồ sơ. Model hay
    # bỏ rơi kỹ năng không có trục tương ứng (VD 'Java'). Ghi vào là trung thực —
    # đây là lời khai của chính họ, và evidence nói rõ chỉ là tự khai.
    for raw in (self_reported.get("declared_skill_axes") or []):
        sid = canon(raw) or str(raw).strip()
        if sid and sid not in merged:
            merged[sid] = (45, "self-reported (người dùng tự khai, chưa có dữ liệu GitHub)")
            prof.skills.append(UISkill(name=sid, level=45, evidence=merged[sid][1]))
    return prof


def analyze_project_ui(proj_input: str) -> UIProjectAnalysis:
    """Flow 2 LLM step — same prompt the app uses; also called by eval."""
    return call_json(MODEL_FAST, UI_PROJECT_SYSTEM,
                     proj_input + "\n\nPhân tích và trả về UIProjectAnalysis.", UIProjectAnalysis)


def match_ui(match_payload: dict) -> UIMatchResult:
    """Flow 3 LLM step — same prompt the app uses; also called by eval."""
    # skill_coverage bắt 1 dòng mỗi skill nên output phình theo số task -> chặn trần.
    return call_json(MODEL_SMART, UI_MATCH_SYSTEM,
                     "Dữ liệu team và task:\n" + json.dumps(match_payload, ensure_ascii=False)
                     + "\n\nPhân công và trả về UIMatchResult.", UIMatchResult,
                     temperature=0.3, max_tokens=2000)


def analyze_prepare(setup: dict, members: list[dict]) -> dict:
    """Luồng 1 + 2: hồ sơ thành viên và Task Graph. CHƯA phân công.

    Tách ra để trước khi tốn lượt matching, người dùng còn nhìn được "kỹ năng nào
    cả nhóm chưa ai có" và chỉ định ai sẽ nhận học — thông tin đó đưa vào Luồng 3.
    """
    # ---- Flow 1: per-member GitHub fetch + LLM profile ----
    # Các thành viên độc lập nhau -> chạy song song. Tuần tự thì thời gian cộng dồn
    # theo số người (đo được ~12.5s/người); song song thì bằng người chậm nhất.
    def _one_member(i: int, m: dict) -> tuple[dict, str]:
        username = (m.get("github") or "").strip()
        gh = fetch_developer(username) if username else GitHubData(
            username="", error="Không nhập GitHub username")
        err = f"{m.get('name') or username}: {gh.error}" if gh.error else ""
        # Người dùng chọn kỹ năng bằng tag (id chuẩn) thay vì gõ tay; ô "khác"
        # vẫn nhận chữ tự do nên vẫn canon lại phòng khi họ gõ 'NextJS'.
        declared = canon_list(m.get("skillIds") or [])
        wants = canon_list(m.get("wantLearnIds") or [])
        profile = profile_developer(gh, {
            "name": m.get("name", ""),
            "declared_skill_axes": declared,
            "declared_skill_labels": [label(s) for s in declared],
            "wants_to_learn_axes": wants,
            "wants_to_learn_labels": [label(s) for s in wants],
            "other_tech_free_text": ", ".join(
                x for x in [m.get("languages", ""), m.get("frameworks", "")] if x),
            "readiness_1_to_10": m.get("readiness", 5),
            "years_experience": m.get("experienceYears", 0),
        })
        name = m.get("name") or gh.display_name or username or f"Thành viên {i+1}"
        return {
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
            "declaredSkills": declared,
            "wantLearnIds": wants,
            "wantLearn": ", ".join(label(s) for s in wants) or m.get("wantLearn", ""),
            "githubStats": {"commits": gh.commit_count, "prs": gh.pr_count,
                            "issues": gh.issue_count},
            "strengths": profile.strengths,
            "missing": profile.missing,
            "learningPath": profile.learning_path,
            "summary": profile.summary,
            "skills": {s.name: s.level for s in profile.skills},
            "skillEvidence": {s.name: s.evidence for s in profile.skills},
        }, err

    with ThreadPoolExecutor(max_workers=min(MAX_MEMBER_WORKERS, len(members))) as pool:
        results = list(pool.map(lambda a: _one_member(*a), enumerate(members)))
    devs = [r[0] for r in results]           # giữ đúng thứ tự người dùng nhập
    gh_errors = [r[1] for r in results if r[1]]

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
    proj_input += ("\n\n=== Danh mục kỹ năng chuẩn (required_skills chỉ được lấy id ở đây) ===\n"
                   + menu_for_prompt())
    team_axes = sorted({sk for d in devs for sk in d["skills"]})
    if team_axes:
        proj_input += "\n\n=== Trục kỹ năng nhóm đang có ===\n" + ", ".join(team_axes)
    proj = analyze_project_ui(proj_input)

    tasks = []
    labs = []
    for i, t in enumerate(proj.tasks):
        tid = f"t{i+1}"
        # Quy về trục chuẩn: 'Next.js' và 'NextJS' cùng ra 'ui-frontend' nên
        # bảng coverage và sơ đồ kỹ năng không còn báo thiếu vì lệch chính tả.
        t.required_skills = canon_list(t.required_skills)
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

    return {"devs": devs, "project": project, "tasks": tasks, "labs": labs,
            "ghErrors": gh_errors, "skillGaps": skill_gaps(devs, tasks),
            "skillCatalog": {sid: meta["label"] for sid, meta in catalog().items()}}


GAP_LEVEL = 40          # dưới mức này coi như chưa làm được việc thật
WEAK_LEVEL = 60         # 40-59: làm được nhưng phải học thêm


def skill_gaps(devs: list[dict], tasks: list[dict]) -> list[dict]:
    """Kỹ năng bài lab đòi mà cả nhóm còn yếu/chưa có. Thuần code, không gọi LLM."""
    need: dict[str, int] = {}
    for t in tasks:
        for s in t.get("skills") or []:
            need[s] = need.get(s, 0) + 1
    out = []
    for sid, count in need.items():
        levels = {d["id"]: (d["skills"] or {}).get(sid, 0) for d in devs}
        best_id = max(levels, key=levels.get) if levels else None
        best = levels.get(best_id, 0) if best_id else 0
        if best >= WEAK_LEVEL:
            continue
        # ai muốn học đúng trục này thì gợi ý sẵn — không tự quyết thay người dùng
        volunteers = [d["id"] for d in devs if sid in (d.get("wantLearnIds") or [])]
        out.append({
            "skill": sid, "label": label(sid), "taskCount": count,
            "best": best, "bestDevId": best_id if best > 0 else None,
            "status": "thiếu" if best < GAP_LEVEL else "yếu",
            "suggested": volunteers,
            "taskNames": [t["name"] for t in tasks if sid in (t.get("skills") or [])],
        })
    out.sort(key=lambda g: (g["best"], -g["taskCount"]))
    return out


def analyze_match(draft: dict, volunteers: dict | None = None) -> dict:
    """Luồng 3: phân công + guardrail. draft là kết quả analyze_prepare().

    volunteers: {skill_id: developer_id} — người dùng đã chỉ định ai nhận học kỹ năng
    nhóm còn thiếu. Đây là quyết định của con người, AI chỉ tôn trọng nó khi ghép.
    """
    devs, tasks = draft["devs"], draft["tasks"]
    gh_errors = list(draft.get("ghErrors") or [])
    valid_dev = {d["id"] for d in devs}
    vol = {k: v for k, v in (volunteers or {}).items() if v in valid_dev}

    match_payload = {
        "developers": [{
            "id": d["id"], "name": d["name"], "roleSuited": d["roleSuited"],
            "experienceYears": d["experienceYears"], "readiness": d["readiness"],
            "wantLearn": d["wantLearn"], "skillAxes": d["skills"],
            "skillEvidence": d["skillEvidence"], "githubStats": d["githubStats"],
            "strengths": d["strengths"],
        } for d in devs],
        "tasks": [{"id": t["id"], "name": t["name"], "required_skills": t["skills"],
                   "difficulty": t["difficulty"], "estimate_days": t["estimateDays"]} for t in tasks],
    }
    if vol:
        match_payload["volunteers"] = [
            {"skill": sid, "developer_id": did,
             "note": "Nhóm đã chốt người này nhận học kỹ năng đang thiếu"}
            for sid, did in vol.items()]
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
    cap_notes = _cap_workload(devs, tasks, assignments, fit_matrix)
    # Hiệu chỉnh SAU CÙNG: guardrail phía trên có thể đổi người nhận việc.
    risk_notes, at_risk = _calibrate_fit(devs, tasks, assignments, fit_matrix)

    coverage_rows = []
    for c in mr.skill_coverage:
        row = c.model_dump()
        row["skill"] = canon(row["skill"]) or row["skill"]
        coverage_rows.append(row)

    return {
        "devs": devs, "project": draft["project"], "tasks": tasks, "labs": draft["labs"],
        "fitMatrix": fit_matrix, "assignments": assignments,
        "warnings": mr.warnings + gh_errors + rebalance_notes + cap_notes + risk_notes,
        "workloadNotes": mr.workload_notes,
        "unassignedTaskIds": [t for t in mr.unassigned_task_ids if t in valid_task],
        "atRiskTaskIds": at_risk,
        "skillCoverage": coverage_rows,
        "skillGaps": draft.get("skillGaps", []),
        "volunteers": vol,
        # Nhãn tiếng Việt cho từng trục — UI hiển thị label, dữ liệu vẫn là id.
        "skillCatalog": {sid: meta["label"] for sid, meta in catalog().items()},
    }


def analyze_all(setup: dict, members: list[dict], volunteers: dict | None = None) -> dict:
    """Chạy cả 3 luồng một lượt (giữ cho các chỗ gọi cũ và test)."""
    return analyze_match(analyze_prepare(setup, members), volunteers)


MAX_CHAT_TURNS = 8      # 8 lượt gần nhất là đủ để hiểu "còn người đó thì sao?" mà prompt không phình


def chat_reply(message: str, state_summary: str, history: list[dict] | None = None) -> str:
    """Grounded chat about the current assignment state.

    history: [{"role": "user"|"assistant", "content": str}] — các lượt TRƯỚC câu hỏi này.
    Không có history thì mỗi câu hỏi là một cuộc hội thoại rời rạc: hỏi "còn Tâm thì sao?"
    ngay sau đó model không biết "còn" là còn gì.
    """
    from .llm import client
    turns = []
    for h in (history or [])[-MAX_CHAT_TURNS * 2:]:
        role = "assistant" if h.get("role") in ("assistant", "ai") else "user"
        content = str(h.get("content") or "").strip()[:1500]
        if content:
            turns.append({"role": role, "content": content})
    resp = client().chat.completions.create(
        model=MODEL_FAST,
        temperature=0.3,
        max_tokens=300,
        messages=[
            {"role": "system", "content":
                "Bạn là trợ lý AI trong app phân công vai trò team (RoleFit AI). "
                "Trả lời NGẮN GỌN (tối đa 3-4 câu) bằng tiếng Việt, CHỈ dựa trên dữ liệu trạng thái được cung cấp. "
                "Không biết thì nói không có dữ liệu — không đoán. "
                "Không xếp hạng 'ai giỏi hơn ai' — chỉ nói về mức phù hợp người-việc. "
                "Có lịch sử hội thoại thì hiểu câu hỏi nối tiếp (đại từ 'người đó', 'việc đó'), "
                "nhưng dữ kiện vẫn phải lấy từ trạng thái bên dưới, không lấy từ câu mình đã nói trước.\n\n"
                "=== Trạng thái hiện tại ===\n" + state_summary},
            *turns,
            {"role": "user", "content": message},
        ],
    )
    return resp.choices[0].message.content or "Xin lỗi, mình chưa trả lời được."
