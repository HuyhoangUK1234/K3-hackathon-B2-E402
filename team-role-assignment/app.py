"""AI-Based Team Role Assignment — Streamlit UI, 3 tabs mirroring the 3 flows."""
import os

import streamlit as st
from dotenv import load_dotenv

from src.dev_analyzer import analyze_developer
from src.github_fetcher import fetch_developer
from src.matcher import match
from src.project_analyzer import analyze_project
from src.schemas import DeveloperProfile, TaskGraph

load_dotenv()

st.set_page_config(page_title="AI Team Role Assignment", page_icon="🧩", layout="wide")
st.title("🧩 AI-Based Team Role Assignment")
st.caption("Phân tích GitHub của từng thành viên + yêu cầu dự án → đề xuất phân công kèm Fit Score. "
           "Kết quả là ĐỀ XUẤT — trưởng nhóm luôn là người quyết định cuối.")

if "profiles" not in st.session_state:
    st.session_state.profiles = []       # list[DeveloperProfile]
if "task_graph" not in st.session_state:
    st.session_state.task_graph = None   # TaskGraph | None
if "match_result" not in st.session_state:
    st.session_state.match_result = None

with st.sidebar:
    st.header("Trạng thái")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        st.error("Chưa có OPENAI_API_KEY trong .env — điền key rồi chạy lại.")
    else:
        st.success("OpenAI key: OK")
    if not os.getenv("GITHUB_TOKEN", "").strip():
        st.warning("Chưa có GITHUB_TOKEN (optional) — GitHub API giới hạn 60 request/giờ.")
    st.metric("Thành viên đã phân tích", len(st.session_state.profiles))
    st.metric("Task trong dự án",
              len(st.session_state.task_graph.tasks) if st.session_state.task_graph else 0)
    if st.button("🗑️ Xoá toàn bộ dữ liệu phiên"):
        st.session_state.profiles = []
        st.session_state.task_graph = None
        st.session_state.match_result = None
        st.rerun()

tab_dev, tab_proj, tab_match = st.tabs(
    ["1️⃣ Thành viên (Developer Analysis)", "2️⃣ Dự án (Project Analysis)", "3️⃣ Phân công (Matching)"]
)

# ---------------- Tab 1: Developer Analysis ----------------
with tab_dev:
    st.subheader("Thêm thành viên")
    with st.form("dev_form"):
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("GitHub username *", placeholder="vd: torvalds")
            self_skills = st.text_input("Skill tự khai (phân cách bởi dấu phẩy)",
                                        placeholder="Java, Spring Boot, SQL")
            wants = st.text_input("Skill muốn học", placeholder="Kubernetes, MLOps")
        with c2:
            readiness = st.slider("Mức sẵn sàng học công nghệ mới", 1, 5, 3)
            years = st.number_input("Số năm kinh nghiệm", 0.0, 40.0, 1.0, step=0.5)
        submitted = st.form_submit_button("🔍 Phân tích thành viên", type="primary")

    if submitted:
        if not username.strip():
            st.error("Cần GitHub username.")
        elif any(p.github_username == username.strip().lstrip("@") for p in st.session_state.profiles):
            st.error(f"'{username}' đã được phân tích rồi.")
        else:
            with st.spinner(f"Đang lấy dữ liệu GitHub của {username}..."):
                gh = fetch_developer(username)
            if gh.error:
                st.error(gh.error)
            else:
                st.info(f"GitHub OK: {gh.public_repos} repo public · "
                        f"{len(gh.recent_commit_messages)} commit gần đây · "
                        f"ngôn ngữ: {', '.join(list(gh.languages)[:5]) or 'không rõ'}")
                with st.spinner("AI đang xây dựng hồ sơ năng lực..."):
                    try:
                        profile = analyze_developer(gh, self_skills, wants, readiness, years)
                        st.session_state.profiles.append(profile)
                        st.session_state.match_result = None
                        st.success(f"Đã thêm {profile.display_name}")
                    except Exception as e:
                        st.error(f"Lỗi gọi AI: {e}")

    for i, p in enumerate(st.session_state.profiles):
        with st.expander(f"👤 {p.display_name} (@{p.github_username}) — {', '.join(p.suggested_roles)}"):
            st.write(p.summary)
            st.table([{
                "Skill": s.name, "Level": s.level, "Bằng chứng": s.evidence
            } for s in p.skills])
            c1, c2 = st.columns(2)
            c1.write("**Điểm mạnh:** " + "; ".join(p.strengths))
            c2.write(f"**Muốn học:** {', '.join(p.wants_to_learn) or '—'} · "
                     f"**Sẵn sàng học:** {p.learning_readiness}/5 · "
                     f"**Kinh nghiệm:** {p.years_experience} năm")
            if st.button("Xoá thành viên này", key=f"del_{i}"):
                st.session_state.profiles.pop(i)
                st.session_state.match_result = None
                st.rerun()

