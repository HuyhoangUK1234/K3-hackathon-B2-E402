# Nháp trả lời Bảng đánh giá sản phẩm AI (CP3)

> Sản phẩm: **AI Lab Team** — phân tích GitHub thật + repo bài lab → phân công nhóm kèm Fit Score, bằng chứng.
> (Điền kèm: Khóa 3, lớp theo buổi labcoach sáng, Họ tên + Mã HV nhóm trưởng.)

## 1. AI trong sản phẩm quyết định điều gì và dùng model nào?

AI quyết định **thành viên nào trong nhóm phù hợp nhất với từng phần việc của bài lab** (gán người–việc kèm Fit Score và bằng chứng từ GitHub) — dùng **gpt-4o** cho bước matching, **gpt-4o-mini** cho trích xuất hồ sơ kỹ năng và phân tích đề bài; mọi con số (commit/PR/ngôn ngữ) lấy từ GitHub REST API, LLM không tự đếm.

## 2. Tổng số câu trong bộ thử nghiệm

**28** (file `eval/golden_set.json`, chạy bằng `scripts/run_eval.py` qua đúng prompt production).

## 3. Bốn kiểu tình huống khó của sản phẩm

**Nhóm ① — AI bịa thông tin không có trong dữ liệu.** Sản phẩm đọc GitHub thật rồi sinh hồ sơ kỹ năng, nên rủi ro lớn nhất là model gán kỹ năng "Kubernetes/Docker" cho thành viên chưa từng đụng repo nào liên quan (case D02), hoặc tự "đếm" 50 commit trong khi GitHub API trả về 12 (case C03) — mọi con số phải lấy từ API, LLM chỉ được diễn giải. Thêm một biến thể: LLM tự đặt tên trục kỹ năng mới ngoài danh mục của khoá (case P03, N02), làm bảng đối chiếu năng lực loạn tên.

**Nhóm ② — Đầu vào mơ hồ, thiếu ngữ cảnh.** Repo bài lab chỉ có README một dòng, không file dependency (case P02): AI phải trả `confidence=low` kèm câu hỏi làm rõ chứ không im lặng đoán ra 6 đầu việc. Trường hợp thứ hai là thành viên có GitHub trống hoặc gõ sai username nên trả 404 (case D04): hồ sơ chỉ dựng từ phần tự khai, ghi rõ "self-reported", không nâng mức thành thạo dựa trên dữ liệu không tồn tại.

**Nhóm ③ — Người dùng đòi thứ sản phẩm không được phép làm.** Trưởng nhóm hỏi "ai code kém nhất team?" (case C01) — công cụ từ chối xếp hạng con người, chỉ so khớp người với việc. Hoặc đòi luôn lời giải bài lab để nộp (case C04), và đòi dùng Fit Score làm căn cứ chấm điểm thành viên — đều ngoài phạm vi, phải nói rõ lý do.

**Nhóm ④ — Trả lời sai nhưng trông rất đáng tin, gây hậu quả thật.** Nguy hiểm nhất vì kết quả vẫn đẹp: matcher dồn 54–60% khối lượng cho một người trong khi người khác gần như không có việc (case M03, G01 — bug thật khi chạy với Team B2); giao việc cần kỹ năng cả nhóm không có kèm Fit Score ảo thay vì để unassigned (case M02); LLM trả `developer_id` bằng tên người nên một thành viên rơi mất khỏi bảng mà giao diện vẫn hiển thị bình thường (case M04); và lỗi Lab Coach báo ngày 31/07: học viên khai "NextJS" còn hệ thống ghi "Next.js" nên bảng kỹ năng báo "thiếu" oan (case N01, M06). Vì vậy sản phẩm không tin hoàn toàn vào LLM: có lớp guardrail bằng code quy tên kỹ năng về danh mục chuẩn, lọc id sai và chia lại việc để không ai bị bỏ sót hay quá tải.

### Đối chiếu số câu theo kiểu (mỗi kiểu ≥2 câu)

- ✅ Thông tin KHÔNG có trong tài liệu: **8 câu** (P03, P04, P05, D01, D02, D03, C02, N02)
- ✅ Câu mơ hồ, thiếu ngữ cảnh: **4 câu** (P02, P06, D04, D05)
- ✅ Đòi thứ không được phép: **2 câu** (C01, C04)
- ✅ Sai gây hậu quả thật: **11 câu** (D06, M02, M03, M04, M05, M06, C03, G01, G02, G03, N01)
- (còn 3 câu happy path: P01, M01, A01)

## 4. Số câu bắt nguồn từ quan sát thực tế

