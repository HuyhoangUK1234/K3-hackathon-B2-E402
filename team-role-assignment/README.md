# 🧩 AI Lab Team — Phân tích bài lab & phân công nhóm

Phân tích GitHub activity thật của từng thành viên + tự đọc repo bài lab → đề xuất phân công tối ưu kèm Fit Score, bằng chứng và tóm tắt bài lab. Hai vai trò: **Học viên** (tạo phân tích, xem phân công, gửi ticket) và **Lab Coach** (theo dõi mọi nhóm, phê duyệt, trả lời ticket).

> Hackathon Hướng C — Làn mở. Kế hoạch chi tiết: [PLAN.md](PLAN.md).

## Chạy

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env           # rồi điền OPENAI_API_KEY (+ GITHUB_TOKEN nếu có)
uvicorn server:app --port 8000   # mở http://localhost:8000
```

## Tính năng chính

- **Luồng 1** — hồ sơ kỹ năng từng người từ GitHub thật (commit/PR/ngôn ngữ), mỗi skill kèm evidence, radar chart.
- **Luồng 2** — agent tự đọc README + chọn file .md cần thiết trong repo bài lab; sinh tóm tắt bài lab, mục tiêu, Task Graph.
- **Luồng 3** — matching người × việc (Fit Score + lý do cite evidence), guardrail code chống dồn việc, bảng "Dự án cần gì — ai có?".
- **Vai trò**: đăng nhập Học viên / Lab Coach; coach xem danh sách nhóm (tỉ lệ cân bằng), phê duyệt, nhận xét.
- **Tickets**: học viên Raise Ticket khi kẹt; coach lọc/đánh dấu xong/phản hồi — cả 2 vai trò cùng xem.

## Cấu trúc

| File | Vai trò |
|---|---|
| `server.py` | FastAPI: UI + `/api/analyze`, `/api/groups`, `/api/tickets`, `/api/chat` |
| `static/index.html` | Toàn bộ UI (vanilla JS, 2 vai trò, radar, kéo-thả matching, tickets) |
| `src/pipeline.py` | 3 luồng AI + agent đọc repo + guardrail `_rebalance` |
| `src/github_fetcher.py` | Thu thập GitHub (REST API, không AI — mọi con số từ đây) |
| `src/repo_fetcher.py` | Đọc README/tree/file từ repo bài lab |
| `src/llm.py` | Wrapper OpenAI JSON mode + validate Pydantic + retry 1 lần |
| `src/schemas.py` | Pydantic schemas cho cả 3 luồng |
| `eval/golden_set.json` | Bộ câu thử 24 case (4 kiểu rủi ro, 12 case từ quan sát thực tế) |
| `eval/results.md` | Kết quả chạy bộ câu thử (kể cả câu fail) |
| `scripts/run_eval.py` | Chạy eval qua đúng prompt production |
| `data/` | groups.json + tickets.json (trạng thái runtime, không commit) |

## Nguyên tắc an toàn (4 lớp chỗ khó)

1. **Nguồn sự thật**: số commit/ngôn ngữ lấy từ GitHub API, LLM không tự đếm; skill không evidence → loại.
2. **Mơ hồ**: README mỏng → `confidence: low` + câu hỏi bổ sung, không đoán im lặng.
3. **Ngoài phạm vi**: tool match người-việc, không xếp hạng "ai giỏi hơn ai" — ghi rõ trong UI.
4. **Cost of error**: đây là *augment* — output là đề xuất, trưởng nhóm duyệt trước khi chốt.
