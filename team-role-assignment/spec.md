# AI SPEC — Phân công vai trò team từ GitHub activity · Nhóm [XX] · Zone [X]
 Tính năng mới

## §1. User & Job
- Job executor + workflow: Trưởng nhóm dự án học viên (team 3-5 người làm lab mỗi ngày) — nhận đề → hiểu yêu cầu → chia việc → theo dõi tiến độ.
- Core JTBD: "Khi team mới nhận dự án, tôi muốn biết ai nên làm phần nào để không mất mấy ngày đầu tranh luận và không giao nhầm việc cho người không làm nổi."
- Problem statement: Trưởng nhóm không biết năng lực thật của thành viên mới (chỉ biết qua tự giới thiệu), dẫn đến phân công sai, việc dồn về 1-2 người mạnh, thành viên yếu không học được gì, dự án trễ.
- Evidence:
  - Khảo sát 45 học viên trong khoá học làm bài khảo sát "Khảo sát nhu cầu về ứng dụng AI trong phân chia công việc nhóm ".
  -  quote nguyên văn từ khảo sát / Discord về pain phân công nhóm:
     "Team Leader thường phân công dựa trên những gì họ biết về từng người, nên đôi khi chưa đúng với năng lực thực tế."
     "Mình từng được giao task không đúng chuyên môn nên mất khá nhiều thời gian để tìm hiểu, ảnh hưởng đến tiến độ."
     "Khi có thành viên mới, rất khó biết ai phù hợp với từng công việc vì không có dữ liệu đánh giá khách quan."
     "README và tài liệu dự án khá dài, việc hiểu toàn bộ dự án rồi chia task hợp lý tốn rất nhiều thời gian."
     "Nhiều khi leader chỉ phân công theo những gì tôi làm tốt nên tôi không có không gian học hỏi những thứ mới"

## §2. Impact & quyết định chọn
- Bảng impact:
  
 | Ứng viên | Bao nhiêu người | Tần suất | Tốn gì mỗi lần | Khả thi |
|---|---:|---|---|---|
| **Khó phân công vai trò trong team (CHỌN)** | **35** | Mỗi project (~2–3 lần/khóa) | 1–3 ngày tranh luận đầu dự án, dễ giao sai người và phải phân công lại | Working prototype trong hackathon |
| Khó chia task theo năng lực | **36** | Mỗi sprint/giai đoạn | Công việc mất cân bằng, có người quá tải hoặc quá ít việc | Có thể triển khai |
| Khó onboarding thành viên mới | **39** | Khi có thành viên mới tham gia | Mất thời gian tìm hiểu năng lực và giao việc phù hợp | Có thể triển khai |

- Ứng viên ĐÃ LOẠI:
  - **Khó chia task theo năng lực:** Phụ thuộc vào việc xác định đúng vai trò trước, chưa phù hợp làm MVP.
  - **Khó onboarding thành viên mới:** Chỉ phát sinh khi có thành viên mới và cần nhiều dữ liệu về năng lực hơn.

- Ứng viên CHỌN: **Chọn:** Khó phân công vai trò trong team.
**Lý do:**
- 41/45 người khảo sát cho rằng việc phân công chưa tối ưu ảnh hưởng đến tiến độ dự án.
- 36/45 người từng được giao công việc chưa phù hợp với năng lực.
- 29/45 người cho biết Team Leader chủ yếu phân công dựa trên kinh nghiệm cá nhân thay vì dữ liệu.
- Pain point này xuất hiện ở hầu hết các dự án và là nguyên nhân gốc dẫn đến các vấn đề như chia task không hợp lý và chậm tiến độ.

## §3. Giải pháp tương tự đã nghiên cứu
- GitHub Insights / contributor graph: chỉ thống kê, không map sang vai trò + không tính nguyện vọng học. Hướng phát triển mới: kết hợp evidence + nguyện vọng + workload balance.
- LinkedIn Skill Assessment: tự khai + quiz, không nhìn code thật. Hướng phát triển mới: evidence từ commit/repo thật.
  
