# KẾ HOẠCH — AI-Based Team Role Assignment

> Phân tích GitHub activity của từng thành viên + phân tích yêu cầu dự án → đề xuất phân công tối ưu kèm Fit Score và giải thích.

**Lưu ý hackathon:** ý tưởng này thuộc **Hướng C — Làn mở** theo `01-de-bai.md`. Vẫn phải qua đủ 5 tiêu chí nghiệm thu (pain + evidence + impact + lát cắt 1 câu + ≥3 willing users) và nộp `spec.md` theo `03-template-ai-spec.md` trước 23:59 N1.

## 1. Lát cắt MỘT CÂU (bắt buộc theo đề bài)

> **Trưởng nhóm dự án** (1 user) · **cần phân chia công việc cho team** (1 việc) · **AI phân tích GitHub profile các thành viên + README dự án rồi quyết định ai làm task nào** (1 quyết định AI) · **nhận bảng phân công kèm Fit Score và lý do** (1 kết quả).

### Non-goals (không build trong hackathon)
- Không tích hợp Jira/Trello/GitHub Projects — chỉ output bảng.
- Không train model riêng — dùng LLM qua API.
- Không auth/multi-tenant — chạy local, single user.
- Không theo dõi tiến độ sau khi phân công.

## 2. Kiến trúc — 3 luồng

```
┌─────────────────────┐   ┌─────────────────────┐
│ Luồng 1: Developer  │   │ Luồng 2: Project    │
│ Analysis            │   │ Analysis            │
│                     │   │                     │
│ GitHub API:         │   │ README.md           │
│ - commits, PRs      │   │ - cấu trúc source   │
│ - issues, languages │   │ - package.json /    │
│ + form tự khai:     │   │   requirements.txt  │
│   skill, mong muốn  │   │                     │
│        │            │   │        │            │
│        ▼            │   │        ▼            │
│ LLM → Developer     │   │ LLM → Task Graph    │
│ Profile (JSON)      │   │ (JSON)              │
└─────────┬───────────┘   └──────────┬──────────┘
          │                          │
          └──────────┬───────────────┘
                     ▼
        ┌─────────────────────────┐
        │ Luồng 3: Matching       │
        │ LLM: profile × task     │
        │ → assignment + FitScore │
        │   + explanation         │
        └─────────────────────────┘
```

### Luồng 1 — Developer Analysis
- **Thu thập** (code thường, không AI): GitHub REST API lấy top languages, commit messages (100 gần nhất), PR titles, repo topics. Form nhập tay: skill hiện có, skill muốn học, mức sẵn sàng học (1-5), số năm kinh nghiệm.
- **AI xử lý**: 1 lời gọi LLM / developer, output JSON theo schema `DeveloperProfile`: `{skills: [{name, level, evidence}], strengths, learning_capacity, suggested_roles}`.
- **Chống bịa (lớp ① nguồn sự thật)**: mỗi skill trong profile PHẢI kèm `evidence` trỏ về commit/PR/repo cụ thể hoặc `"self-reported"`. Không có evidence → không đưa vào profile.

### Luồng 2 — Project Analysis
- **Input**: README.md + danh sách file dependency (paste hoặc link repo).
- **AI xử lý**: 1 lời gọi LLM, output JSON `TaskGraph`: `{project_type, scale, tech_stack, modules, tasks: [{name, required_skills, difficulty, estimate_days}]}`.
- **Lớp ② mơ hồ**: README quá ngắn / thiếu dependency file → AI trả `confidence: low` + danh sách câu hỏi cần bổ sung, không đoán bừa estimate.

### Luồng 3 — Matching
- **Input**: list `DeveloperProfile` + `TaskGraph`.
- **AI xử lý**: 1 lời gọi LLM với ràng buộc rõ trong prompt: maximize fit, cân bằng workload (không ai nhận >40% tổng effort), ưu tiên cơ hội học skill mới khi fit gap nhỏ.
- **Output**: `{assignments: [{dev, task, fit_score, reasons: [...]}], workload_balance, unassigned_tasks}`.
- **Giải thích bắt buộc**: mỗi assignment ≥1 reason trỏ về evidence từ Luồng 1 (ví dụ "A có 34 commit Spring Boot trong repo X").

