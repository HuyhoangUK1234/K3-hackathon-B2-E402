"""Toán của vector năng lực — thuần Python, không import LLM, không mạng.

Trục = key trong skills.json, cố định. Vector = {skill_id: 0..1}, thiếu key = 0.

TĂNG TRƯỞNG — hai chiều, cả hai cộng dồn theo từng lab:

  Học viên   student[s] = 1 - Π(1 - gain_lab[s])
             Mỗi lab là một lần chứng minh. Học lại kỹ năng cũ -> trục đó DÀI ra
             (thêm giảm dần, không bao giờ chạm 1). Học kỹ năng mới -> trục đang 0
             nay khác 0, tức THÊM CHIỀU.

  Lab        required[lab][s] = max(declared, observed, 0.5^bậc × required[cha][s])
             declared  — LLM đọc tài liệu đề bài (src/extract.py)
             inherited — lab sau kế thừa yêu cầu lab trước, giảm 1 nửa mỗi bậc
             observed  — kỹ năng đa số học viên THỰC SỰ dùng trong lab đó, kể cả
                         đề bài không viết ra. Đây là phần lab tự học từ hành vi
                         cohort: càng nhiều lượt chạy, vector lab càng sát thực tế.
"""

# Trần điểm theo loại bằng chứng — LLM đề xuất strength, code chặn trần.
EVIDENCE_CAP = {
    "commit": 0.60,        # có commit thật trên repo lab đó
    "report": 0.40,        # báo cáo cá nhân
    "group_report": 0.25,  # chỉ báo cáo nhóm, không rõ ai làm phần nào
    "none": 0.10,
}
BLOCKED_FACTOR = 0.4            # blocker nhắc kỹ năng nào -> kỹ năng đó nhân 0.4
WEAK_ATTRIBUTION_FACTOR = 0.6   # commit đếm được nhưng không lọc được theo tác giả
INHERIT_DECAY = 0.5             # mỗi bậc depends_on
OBSERVED_MAJORITY = 0.60        # >=50% học viên thể hiện -> lab thật sự cần
OBSERVED_MINORITY = 0.35        # >=25%
OBSERVED_MIN_GAIN = 0.2         # gain dưới mức này không tính là "đã dùng"


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ---------- Bước 1: signal thô -> gain của 1 học viên trong 1 lab ----------

def apply_evidence_caps(signals: list[dict], skills: dict, blocked: set[str],
                        weak_attribution: bool = False) -> tuple[dict, dict, list]:
    """Áp trần theo bằng chứng + phạt blocker. Trả (gains, evidence, dropped).

    signals: [{skill, strength, evidence_type, evidence}] — output LLM.
    Skill ngoài registry bị VỨT, không tự thêm trục.
    """
    gains: dict[str, float] = {}
    evidence: dict[str, dict] = {}
    dropped: list[str] = []

    for sig in signals:
        skill = sig["skill"]
        if skill not in skills:
            dropped.append(skill)
            continue
        cap = EVIDENCE_CAP.get(sig["evidence_type"], EVIDENCE_CAP["none"])
        if sig["evidence_type"] == "commit" and weak_attribution:
            cap *= WEAK_ATTRIBUTION_FACTOR      # không chắc commit của đúng người này
        val = clamp(float(sig["strength"])) * cap
        if skill in blocked:
            val *= BLOCKED_FACTOR
        if val > gains.get(skill, 0.0):
            gains[skill] = round(val, 4)
            evidence[skill] = {"type": sig["evidence_type"], "text": sig.get("evidence", "")}
    return gains, evidence, dropped


# ---------- Bước 2: cộng dồn qua các lab ----------

def accumulate_student(gain_records: list[dict], lab_seq: list[str]) -> dict:
    """[gain từng lab] -> vector tích luỹ + lịch sử tăng trưởng từng trục."""
    by_lab = {g["lab"]: g for g in gain_records}
    vec: dict[str, float] = {}
    history: dict[str, list] = {}
    interests: set[str] = set()
    blocked_latest: set[str] = set()

    for lab in lab_seq:                      # đúng thứ tự lab, cũ trước mới sau
        g = by_lab.get(lab)
        if not g:
            continue
        interests |= set(g.get("interests", []))
        blocked_latest = set(g.get("blocked", []))    # blocker của lab gần nhất
        for skill, gain in g["gains"].items():
            before = vec.get(skill, 0.0)
            vec[skill] = round(1 - (1 - before) * (1 - gain), 4)
            history.setdefault(skill, []).append(
                {"lab": lab, "gain": gain, "after": vec[skill]})

    return {
        "vector": vec,
        "history": history,
        "interests": sorted(interests - set(vec)),    # muốn học và CHƯA có
        "open_blockers": sorted(blocked_latest),
        "labs_done": [l for l in lab_seq if l in by_lab],
    }


# ---------- Bước 3: vector yêu cầu của lab ----------

def lab_observed(gain_records: list[dict], skills: dict) -> dict[str, float]:
    """Kỹ năng học viên THỰC SỰ dùng trong lab, kể cả đề bài không nhắc."""
    n = len(gain_records)
    if n == 0:
        return {}
    counts: dict[str, int] = {}
    for g in gain_records:
        for skill, val in g["gains"].items():
            if val >= OBSERVED_MIN_GAIN and skill in skills:
                counts[skill] = counts.get(skill, 0) + 1
    out = {}
    for skill, c in counts.items():
        frac = c / n
        if frac >= 0.5:
            out[skill] = OBSERVED_MAJORITY
        elif frac >= 0.25:
            out[skill] = OBSERVED_MINORITY
    return out


def lab_required(lab_name: str, labs: dict, declared: dict, observed: dict) -> dict:
    """Hợp 3 nguồn + kế thừa đệ quy theo depends_on."""
    memo: dict[str, dict] = {}

    def resolve(name: str) -> dict[str, float]:
        if name in memo:
            return memo[name]
        vec: dict[str, float] = {}
        for src in (declared.get(name, {}).get("weights", {}), observed.get(name, {})):
            for skill, w in src.items():
                vec[skill] = max(vec.get(skill, 0.0), w)
        for dep in labs[name].get("depends_on", []):
            for skill, w in resolve(dep).items():
                vec[skill] = max(vec.get(skill, 0.0), round(w * INHERIT_DECAY, 4))
        memo[name] = vec
        return vec

    vec = resolve(lab_name)
    own = set(declared.get(lab_name, {}).get("weights", {}))
    obs = set(observed.get(lab_name, {}))
    return {
        "lab": lab_name,
        "vector": {k: round(v, 4) for k, v in sorted(vec.items(), key=lambda x: -x[1])},
        "source": {
            "declared": sorted(own),
            "observed_only": sorted(obs - own),       # cohort dùng mà đề bài không nói
            "inherited_only": sorted(set(vec) - own - obs),
        },
        "summary": declared.get(lab_name, {}).get("summary", ""),
        "confidence": declared.get(lab_name, {}).get("confidence", "low"),
        "reasons": declared.get(lab_name, {}).get("reasons", {}),
    }