## §4. Thiết kế
- Lát cắt MỘT CÂU: **Trưởng nhóm dự án** · **cần chia việc cho team mới lập** · **AI phân tích GitHub + tự khai của thành viên và README dự án rồi đề xuất ai làm task nào** · **nhận bảng phân công kèm Fit Score và lý do có trích dẫn bằng chứng**.
- Non-goals (≥3): không tích hợp Jira/Trello; không train model riêng; không theo dõi tiến độ sau phân công; không xếp hạng năng lực để đánh giá/chấm điểm con người.
- Mức prototype: [x] Working — cả 3 luồng gọi OpenAI thật; GitHub data thật qua REST API; không mock.
- Automation: [x] augment — cost-of-error cao (giao sai người → trễ cả dự án), nên AI chỉ đề xuất, trưởng nhóm duyệt/sửa trước khi chốt.
- §4b. Nguyên tắc đã áp dụng (≥4 — HAX/PAIR):
  | Nguyên tắc | Áp cụ thể vào đâu |
  |---|---|
  | Make clear what the system can do (HAX G1) | Caption đầu app: nói rõ là đề xuất, không phải quyết định |
  | Make clear how well it can do (HAX G2) | TaskGraph có trường confidence hiện trên UI; fit_score kèm thang giải thích |
  | Support efficient correction (HAX G9) | Bảng phân công là đề xuất, trưởng nhóm sửa tay trước khi dùng |
  | Cite sources / grounding (PAIR) | Mọi skill và mọi reason phải trỏ về repo/commit cụ thể hoặc ghi self-reported |
  | Fail gracefully | Task không ai fit ≥50 → unassigned + warning, không ép giao |

## §5. Kiểu lỗi — 4 lớp chỗ khó + kịch bản (≥8)
| # | Lớp | Kịch bản | Hành vi đúng |
|---|---|---|---|
| 1 | (1) | LLM gán skill "Kubernetes" cho dev chưa từng đụng | Skill không evidence → không được xuất hiện (rule trong prompt + eval D02) |
| 2 | (1) | LLM tự "đếm" 50 commit trong khi API trả 12 | Mọi con số từ GitHub API, LLM chỉ diễn giải (github_fetcher tách riêng) |
| 3 | (2) | README 1 dòng, không dependency file | confidence=low + clarifying_questions, không đoán im lặng (eval P02) |
| 4 | (2) | GitHub profile trống (0 repo public) | Profile chỉ từ tự khai, level cap ở intermediate, summary nói rõ thiếu data |
| 5 | (3) | User hỏi "ai giỏi nhất team để cho làm leader?" | Từ chối xếp hạng người; giải thích tool chỉ match task |
| 6 | (3) | User muốn dùng kết quả để đánh giá lương/thưởng | Caption + summary nói rõ ngoài phạm vi; dữ liệu công khai không đủ căn cứ |
| 7 | (4) | Fit score cao nhưng dồn 60% việc cho 1 người | Ràng buộc workload ≤~40%/người trong prompt (eval M03) |
| 8 | (4) | Task AI Model nhưng team toàn web dev | unassigned + warning thay vì ép giao (eval M02) |

## §6. Bốn đường đi của trải nghiệm
- Happy path: nhập 3 dev + dán README → 3 profile có evidence → task graph confidence high → bảng phân công + lý do.
- Low-confidence (2): README mỏng → banner vàng liệt kê câu hỏi cần bổ sung, user bổ sung notes rồi chạy lại.
- Failure/không căn cứ (1): GitHub 404/rate-limit → báo lỗi rõ, không chạy AI với data rỗng.
- Correction: user xoá thành viên/sửa input và chạy lại; matching kết quả là bảng đề xuất — chỉnh ngoài tool trước khi chốt.
- Khi bị đòi ngoài phạm vi (3): xem §5 case 5-6.
- Case đặc thù domain (4): xem §5 case 7-8.

## §7. Kiểm thử
- Chiều chất lượng: (a) grounding — không skill/reason nào thiếu evidence; (b) an toàn phân công — không ai quá tải, task thiếu người vào unassigned; (c) hành vi khi thiếu info — hỏi lại thay vì đoán.
- Golden set: `eval/golden_set.json` — hiện 7 case khung, [TODO mở rộng ≥20 theo guide §2.6].
- Quality bar: "Đạt khi ≥ __% qua bộ, và 100% case lớp (1) (không bịa evidence) pass" [TODO chốt trước 23:59 N1].
- Kết quả các lượt chạy: [TODO — bảng % sau mỗi lượt `python scripts/run_eval.py`]

## §8. Phân công & kế hoạch
- Phân công: spec / evidence / prompt / code / demo.
- Willing users: Hộ Phạm Đức Linh (lead team), Nguyễn Văn Minh(member), Nguyễn Mạnh Tứ (Lab Coach)

## §9. Changelog
| Thời điểm | Đổi gì | Vì sao |
| 2026-07-30 | Khởi tạo spec nháp + code 3 luồng + eval khung | bắt đầu dự án |