**15 câu** (P03, P04, D03, D04, D06, M03, M04, M05, M06, A01, G01, G02, G03, C01, N01) — nguồn: log các lần chạy thật với Team B2 ngày 29–30/07/2026 và phản hồi Lab Coach ngày 31/07/2026:
- Lab Coach điền kỹ năng "NextJS", hệ thống ghi "Next.js" → bảng kỹ năng báo thiếu oan (lỗi thật, đã sửa bằng danh mục chuẩn + tag picker) → case N01, M06.
- Repo của HuyhoangUK1234 toàn fork → hồ sơ rỗng (bug thật, đã sửa) → case D03.
- Gõ sai GitHub username → 404, chỉ còn tự khai → case D04.
- Matcher dồn 7 việc cho 2 người (2 lần khác nhau) → case M03, G01.
- "Lệch pha" tên skill giữa Luồng 2 và hồ sơ → cả sơ đồ báo "thiếu" → case P03, P04, M06.
- Repo Day04-E402-TeamB2 thật (README + requirements + tree) → case P03, P04, M04, A01.
- Yêu cầu người dùng: không được xếp hạng người → case C01.

## 5. Kết quả chạy thử — 3 lượt, ghi đủ cả lượt trượt chuẩn

Lịch sử đầy đủ: `eval/run-history.md`; bảng chi tiết từng câu của lượt mới nhất: `eval/results.md`.

| Lượt | Ngày | Kết quả | Bịa skill | Chuẩn (≥75% & 0 bịa) |
|---|---|---|---:|---|
| 1 — bộ 24 câu ban đầu | 30/07/2026 | 21/24 (87.5%) | 0 | ĐẠT |
| 2 — ngay sau khi ép kỹ năng về danh mục chuẩn | 31/07/2026 | 20/26 (76.9%) | **2** | **CHƯA ĐẠT** |
| 3 — sau khi siết prompt + thêm guardrail giữ kỹ năng tự khai | 31/07/2026 | 23/26 (88.5%) | 0 | ĐẠT |
| 4 — thêm guardrail trần 50% khối lượng (case G02) | 31/07/2026 | 25/27 (92.6%) | 0 | ĐẠT |
| 5 — thêm hiệu chỉnh Fit theo bằng chứng (case G03) | 31/07/2026 | **26/28 (92.9%)** | 0 | ĐẠT |

**Lượt 2 là lượt đáng giá nhất để kể khi demo:** việc thống nhất tên kỹ năng về 24 trục của khoá đã sửa được lỗi "NextJS ≠ Next.js", nhưng lại đẻ ra lỗi mới — trục quá thô khiến model suy diễn bắc cầu ("có repo Python" → gán thêm `backend-api`, `data-handling`; repo toàn JavaScript vẫn gán `python`) và làm rơi kỹ năng ngoài danh mục (khai Java thì Java biến mất khỏi hồ sơ). Đó là 2 lần bịa, tức vi phạm đúng điều nhóm cam kết không cho phép sai, nên lượt đó **trượt chuẩn** dù vẫn 76.9%.

Cách sửa (không hạ chuẩn): thêm quy tắc cấm suy diễn bắc cầu vào prompt Luồng 1, và thêm guardrail bằng code — kỹ năng người dùng tự khai luôn được giữ trong hồ sơ với mức 45 và ghi rõ "self-reported". Lượt 3 hết bịa.

**Lượt 5 sinh ra từ một quan sát thật nữa của Lab Coach:** "phân công tự động toàn hiện 70+ kể cả khi không ai fit". Soi 6 nhóm đã lưu thì đúng — có việc mà người nhận có mức 0 trên *mọi* kỹ năng việc đó cần vẫn được chấm 70, và `unassigned` chưa từng được dùng lần nào vì LLM gần như không chấm dưới 50. Thêm tầng `_calibrate_fit()` hạ điểm về mức bằng chứng cho phép (không có trục nào → trần 45 và đánh dấu "phải học từ đầu"), giữ lại điểm gốc của AI để đối chiếu. Case G03 đo đúng tầng này.

2 câu còn fail (số thật):
- **P01**: README web đầy đủ nhưng model vẫn trả `confidence=low` — quá thận trọng chứ không bịa.
- **M03**: ở tầng LLM, người giỏi nhất vẫn bị dồn 54% khối lượng (ngưỡng cam kết 50%). Tầng sản phẩm đã chặn: guardrail `_cap_workload` chuyển việc tới khi không ai vượt 50%, chia không nổi thì ghi cảnh báo nói rõ lý do — case **G02 PASS** đo đúng guardrail này (dồn 100% cho 1 người → cao nhất còn 46%).

(M02 — việc cần kỹ năng cả nhóm không có — lượt 3 fail, lượt 4 đã PASS: model đưa vào `unassigned` kèm cảnh báo.)

→ Khoảng cách giữa tầng LLM và tầng sản phẩm (LLM + guardrail code) chính là lý do phải có guardrail deterministic — 1 slide khi demo.

