# EduTrack — Hệ thống theo dõi tiến độ học viên

Web app cho trung tâm đào tạo lập trình: giảng viên xem dashboard tiến độ, học viên nộp bài và nhận feedback tự động từ AI.

## Tính năng chính
- Đăng nhập / phân quyền (giảng viên, học viên, admin)
- Dashboard tiến độ theo lớp và theo cá nhân (biểu đồ)
- Nộp bài tập, chấm tự động bằng LLM + rubric
- Thông báo qua email khi trễ deadline

## Tech dự kiến
- Frontend: React + TypeScript, TailwindCSS
- Backend: FastAPI (Python), PostgreSQL
- AI: OpenAI API cho chấm bài
- Deploy: Docker trên VPS

## requirements.txt (backend)
```
fastapi
uvicorn
sqlalchemy
psycopg2-binary
openai
python-jose
```

## package.json (frontend, rút gọn)
```json
{"dependencies": {"react": "^18", "typescript": "^5", "tailwindcss": "^3", "recharts": "^2", "axios": "^1"}}
```
