"""Flow 3: DeveloperProfiles x TaskGraph -> MatchResult with fit scores and cited reasons."""
import json

from .llm import MODEL_SMART, call_json
from .schemas import DeveloperProfile, MatchResult, TaskGraph

SYSTEM = """Bạn là trưởng nhóm kỹ thuật phân công công việc cho team.

MỤC TIÊU TỐI ƯU (theo thứ tự):
1. Tối đa mức phù hợp skill giữa người và task (dựa trên evidence trong profile).
2. Cân bằng workload: không ai nhận quá ~40% tổng estimate_days; ai cũng có việc nếu đủ task.
3. Cơ hội học: nếu chênh lệch fit nhỏ (<10 điểm), ưu tiên người có wants_to_learn khớp với task
   và learning_readiness cao — ghi rõ các skill họ sẽ phải học vào skills_to_learn.

QUY TẮC GIẢI THÍCH (bắt buộc):
- Mỗi assignment phải có >=1 reason TRÍCH DẪN evidence cụ thể từ profile
  (ví dụ: "34 commit Spring Boot trong repo shop-api", "tự khai 3 năm React").
- KHÔNG bịa evidence không có trong profile.
- fit_score 0-100: 90+ = skill khớp hoàn toàn có bằng chứng mạnh; 70-89 = khớp phần lớn;
  50-69 = phải học thêm đáng kể; <50 chỉ dùng khi bất khả kháng và phải ghi warning.
- Task không ai phù hợp (fit < 50 với mọi người) -> đưa vào unassigned_tasks kèm warning
  thay vì ép giao.
- Đây là bảng ĐỀ XUẤT để trưởng nhóm duyệt — nêu rõ trong workload_notes những chỗ
  cần con người quyết định.
- reasons và workload_notes viết tiếng Việt, tên công nghệ giữ tiếng Anh."""


def match(profiles: list[DeveloperProfile], task_graph: TaskGraph) -> MatchResult:
    payload = {
        "developers": [p.model_dump() for p in profiles],
        "task_graph": task_graph.model_dump(),
    }
    user = (
        "Dữ liệu team và dự án:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nPhân công và trả về MatchResult."
    )
    return call_json(MODEL_SMART, SYSTEM, user, MatchResult, temperature=0.3)
