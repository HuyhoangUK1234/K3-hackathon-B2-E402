"""Flow 1 AI step: GitHubData + self-reported form -> DeveloperProfile."""
import json

from .llm import MODEL_FAST, call_json
from .schemas import DeveloperProfile, GitHubData

SYSTEM = """Bạn là chuyên gia đánh giá năng lực lập trình viên cho việc phân công vai trò trong team.

QUY TẮC CHỐNG BỊA (bắt buộc):
- Mỗi skill trong output PHẢI có trường evidence trỏ về dữ liệu cụ thể được cung cấp:
  tên repo, ngôn ngữ thống kê từ GitHub, commit message — hoặc ghi 'self-reported' nếu chỉ do người đó tự khai.
- KHÔNG suy diễn skill từ thứ không có trong dữ liệu. Không có bằng chứng thì không đưa vào.
- Mức level: advanced chỉ khi có nhiều bằng chứng nhất quán (nhiều repo/commit cùng công nghệ);
  self-reported đơn thuần tối đa là intermediate.
- suggested_roles chọn trong: Backend, Frontend, Fullstack, Mobile, AI/ML, Data, DevOps, QA/Testing, Product/Docs.
- summary 2-3 câu tiếng Việt, trung thực về cả điểm mạnh lẫn khoảng trống dữ liệu."""


def analyze_developer(
    gh: GitHubData,
    self_skills: str = "",
    wants_to_learn: str = "",
    learning_readiness: int = 3,
    years_experience: float = 0,
) -> DeveloperProfile:
    payload = {
        "github_data": gh.model_dump(),
        "self_reported": {
            "skills": self_skills,
            "wants_to_learn": wants_to_learn,
            "learning_readiness_1_to_5": learning_readiness,
            "years_experience": years_experience,
        },
    }
    user = (
        "Dữ liệu về lập trình viên (GitHub thật + tự khai):\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + "\n\nHãy xây dựng DeveloperProfile. Nhớ: github_username, learning_readiness, "
          "years_experience giữ nguyên giá trị đầu vào."
    )
    profile = call_json(MODEL_FAST, SYSTEM, user, DeveloperProfile)
    # These fields are facts from input, never let the model rewrite them.
    profile.github_username = gh.username
    profile.display_name = gh.display_name or gh.username
    profile.learning_readiness = learning_readiness
    profile.years_experience = years_experience
    return profile