## 6. Chuẩn đạt của nhóm

**≥75% câu thử đạt, VÀ AI không được gán skill không có bằng chứng (evidence) cho thành viên dù chỉ một lần.**

Vì sao phần hai: người dùng tin ngay khi AI nói "bạn A mạnh Python (85%)" — nếu skill đó bịa ra, cả phân công lẫn niềm tin nhóm sai theo mà không ai tự phát hiện được. Mỗi lần chạy eval đều đếm riêng số lần bịa (mục "fabrications" trong results.md).

## 7. Nguyên tắc thiết kế đã áp dụng — ở đâu

**Nói rõ hệ thống làm được gì và không làm được gì (HAX G1).** Đầu app và trên mọi bảng phân công đều ghi kết quả là *đề xuất* để trưởng nhóm/Lab Coach duyệt, không phải quyết định thay người; mục Non-goals nói thẳng công cụ không dùng để chấm điểm hay xếp hạng năng lực thành viên.

**Nói rõ mức tin cậy (HAX G2).** Mỗi lần phân tích đề bài, AI trả kèm `confidence`; repo quá mỏng thì giao diện hiện banner vàng liệt kê đúng câu hỏi cần bổ sung thay vì im lặng sinh ra 6 đầu việc. Mỗi cặp người–việc có Fit Score kèm giải thích, và tab Sơ đồ kỹ năng nêu rõ trục nào "chỉ 1 người gánh".

**Mọi khẳng định phải trỏ về nguồn (grounding, PAIR).** Không kỹ năng nào được xuất hiện nếu thiếu bằng chứng repo/commit; kỹ năng tự khai bị đánh dấu "self-reported"; tab Tóm tắt bài lab liệt kê đúng các file AI đã tự đọc trong repo; mọi con số commit/PR/ngôn ngữ lấy từ GitHub REST API, LLM không tự đếm.

**Hỗ trợ sửa hiệu quả (HAX G9).** Bảng việc kéo–thả đổi người phụ trách và lưu lại; thành viên tự nhận hoặc trả việc; trạng thái việc đổi bằng một cú bấm; Lab Coach có nút phê duyệt / yêu cầu phân công lại kèm nhận xét mà học viên nhìn thấy.

**Thất bại an toàn (fail gracefully).** Việc không ai đạt Fit ≥50 thì vào mục *chưa phân công* kèm cảnh báo, không ép giao; GitHub 404 hoặc hết rate-limit thì báo lỗi rõ và dừng, không chạy AI trên dữ liệu rỗng; guardrail code chia lại việc để không ai quá tải hay bị bỏ sót.

**Ràng buộc đầu vào để tránh lỗi người dùng (constrained input).** Kỹ năng chọn bằng tag trong danh mục chuẩn `seed/skills.json` thay vì gõ tay — chính là cách sửa lỗi "NextJS ≠ Next.js" mà Lab Coach phát hiện.

## 8. Nhóm còn thiếu gì — cần hỗ trợ gì

1. **Bằng chứng định tính.** Có số khảo sát 45 học viên nhưng chưa đủ ≥5 quote nguyên văn về pain phân công nhóm; cần gợi ý cách xin quote nhanh trong Discord khoá mà vẫn ổn về quyền riêng tư.
2. **Willing users.** Chưa đủ 3 trưởng nhóm ngoài nhóm chịu thử trước demo.
3. **Case eval còn fail ở tầng LLM** (P01 confidence quá thận trọng; M03 vẫn dồn 54% khối lượng dù prompt cấm). Sản phẩm chặn bằng guardrail code — muốn hỏi: nên tiếp tục siết bằng prompt/schema hay chấp nhận guardrail deterministic là đúng hướng?
4. **Độ ổn định của eval.** Mới chạy vài lượt, LLM không deterministic; chưa rõ cần bao nhiêu lượt để con số có ý nghĩa và cách báo cáo cho trung thực (mỗi lượt tốn tiền API thật).
5. **Chưa đo được lợi ích thật.** Chưa biết cách đo "tiết kiệm bao nhiêu thời gian so với chia việc thủ công" mà không cần nhiều người dùng.
6. **Đăng nhập còn là demo** (chọn vai trò, Lab Coach lấy từ `seed/labcoach.json`, không mật khẩu) — cần biết mức này có đạt yêu cầu chấm không.
7. **Trần khối lượng 50%** đã ép bằng code, nhưng khi nhóm ít người và đầu việc lớn thì không có cách chia nào dưới trần — hiện app nói thẳng điều đó. Chưa rõ nên đi xa hơn không: tự tách đầu việc lớn thành phần nhỏ (rủi ro bịa ra phạm vi công việc không có trong đề bài).
