# 🧩 AI-Based Team Role Assignment

Phân tích GitHub activity của từng thành viên + yêu cầu dự án → đề xuất phân công công việc tối ưu kèm Fit Score và giải thích có trích dẫn bằng chứng.

> Hackathon Hướng C — Làn mở. Kế hoạch chi tiết: [PLAN.md](PLAN.md).

## Thông tin nhóm

| STT | Họ và tên           | Mã học viên | Phân công công việc                                                                          |
| --- | ---------------------- | -------------- | ------------------------------------------------------------------------------------------------ |
| 1   | Trần Thị Thanh Tâm  | 2A202601267    | Định hướng thiết kế UI/UX giao diện và chuẩn bị dữ liệu mẫu                         |
| 2   | Huỳnh Hoàng Việt    | 2A202601105    | Đầu mối kéo code/file của nhóm (`git pull`), Vibe Code lắp ráp thành App hoàn chỉnh |
| 3   | Nguyễn Văn Tiến     | 2A202601433    | Định nghĩa cấu trúc Pydantic Schemas và config API OpenAI                                  |
| 4   | Tạ Thị Nga           | 2A202601125    | Lập bảng Scoring Matrix (Golden Set) & Soi nhật ký Trace Log                                 |
| 5   | Nguyễn Duy Hải Bằng | 2A202601225    | Viết System Prompt & phanh Guardrails cho AI phân tích                                        |

## Chạy

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env           # rồi điền OPENAI_API_KEY
streamlit run app.py
```

## Cấu trúc

| File                        | Vai trò                                                                                           |
| --------------------------- | -------------------------------------------------------------------------------------------------- |
| `app.py`                  | Streamlit UI — 3 tab: Thành viên / Dự án / Phân công                                        |
| `src/github_fetcher.py`   | Luồng 1 thu thập GitHub (REST API, không AI — mọi con số từ đây)                          |
| `src/dev_analyzer.py`     | Luồng 1 AI: GitHubData + tự khai → DeveloperProfile (skill nào cũng phải có evidence)       |
| `src/project_analyzer.py` | Luồng 2 AI: README + deps → TaskGraph (thiếu info → confidence low + câu hỏi, không đoán) |
| `src/matcher.py`          | Luồng 3 AI: profiles × tasks → assignments + fit score + lý do cite evidence                   |
| `src/llm.py`              | Wrapper OpenAI JSON mode + validate Pydantic + retry 1 lần                                        |
| `src/schemas.py`          | Pydantic schemas cho cả 3 luồng                                                                  |
| `eval/golden_set.json`    | Bộ case kiểm thử (đang mở rộng lên ≥20)                                                    |
| `demo/sample_readme.md`   | README mẫu để demo Tab 2 nhanh                                                                  |
