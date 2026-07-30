"""Từ vựng kỹ năng dùng chung cho cả hệ thống — nguồn duy nhất: seed/skills.json.

Trước đây mỗi luồng tự đặt tên kỹ năng: người dùng gõ "NextJS", LLM sinh "Next.js",
bảng coverage lại ghi "Frontend Development" -> ba chuỗi khác nhau cho cùng một thứ,
so khớp bằng chuỗi luôn trượt. Ở đây mọi tên đều quy về ĐÚNG một skill id trong seed.

canon() chỉ là ánh xạ tra bảng (không LLM, không đoán): id -> label -> alias.
Không khớp thì trả None và phía gọi giữ nguyên tên gốc, không bịa ra trục mới.
"""
import unicodedata

from .seed_loader import load_skills

# Tên công nghệ hay gặp -> trục năng lực tương ứng trong seed/skills.json.
# Chỉ ánh xạ thứ rõ ràng; cái nào mơ hồ thì để None (giữ tên gốc) chứ không đoán.
ALIASES: dict[str, str] = {
    # Giao diện web
    "html": "ui-frontend", "css": "ui-frontend", "html/css": "ui-frontend",
    "javascript": "ui-frontend", "js": "ui-frontend", "typescript": "ui-frontend",
    "react": "ui-frontend", "reactjs": "ui-frontend", "next": "ui-frontend",
    "nextjs": "ui-frontend", "vue": "ui-frontend", "vuejs": "ui-frontend",
    "angular": "ui-frontend", "tailwind": "ui-frontend", "tailwindcss": "ui-frontend",
    "bootstrap": "ui-frontend", "frontend": "ui-frontend", "ui": "ui-frontend",
    "streamlit": "ui-frontend", "gradio": "ui-frontend",
    # Backend / server
    "fastapi": "backend-api", "flask": "backend-api", "django": "backend-api",
    "express": "backend-api", "nodejs": "backend-api", "node": "backend-api",
    "spring": "backend-api", "springboot": "backend-api", "uvicorn": "backend-api",
    "backend": "backend-api", "server": "backend-api", "pydantic": "backend-api",
    # Gọi API bên ngoài
    "restapi": "api-integration", "api": "api-integration", "http": "api-integration",
    "requests": "api-integration", "axios": "api-integration",
    "openaiapi": "api-integration", "githubapi": "api-integration",
    "apikey": "api-integration", "webhook": "api-integration",
    # Ngôn ngữ nền
    "python": "python", "python3": "python", "py": "python",
    # Git
    "git": "git-github", "github": "git-github", "gitlab": "git-github",
    "pullrequest": "git-github", "pr": "git-github", "versioncontrol": "git-github",
    # LLM
    "openai": "llm-app-dev", "llm": "llm-app-dev", "gpt": "llm-app-dev",
    "langchain": "llm-app-dev", "chatgpt": "llm-app-dev",
    "prompt": "prompt-engineering", "prompting": "prompt-engineering",
    "agent": "ai-agent-design", "aiagent": "ai-agent-design", "tooluse": "ai-agent-design",
    "rag": "rag-retrieval", "embedding": "rag-retrieval", "vectordb": "rag-retrieval",
    "vectorsearch": "rag-retrieval", "semanticsearch": "rag-retrieval",
    # Dữ liệu
    "pandas": "data-handling", "numpy": "data-handling", "csv": "data-handling",
    "json": "data-handling", "excel": "data-handling", "etl": "data-handling",
    "matplotlib": "data-analysis", "seaborn": "data-analysis", "statistics": "data-analysis",
    "jupyter": "notebook-jupyter", "notebook": "notebook-jupyter", "colab": "notebook-jupyter",
    # Cơ sở dữ liệu
    "sql": "database", "mysql": "database", "postgres": "database",
    "postgresql": "database", "sqlite": "database", "mongodb": "database",
    "database": "database", "db": "database",
    # Kiểm thử / triển khai
    "pytest": "testing-eval", "unittest": "testing-eval", "test": "testing-eval",
    "testing": "testing-eval", "eval": "testing-eval", "qa": "testing-eval",
    "docker": "devops-deploy", "kubernetes": "devops-deploy", "k8s": "devops-deploy",
    "cicd": "devops-deploy", "deploy": "devops-deploy", "deployment": "devops-deploy",
    "render": "devops-deploy", "vercel": "devops-deploy", "heroku": "devops-deploy",
    # Môi trường
    "venv": "env-setup", "virtualenv": "env-setup", "pip": "env-setup",
    "conda": "env-setup", "requirementstxt": "env-setup", "dotenv": "env-setup",
    # Tài liệu / kế hoạch
    "markdown": "documentation", "readme": "documentation", "docs": "documentation",
    "documentation": "documentation", "technicalwriting": "documentation",
    "jira": "project-planning", "trello": "project-planning", "scrum": "project-planning",
    "agile": "project-planning", "roadmap": "project-planning", "backlog": "project-planning",
    "demo": "presentation-demo", "slide": "presentation-demo", "powerpoint": "presentation-demo",
    "figma": "user-research", "survey": "user-research", "interview": "user-research",
    "debug": "debugging", "debugging": "debugging", "traceback": "debugging",
}


