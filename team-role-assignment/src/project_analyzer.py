"""Flow 2: README + dependency files -> TaskGraph."""
from .llm import MODEL_FAST, call_json
from .schemas import TaskGraph

SYSTEM = """Bạn là kỹ sư trưởng phân tích dự án phần mềm để lập danh sách đầu việc.

QUY TẮC:
- Chỉ kết luận từ nội dung được cung cấp (README, dependency files). Không bịa công nghệ không xuất hiện.
- Nếu thông tin quá mỏng (README ngắn, không có dependency file, mục tiêu không rõ):
  đặt confidence = "low", vẫn tạo task graph tốt nhất có thể, và liệt kê clarifying_questions
  (những câu cần hỏi chủ dự án). KHÔNG đoán im lặng.
- tasks: 4-10 đầu việc phủ đủ vòng đời (thiết kế DB, API, UI, AI/model nếu có, DevOps, testing, docs
  — chỉ những mục thực sự cần cho dự án này).
- estimate_days thực tế cho team 3-5 người mới ở mức intermediate.
- Mô tả task bằng tiếng Việt, tên công nghệ giữ nguyên tiếng Anh."""


def analyze_project(readme: str, dependency_files: str = "", extra_notes: str = "") -> TaskGraph:
    user = (
        "=== README.md ===\n" + (readme.strip() or "(trống)")
        + "\n\n=== Dependency files (package.json / requirements.txt / pom.xml ...) ===\n"
        + (dependency_files.strip() or "(không cung cấp)")
        + "\n\n=== Ghi chú thêm từ chủ dự án ===\n" + (extra_notes.strip() or "(không có)")
        + "\n\nPhân tích và trả về TaskGraph."
    )
    return call_json(MODEL_FAST, SYSTEM, user, TaskGraph)
