"""Pydantic schemas for the three flows: DeveloperProfile, TaskGraph, MatchResult."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------- Flow 1: Developer Analysis ----------

class Skill(BaseModel):
    name: str
    level: Literal["beginner", "intermediate", "advanced"]
    # Every skill must point to verifiable evidence (commit/repo/PR) or be
    # marked self-reported — the LLM is not allowed to invent skills.
    evidence: str = Field(description="Concrete evidence: repo/commit/PR reference, or 'self-reported'")


class DeveloperProfile(BaseModel):
    github_username: str
    display_name: str = ""
    skills: list[Skill]
    strengths: list[str]
    wants_to_learn: list[str] = []
    learning_readiness: int = Field(ge=1, le=5, description="1-5 self-reported willingness to learn new tech")
    years_experience: float = 0
    suggested_roles: list[str]
    summary: str


# ---------- Flow 2: Project Analysis ----------

class ProjectTask(BaseModel):
    name: str
    description: str
    required_skills: list[str]
    difficulty: Literal["low", "medium", "high"]
    estimate_days: float


class TaskGraph(BaseModel):
    project_type: str
    scale: Literal["small", "medium", "large"]
    tech_stack: list[str]
    modules: list[str]
    tasks: list[ProjectTask]
    confidence: Literal["low", "medium", "high"]
    # When confidence is low the model must ask instead of silently guessing.
    clarifying_questions: list[str] = []


# ---------- Flow 3: Matching ----------

class Assignment(BaseModel):
    developer: str
    task: str
    fit_score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(description="Each reason must cite evidence from the developer profile")
    skills_to_learn: list[str] = []


class MatchResult(BaseModel):
    assignments: list[Assignment]
    workload_notes: str
    unassigned_tasks: list[str] = []
    warnings: list[str] = []


# ---------- Raw GitHub data (no AI involved) ----------

class GitHubData(BaseModel):
    username: str
    display_name: str = ""
    public_repos: int = 0
    languages: dict[str, int] = {}          # language -> bytes across top repos
    top_repos: list[dict] = []              # [{name, description, language, stars, topics}]
    recent_commit_messages: list[str] = []  # newest first
    commit_count: int = 0                   # commits authored in recent repos (counted, not LLM)
    pr_count: int = 0                       # from GitHub search API
    issue_count: int = 0                    # from GitHub search API
    error: Optional[str] = None


# ---------- UI app (RoleFit AI) schemas — percent-based for the web UI ----------

class UISkill(BaseModel):
    name: str
    level: int = Field(ge=0, le=100, description="Proficiency percent")
    evidence: str = Field(description="Concrete evidence: repo/commit/language stat, or 'self-reported'")


class UIDevProfile(BaseModel):
    role_suited: Literal["Backend Developer", "Frontend Developer", "Fullstack Developer",
                         "Mobile Developer", "AI Engineer", "Data Engineer",
                         "DevOps Engineer", "QA Engineer", "Product/Docs"]
    skills: list[UISkill] = Field(description="4-6 skills, each with evidence")
    strengths: list[str] = Field(description="2-4 concrete strengths, Vietnamese")
    missing: list[str] = Field(description="1-3 skills missing vs their role, Vietnamese ok")
    learning_path: list[str] = Field(description="2-4 ordered learning steps, Vietnamese")
    summary: str


class UIProjectAnalysis(BaseModel):
    project_type: str
    scale: Literal["Nhỏ", "Trung bình", "Lớn"]
    tech_stack: list[str]
    modules: list[str]
    tasks: list[ProjectTask] = Field(description="4-8 tasks covering the project lifecycle")
    confidence: Literal["low", "medium", "high"]
    clarifying_questions: list[str] = []


class RepoReadPlan(BaseModel):
    """Agent decision: is the README enough, or which extra files to read?"""
    enough: bool = Field(description="True if README + dependency files already give enough info")
    files_to_read: list[str] = Field(
        default=[],
        description="Up to 6 file paths from the provided tree worth reading (docs/*.md, specs...). Empty if enough.")
    reason: str = Field(description="1 sentence why, Vietnamese")


class UIAssignment(BaseModel):
    task_id: str
    developer_id: str
    fit_score: int = Field(ge=0, le=100)
    reason: str = Field(description="1-2 sentences, must cite evidence from the profile, Vietnamese")
    skills_to_learn: list[str] = []


class UIMatchResult(BaseModel):
    assignments: list[UIAssignment]
    unassigned_task_ids: list[str] = []
    warnings: list[str] = []
    workload_notes: str
