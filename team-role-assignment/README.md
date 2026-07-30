# 🧩 AI Lab Team — Phân tích bài lab & phân công nhóm

Phân tích GitHub activity thật của từng thành viên + tự đọc repo bài lab → đề xuất phân công tối ưu kèm Fit Score, bằng chứng và tóm tắt bài lab. Hai vai trò: **Học viên** (tạo phân tích, xem phân công, gửi ticket) và **Lab Coach** (theo dõi mọi nhóm, phê duyệt, trả lời ticket).

> Hackathon Hướng C — Làn mở. Kế hoạch chi tiết: [PLAN.md](PLAN.md).

## Tính năng chính
- Phân quyền theo 2 vai trò: **Học viên** và **Lab Coach**.
- **Học viên**: Tạo phân tích dựa trên GitHub activity, xem đề xuất phân công nhóm, gửi ticket hỗ trợ.
- **Lab Coach**: Dashboard theo dõi tiến độ của tất cả các nhóm, phê duyệt phân công, trả lời ticket.
- AI đọc hiểu tự động repo bài lab và tóm tắt yêu cầu bài lab.
- AI phân tích dữ liệu GitHub để tính độ phù hợp (Fit Score) và đưa ra bằng chứng giải thích lý do giao task.

## Tech dự kiến
- Frontend: HTML/CSS/JS tĩnh (`static/index.html`)
- Backend: FastAPI (Python), Uvicorn
- AI/LLM: OpenAI API (phân tích & đọc hiểu), Pydantic (validate schemas)
- Tích hợp: GitHub REST API (kéo lịch sử commit/hoạt động)

## Thông tin nhóm

| STT | Họ và tên           | Mã học viên | Phân công công việc                                                                                   |
| --- | ---------------------- | -------------- | --------------------------------------------------------------------------------------------------------- |
| 1   | Trần Thị Thanh Tâm  | 2A202601267    | Xây dựng giao diện Web tương tác và chuẩn bị dữ liệu mẫu                                      |
| 2   | Huỳnh Hoàng Việt    | 2A202601105    | Đầu mối kéo code/file của nhóm (`git pull`), làm API FastAPI và lắp ráp pipeline hoàn chỉnh |
| 3   | Nguyễn Văn Tiến     | 2A202601433    | Tích hợp API OpenAI, thiết kế Schemas và viết luồng AI phân tích kỹ năng                       |
| 4   | Tạ Thị Nga           | 2A202601125    | Kéo dữ liệu từ GitHub và xây dựng AI đọc hiểu yêu cầu dự án                                 |
| 5   | Nguyễn Duy Hải Bằng | 2A202601225    | Phát triển thuật toán AI Matcher và xây dựng kịch bản kiểm thử đánh giá                     |

## Chạy

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env           # rồi điền OPENAI_API_KEY (+ GITHUB_TOKEN nếu có)
uvicorn server:app --port 8000   # mở http://localhost:8000
```
