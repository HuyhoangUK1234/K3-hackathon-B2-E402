# 🧩 AI-Based Team Role Assignment

Phân tích GitHub activity của từng thành viên + yêu cầu dự án → đề xuất phân công công việc tối ưu kèm Fit Score và giải thích có trích dẫn bằng chứng.

> Hackathon Hướng C — Làn mở. Kế hoạch chi tiết: [PLAN.md](PLAN.md).

## Chạy

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env           # rồi điền OPENAI_API_KEY
streamlit run app.py
```

## Cấu trúc

| File | Vai trò |
|---|---|
| `app.py` | Streamlit UI — 3 tab: Thành viên / Dự án / Phân công |
| `src/github_fetcher.py` | Luồng 1 thu thập GitHub (REST API, không AI — mọi con số từ đây) |
| `src/dev_analyzer.py` | Luồng 1 AI: GitHubData + tự khai → DeveloperProfile (skill nào cũng phải có evidence) |
| `src/project_analyzer.py` | Luồng 2 AI: README + deps → TaskGraph (thiếu info → confidence low + câu hỏi, không đoán) |
| `src/matcher.py` | Luồng 3 AI: profiles × tasks → assignments + fit score + lý do cite evidence |
| `src/llm.py` | Wrapper OpenAI JSON mode + validate Pydantic + retry 1 lần |
| `src/schemas.py` | Pydantic schemas cho cả 3 luồng |
| `eval/golden_set.json` | Bộ case kiểm thử (đang mở rộng lên ≥20) |
| `demo/sample_readme.md` | README mẫu để demo Tab 2 nhanh |

## Nguyên tắc an toàn (4 lớp chỗ khó)

1. **Nguồn sự thật**: số commit/ngôn ngữ lấy từ GitHub API, LLM không tự đếm; skill không evidence → loại.
2. **Mơ hồ**: README mỏng → `confidence: low` + câu hỏi bổ sung, không đoán im lặng.
3. **Ngoài phạm vi**: tool match người-việc, không xếp hạng "ai giỏi hơn ai" — ghi rõ trong UI.
4. **Cost of error**: đây là *augment* — output là đề xuất, trưởng nhóm duyệt trước khi chốt.
