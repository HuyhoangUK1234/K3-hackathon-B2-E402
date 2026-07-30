# Nháp trả lời Bảng đánh giá sản phẩm AI (CP3)

> Sản phẩm: **AI Lab Team** — phân tích GitHub thật + repo bài lab → phân công nhóm kèm Fit Score, bằng chứng.
> (Điền kèm: Khóa 3, lớp theo buổi labcoach sáng, Họ tên + Mã HV nhóm trưởng.)

## 1. AI trong sản phẩm quyết định điều gì và dùng model nào?

AI quyết định **thành viên nào trong nhóm phù hợp nhất với từng phần việc của bài lab** (gán người–việc kèm Fit Score và bằng chứng từ GitHub) — dùng **gpt-4o** cho bước matching, **gpt-4o-mini** cho trích xuất hồ sơ kỹ năng và phân tích đề bài; mọi con số (commit/PR/ngôn ngữ) lấy từ GitHub REST API, LLM không tự đếm.

## 2. Tổng số câu trong bộ thử nghiệm

**24** (file `eval/golden_set.json`, chạy bằng `scripts/run_eval.py` qua đúng prompt production).

## 3. Bộ câu thử có đủ 4 kiểu tình huống? (mỗi kiểu ≥2 câu)

- ✅ Thông tin KHÔNG có trong tài liệu — xem AI có bịa không: **6 câu** (P03, P05, D01, D02, D03, C02)
- ✅ Câu mơ hồ, thiếu ngữ cảnh — hỏi lại hay đoán bừa: **4 câu** (P02, P06, D04, D05)
- ✅ Đòi thứ sản phẩm không được phép làm: **2 câu** (C01 xếp hạng "ai code kém nhất", C04 đòi lời giải bài lab để nộp)
- ✅ Trả lời sai gây hậu quả thật: **6 câu** (M02 giao việc cho người không đủ skill, M03/M05 dồn việc–fit ảo, D06 skill ngoài dữ liệu, C03 sai số commit, G01 guardrail cân bằng)

## 4. Số câu bắt nguồn từ quan sát thực tế

**12 câu** (P03, P04, D03, D04, D06, M03, M04, M05, M06, A01, G01, C01) — nguồn: log các lần chạy thật với Team B2 ngày 29–30/07/2026:
- Repo của HuyhoangUK1234 toàn fork → hồ sơ rỗng (bug thật, đã sửa) → case D03.
- Gõ sai GitHub username → 404, chỉ còn tự khai → case D04.
- Matcher dồn 7 việc cho 2 người (2 lần khác nhau) → case M03, G01.
- "Lệch pha" tên skill giữa Luồng 2 và hồ sơ → cả sơ đồ báo "thiếu" → case P03, P04, M06.
- Repo Day04-E402-TeamB2 thật (README + requirements + tree) → case P03, P04, M04, A01.
- Yêu cầu người dùng: không được xếp hạng người → case C01.

## 5. Kết quả chạy thử lần đầu

**21/24** (87.5%) — chạy 30/07/2026, bảng đầy đủ kể cả câu fail: `eval/results.md`. Số lần bịa skill không bằng chứng: **0**.

3 câu fail (số thật, phân tích cho slide demo):
- **P01**: README web đầy đủ nhưng model trả `confidence=low` — quá thận trọng chứ không bịa; cần nới rule confidence trong prompt.
- **M03**: 1 người giỏi nhất vẫn bị dồn 54% khối lượng (ngưỡng 50%) — LLM chưa tuân thủ hết ràng buộc cân bằng ở tầng prompt.
- **M04**: LLM trả `developer_id` bằng tên thay vì id → 1 thành viên 0 việc ở tầng LLM. Ở sản phẩm thật, tầng code đã có guardrail: lọc id sai + `_rebalance` tự chia lại (case G01 PASS chứng minh guardrail chạy; lần chạy end-to-end thật cùng ngày ai cũng có việc).

→ Khoảng cách giữa tầng LLM (21/24) và tầng sản phẩm (LLM + guardrail code) chính là lý do sản phẩm cần guardrail deterministic — nội dung 1 slide khi demo.

## 6. Chuẩn đạt của nhóm

**≥75% câu thử đạt, VÀ AI không được gán skill không có bằng chứng (evidence) cho thành viên dù chỉ một lần.**

Vì sao phần hai: người dùng tin ngay khi AI nói "bạn A mạnh Python (85%)" — nếu skill đó bịa ra, cả phân công lẫn niềm tin nhóm sai theo mà không ai tự phát hiện được. Mỗi lần chạy eval đều đếm riêng số lần bịa (mục "fabrications" trong results.md).
