"""Rút signal bằng LLM: bằng chứng thô -> đề xuất kỹ năng.

LLM chỉ ĐỀ XUẤT. Trần điểm, phạt blocker và loại skill ngoài registry do
src/vectors.py quyết định bằng code — cùng tinh thần guardrail `_rebalance`.
"""
import json

from .llm import MODEL_FAST, call_json
from .schemas import LabRequirements, StudentLabSignals
from .vectors import apply_evidence_caps, clamp

STUDENT_SYSTEM = """Bạn chấm kỹ năng một học viên thể hiện trong MỘT bài lab.

QUY TẮC CỨNG:
- skill PHẢI là id trong DANH SÁCH TRỤC được cung cấp. Không có id phù hợp thì BỎ QUA,
  tuyệt đối không đặt tên mới.
- Chỉ đưa kỹ năng CÓ bằng chứng trong dữ liệu lab này. Không suy diễn từ tên repo hay tên lab.
- evidence_type chọn nguồn MẠNH NHẤT chứng minh: commit > report > group_report > none.
- evidence trích ngắn đúng chỗ chứng minh (câu trong report, hoặc commit message).
- strength là mức thể hiện TRONG LAB NÀY, không phải năng lực tổng của người đó.
- blocked_skills: skill id mà mục "khó khăn" cho thấy còn vướng.
- interest_skills: skill id mà mục "định hướng" cho thấy muốn học — KHÔNG đưa vào signals.
- Không có bằng chứng gì thì trả signals rỗng. Rỗng là kết quả hợp lệ."""

LAB_SYSTEM = """Bạn đọc tài liệu đề bài một lab và liệt kê kỹ năng lab đó thực sự đòi hỏi.

QUY TẮC CỨNG:
- skill PHẢI là id trong DANH SÁCH TRỤC được cung cấp. Không có id phù hợp thì BỎ QUA,
  không đặt tên mới.
- Chỉ lấy từ tài liệu được cung cấp. Không đoán theo tên lab.
- weight: 1.0 = lab dạy hoặc bắt buộc dùng; 0.6 = cần nhưng phụ; 0.3 = chỉ chạm qua.
- reason trích ngắn từ tài liệu.
- Tài liệu mỏng -> confidence="low" và chỉ liệt kê kỹ năng chắc chắn."""


def skill_menu(skills: dict[str, dict]) -> str:
    return "\n".join(f"- {sid}: {m['label']} — {m.get('description', '')}"
                     for sid, m in skills.items())


def student_lab_gain(raw: dict, skills: dict[str, dict]) -> dict:
    """raw (crawl.crawl_student_lab) -> gain đã áp trần cho 1 (học viên, lab)."""
    commits = raw.get("commits", {})
    payload = {
        "ho_ten": raw["name"],
        "lab": raw["lab"],
        "repo_lab": raw["repo_url"] or "(không có)",
        "repo_doc_duoc": raw.get("repo_ok", False),
        "so_commit_cua_nguoi_nay": commits.get("count", 0),
        "cach_dem_commit": commits.get("attribution", "none"),
        "commit_messages": commits.get("messages", [])[:30],
        "ngon_ngu_repo": raw.get("languages", {}),
        "bao_cao_ca_nhan": [r["text"][:6000] for r in raw.get("reports", []) if r.get("ok")],
        "bao_cao_nhom": [r["text"][:6000] for r in raw.get("group_reports", []) if r.get("ok")],
        "kho_khan": raw.get("blockers", []),
        "dinh_huong": raw.get("intentions", []),
    }
    res = call_json(
        MODEL_FAST, STUDENT_SYSTEM,
        "=== DANH SÁCH TRỤC (chỉ được chọn trong đây) ===\n" + skill_menu(skills)
        + "\n\n=== DỮ LIỆU LAB CỦA HỌC VIÊN ===\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nTrả về StudentLabSignals.",
        StudentLabSignals,
    )

    blocked = {s for s in res.blocked_skills if s in skills}
    gains, evidence, dropped = apply_evidence_caps(
        [s.model_dump() for s in res.signals], skills, blocked,
        weak_attribution=commits.get("attribution") == "all-commits",
    )
    return {
        "lab": raw["lab"], "mssv": raw["mssv"], "name": raw["name"],
        "gains": gains, "evidence": evidence,
        "blocked": sorted(blocked),
        "interests": sorted({s for s in res.interest_skills if s in skills}),
        "summary": res.summary,
        "dropped_skills": dropped,
        "attribution": commits.get("attribution", "none"),
    }


def lab_declared(raw_lab: dict, skills: dict[str, dict]) -> dict:
    """Tài liệu đề bài -> {skill: weight} do lab tự khai."""
    docs = [d for d in raw_lab.get("docs", []) if d.get("ok")]
    if not docs:
        return {"weights": {}, "summary": "Không đọc được tài liệu đề bài.",
                "confidence": "low", "reasons": {}, "dropped_skills": [], "doc_count": 0}
    body = "\n\n".join(f"=== {d['source']} ===\n{d['text'][:12000]}" for d in docs)
    res = call_json(
        MODEL_FAST, LAB_SYSTEM,
        "=== DANH SÁCH TRỤC (chỉ được chọn trong đây) ===\n" + skill_menu(skills)
        + f"\n\n=== TÀI LIỆU LAB {raw_lab['lab']} ===\n" + body
        + "\n\nTrả về LabRequirements.",
        LabRequirements,
    )
    weights, reasons, dropped = {}, {}, []
    for r in res.requirements:
        if r.skill not in skills:
            dropped.append(r.skill)
            continue
        w = clamp(r.weight)
        if w > weights.get(r.skill, 0.0):
            weights[r.skill] = round(w, 4)
            reasons[r.skill] = r.reason
    return {"weights": weights, "summary": res.summary, "confidence": res.confidence,
            "reasons": reasons, "dropped_skills": dropped, "doc_count": len(docs)}