def _norm(s: str) -> str:
    """Bỏ dấu, bỏ ký tự không phải chữ/số, hạ chữ thường.

    'Next.js', 'NextJS', 'next js' -> 'nextjs';  'Kiểm thử' -> 'kiemthu'.
    """
    txt = unicodedata.normalize("NFD", str(s or ""))
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = txt.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in txt.lower() if c.isalnum())


_CACHE: dict = {}


def catalog() -> dict[str, dict]:
    """{skill_id: {label, description}} từ seed/skills.json."""
    if "catalog" not in _CACHE:
        _CACHE["catalog"] = load_skills()
    return _CACHE["catalog"]


def _index() -> dict[str, str]:
    """Bảng tra: chuỗi đã chuẩn hoá -> skill id."""
    if "index" not in _CACHE:
        idx: dict[str, str] = {}
        for sid, meta in catalog().items():
            idx[_norm(sid)] = sid
            idx[_norm(meta["label"])] = sid
        for alias, sid in ALIASES.items():
            if sid in catalog():
                idx.setdefault(_norm(alias), sid)
        _CACHE["index"] = idx
    return _CACHE["index"]


def canon(name: str) -> str | None:
    """Tên tự do -> skill id trong seed. Không khớp -> None (không đoán bừa)."""
    key = _norm(name)
    if not key:
        return None
    idx = _index()
    if key in idx:
        return idx[key]
    # 'React (frontend)' / 'OpenAI API' -> thử bỏ phần trong ngoặc, tách từ
    for part in str(name).replace("(", " ").replace(")", " ").replace("/", " ").split():
        p = _norm(part)
        if p in idx:
            return idx[p]
    return None


def label(skill_id: str) -> str:
    """Label tiếng Việt để hiển thị; id lạ thì trả lại chính nó."""
    meta = catalog().get(skill_id)
    return meta["label"] if meta else str(skill_id)


def canon_list(names) -> list[str]:
    """Danh sách tên tự do -> danh sách skill id, giữ thứ tự, bỏ trùng.

    Tên không map được vẫn được GIỮ NGUYÊN — mất kỹ năng còn tệ hơn lệch tên.
    """
    out: list[str] = []
    for n in names or []:
        sid = canon(n) or str(n).strip()
        if sid and sid not in out:
            out.append(sid)
    return out


def menu_for_prompt() -> str:
    """Danh mục dán vào prompt: LLM chỉ được chọn id trong đây."""
    return "\n".join(f"- {sid}: {meta['label']} — {meta['description']}"
                     for sid, meta in catalog().items())


def as_options() -> list[dict]:
    """Cho UI: [{id, label, description}] theo đúng thứ tự file seed."""
    return [{"id": sid, "label": meta["label"], "description": meta.get("description", "")}
            for sid, meta in catalog().items()]