## 3. Tech stack

| Thành phần | Chọn | Lý do |
|---|---|---|
| Ngôn ngữ | Python 3.11+ | nhanh cho hackathon, SDK đầy đủ |
| UI | Streamlit | 1 file ra demo được, đủ cho 5 phút demo |
| LLM | OpenAI `gpt-4o-mini` (default) / `gpt-4o` cho matching | mini rẻ cho profile extraction; matching cần suy luận hơn |
| Structured output | OpenAI `response_format: json_schema` | ép JSON đúng schema, khỏi parse lỗi |
| GitHub data | `requests` + GitHub REST API (token optional) | PyGithub nặng không cần |
| Config | `python-dotenv` + `.env` | key không vào code |

## 4. Cấu trúc thư mục

```
team-role-assignment/
├── .env                  # API keys (KHÔNG commit)
├── .env.example          # template
├── .gitignore
├── requirements.txt
├── app.py                # Streamlit UI — 3 tab: Developers / Project / Matching
├── src/
│   ├── github_fetcher.py # Luồng 1 thu thập (không AI)
│   ├── dev_analyzer.py   # Luồng 1 AI → DeveloperProfile
│   ├── project_analyzer.py # Luồng 2 AI → TaskGraph
│   ├── matcher.py        # Luồng 3 AI → Assignments
│   ├── schemas.py        # Pydantic: DeveloperProfile, TaskGraph, Assignment
│   └── llm.py            # OpenAI client wrapper + json_schema helper
└── eval/
    └── golden_set.json   # ≥20 case kiểm thử (yêu cầu §7 spec)
```

## 5. Lộ trình build

| Bước | Việc | Ước lượng |
|---|---|---|
| 1 | Setup: env, requirements, schemas.py, llm.py | 1h |
| 2 | Luồng 2 trước (dễ nhất — chỉ cần README) | 2h |
| 3 | Luồng 1: github_fetcher + dev_analyzer | 3h |
| 4 | Luồng 3: matcher + prompt ràng buộc workload | 2h |
| 5 | Streamlit UI 3 tab nối luồng | 2h |
| 6 | Golden set ≥20 case + chạy eval | 2h |
| 7 | Polish demo 5 phút: 3-4 dev profile mẫu + 1 repo mẫu | 1h |

Build Luồng 2 trước vì demo được sớm nhất với ≥1 lời gọi AI thật (ràng buộc đề bài).

## 6. 4 lớp chỗ khó (bắt buộc theo đề bài — nháp)

| Lớp | Chỗ khó | Cách xử |
|---|---|---|
| ① Nguồn sự thật | AI bịa skill dev không có / bịa số commit | mọi skill phải kèm evidence trỏ được về data thật; số liệu lấy từ GitHub API chứ không để LLM đếm |
| ② Mơ hồ | README sơ sài, profile GitHub trống | trả confidence low + câu hỏi bổ sung, không đoán im lặng |
| ③ Ngoài phạm vi | user đòi đánh giá "ai giỏi hơn ai" / dùng để chấm lương | từ chối xếp hạng người; tool chỉ match task, nói rõ trong UI |
| ④ Đặc thù domain | Fit Score sai → giao việc sai người → trễ deadline cả team | matching là **augment** không automate: bảng đề xuất luôn cho leader sửa tay trước khi chốt |

## 7. Chi phí API (ước)

- Profile 1 dev: ~3-5K token input → gpt-4o-mini ≈ $0.001/dev.
- Project analysis: ~5-10K token ≈ $0.002.
- Matching (gpt-4o): ~5K token ≈ $0.02/lần.
- Cả demo + eval 20 case: **dưới $1**. Không lo.

## 8. Setup

```bash
cd team-role-assignment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# điền OPENAI_API_KEY vào .env
streamlit run app.py
```