# ---------------- Tab 2: Project Analysis ----------------
with tab_proj:
    st.subheader("Phân tích dự án")
    readme = st.text_area("Nội dung README.md *", height=220,
                          placeholder="Dán README của dự án vào đây...")
    deps = st.text_area("Dependency files (package.json / requirements.txt / pom.xml...)",
                        height=140, placeholder="Dán nội dung file dependency (nếu có)...")
    notes = st.text_input("Ghi chú thêm (deadline, ưu tiên, ràng buộc...)")

    if st.button("🔍 Phân tích dự án", type="primary"):
        if not readme.strip():
            st.error("Cần nội dung README.")
        else:
            with st.spinner("AI đang phân tích dự án..."):
                try:
                    st.session_state.task_graph = analyze_project(readme, deps, notes)
                    st.session_state.match_result = None
                except Exception as e:
                    st.error(f"Lỗi gọi AI: {e}")

    tg: TaskGraph | None = st.session_state.task_graph
    if tg:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Loại dự án", tg.project_type)
        c2.metric("Quy mô", tg.scale)
        c3.metric("Số task", len(tg.tasks))
        c4.metric("Độ tin cậy phân tích", tg.confidence)
        if tg.confidence == "low" and tg.clarifying_questions:
            st.warning("**Thông tin dự án chưa đủ chắc — AI cần hỏi thêm:**\n\n"
                       + "\n".join(f"- {q}" for q in tg.clarifying_questions))
        st.write("**Tech stack:** " + ", ".join(tg.tech_stack))
        st.write("**Module chính:** " + ", ".join(tg.modules))
        st.table([{
            "Đầu việc": t.name,
            "Kỹ năng cần": ", ".join(t.required_skills),
            "Độ khó": t.difficulty,
            "Ước lượng (ngày)": t.estimate_days,
        } for t in tg.tasks])

# ---------------- Tab 3: Matching ----------------
with tab_match:
    st.subheader("Phân công Developer × Task")
    n_dev = len(st.session_state.profiles)
    tg = st.session_state.task_graph
    if n_dev == 0 or tg is None:
        st.info("Cần ít nhất 1 thành viên (Tab 1) và 1 dự án đã phân tích (Tab 2).")
    else:
        st.write(f"Sẵn sàng match **{n_dev} thành viên** × **{len(tg.tasks)} task**.")
        if st.button("🎯 Chạy phân công", type="primary"):
            with st.spinner("AI đang tối ưu phân công..."):
                try:
                    st.session_state.match_result = match(st.session_state.profiles, tg)
                except Exception as e:
                    st.error(f"Lỗi gọi AI: {e}")

        mr = st.session_state.match_result
        if mr:
            st.table([{
                "Thành viên": a.developer,
                "Công việc": a.task,
                "Fit Score": f"{a.fit_score}%",
                "Cần học thêm": ", ".join(a.skills_to_learn) or "—",
            } for a in mr.assignments])
            st.markdown("#### Lý do phân công")
            for a in mr.assignments:
                st.markdown(f"**{a.developer} → {a.task} ({a.fit_score}%)**")
                for r in a.reasons:
                    st.markdown(f"- {r}")
            if mr.unassigned_tasks:
                st.error("**Task chưa giao được (không ai đủ phù hợp):** "
                         + ", ".join(mr.unassigned_tasks))
            for w in mr.warnings:
                st.warning(w)
            st.info("**Ghi chú workload:** " + mr.workload_notes)
            st.caption("⚠️ Đây là đề xuất của AI dựa trên dữ liệu công khai + tự khai. "
                       "Trưởng nhóm duyệt và chỉnh trước khi chốt — tool không xếp hạng năng lực con người.")
