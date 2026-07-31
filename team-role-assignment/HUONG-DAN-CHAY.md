# 📖 Hướng dẫn chạy AI Lab Team (cho người mới hoàn toàn)

Ứng dụng **AI Lab Team**: nhập tên + GitHub của các thành viên nhóm và link repo bài lab → AI tự đọc GitHub thật + README bài lab → đề xuất **ai làm phần nào**, kèm điểm phù hợp (Fit Score), bằng chứng, radar kỹ năng, và hệ thống ticket hỏi Lab Coach.

> Không cần biết lập trình vẫn chạy được — cứ làm đúng từng bước bên dưới.

---

## 1. Cần chuẩn bị gì?

| Thứ cần có | Để làm gì | Lấy ở đâu |
|---|---|---|
| **Python 3.10+** | Chạy ứng dụng | [python.org/downloads](https://www.python.org/downloads/) — khi cài nhớ tick ô **"Add Python to PATH"** |
| **OpenAI API key** | AI phân tích (bắt buộc) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) → Create new secret key |
| **GitHub token** | Đọc GitHub không bị giới hạn (nên có) | [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic) → không cần tick quyền gì → Generate |
| **Git** (nếu tải bằng lệnh) | Tải mã nguồn | [git-scm.com](https://git-scm.com/) — hoặc bấm nút **Code → Download ZIP** trên GitHub, khỏi cần Git |

---

## 2. Tải mã nguồn

**Cách 1 — dùng Git (khuyên dùng):** mở **Command Prompt** (bấm phím Windows, gõ `cmd`, Enter) rồi chạy:

```bash
git clone https://github.com/HuyhoangUK1234/K3-hackathon-B2-E402.git
cd K3-hackathon-B2-E402\team-role-assignment
```

**Cách 2 — không dùng Git:** vào trang GitHub của repo → nút xanh **Code** → **Download ZIP** → giải nén → mở Command Prompt tại thư mục `team-role-assignment` (vào thư mục đó trong File Explorer, gõ `cmd` vào thanh địa chỉ, Enter).

---

## 3. Cài đặt (chỉ làm 1 lần)

Chạy lần lượt từng dòng trong Command Prompt (đang đứng ở thư mục `team-role-assignment`):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

- Dòng 1: tạo "hộp riêng" chứa thư viện (venv) — không đụng gì tới máy bạn.
- Dòng 2: bật hộp đó lên (đầu dòng lệnh sẽ hiện `(.venv)`).
- Dòng 3: cài thư viện, chờ 1-2 phút.

> 💡 Trên Mac/Linux: thay dòng 2 bằng `source .venv/bin/activate`.

---

## 4. Điền chìa khóa API (bước quan trọng nhất)

1. Chép file mẫu thành file thật:
   ```bash
   copy .env.example .env
   ```
2. Mở file `.env` bằng Notepad, điền 2 dòng:
   ```
   OPENAI_API_KEY=sk-...key-cua-ban...
   GITHUB_TOKEN=ghp-...token-cua-ban...
   ```
   - `OPENAI_API_KEY`: **bắt buộc** — không có thì AI không phân tích được.
   - `GITHUB_TOKEN`: nên có — không có thì GitHub chỉ cho đọc 60 lượt/giờ, phân tích 4 người là gần hết.

> ⚠️ **Tuyệt đối không** gửi file `.env` cho ai hay đưa lên mạng — key này trừ tiền tài khoản của bạn.

---

## 5. Chạy ứng dụng

```bash
uvicorn server:app --port 8000
```

Thấy dòng `Uvicorn running on http://127.0.0.1:8000` là thành công. Mở trình duyệt vào:

👉 **http://localhost:8000**

Muốn tắt: bấm `Ctrl + C` trong Command Prompt.

> Lần sau chạy lại chỉ cần 2 lệnh: `.venv\Scripts\activate` rồi `uvicorn server:app --port 8000`.

---

## 6. Dùng như thế nào?

### 👤 Vai trò Học viên (người làm bài lab)

1. Màn đăng nhập → bấm **"Đăng nhập với vai trò Học viên"** (demo, không cần mật khẩu).
2. **Bước 1**: dán link repo bài lab (đã điền sẵn repo mẫu Day04 của Team B2). Chỉ cần repo — AI tự đọc README và các file cần thiết.
3. **Bước 2**: điền các thành viên — chỉ cần **tên + GitHub username** là đủ (đã điền sẵn 4 người Team B2 để thử, có thể xoá/sửa).
   - Muốn khai thêm năng lực thì bấm **+ Chọn** ở ô *Kỹ năng đang có* / *Kỹ năng muốn học* rồi tick trong danh mục chuẩn của khoá (24 kỹ năng, lấy từ `seed/skills.json`). **Không gõ tay** — chọn tag để tránh cảnh "NextJS" và "Next.js" bị coi là hai kỹ năng khác nhau.
   - Mỗi kỹ năng đã chọn có **thanh kéo mức thành thạo** (Mới học → Làm được cơ bản → Khá vững → Thành thạo). Khai bao nhiêu cũng được nhưng mức chỉ dựa trên lời tự khai bị **giới hạn 65/100** — muốn cao hơn thì phải có commit/repo chứng minh.
   - Công nghệ ngoài danh mục (Unity, Rust…) thì điền ở ô **Công nghệ khác**.
4. Bấm **"Đưa cho AI phân tích"** → chờ 1-2 phút (AI đọc GitHub thật + gọi OpenAI thật).
5. **Bước 3 — trước khi AI phân công**: app dừng lại, hiện **radar năng lực nhóm so với bài lab** và danh sách **kỹ năng cả nhóm còn hổng**. Với mỗi kỹ năng, chọn ai sẽ nhận học (người từng khai "muốn học" được gợi ý sẵn) rồi bấm **Phân công với lựa chọn này** — AI sẽ ưu tiên giao việc đó cho đúng người ấy. Không muốn chọn thì bấm **Bỏ qua, để AI tự quyết**.
6. Xem kết quả qua các tab:
   - **Tổng quan** — mặc định hiện gọn: ai làm phần nào + thanh % khối lượng. Cần xem sâu thì bấm **"Xem chi tiết"** để mở mô tả việc, cảnh báo của AI và bảng "Dự án cần gì — ai có?". Việc nào người nhận chưa có bằng chứng năng lực sẽ hiện chip đỏ **"⚠ phải học"** kèm ô cảnh báo riêng.
   - **Bảng việc** — kéo thẻ việc sang cột người khác để đổi người làm; bấm nhãn trạng thái để đổi *Chưa làm → Đang làm → Xong*. Dùng thay Jira cho nhóm nhỏ; thay đổi lưu cho cả nhóm và Lab Coach.
   - **Việc của tôi** — chọn mình là ai ở góc phải, xem việc còn trống để nhận hoặc trả lại việc.
   - **Tóm tắt bài lab** — AI tóm tắt đề bài + mục tiêu, liệt kê file đã tự đọc.
   - **Sơ đồ kỹ năng** — 2 chế độ: **Ma trận** (radar nhóm-so-với-bài-lab + bảng người × kỹ năng, kèm 4 con số: bài lab cần bao nhiêu trục, bao nhiêu trục đã đủ người, trục nào chỉ 1 người gánh, trục nào chưa ai làm được) và **Sơ đồ luồng** (đồ thị người → kỹ năng → việc).
   - Bấm vào thẻ thành viên ở Tổng quan để mở hồ sơ chi tiết: radar kỹ năng, số commit/PR thật, bằng chứng cho từng kỹ năng.
   - **🛟 Tickets** — bấm **Raise Ticket** khi kẹt, Lab Coach sẽ thấy và trả lời.
   - **💬 Trợ lý AI** (nút tròn góc dưới phải) — nhớ được các lượt hỏi trước trong cùng phiên nên hỏi nối tiếp kiểu "còn người đó thì sao?" vẫn hiểu; bấm **Hội thoại mới** để xoá bộ nhớ. Trợ lý chỉ trả lời dựa trên dữ liệu đang hiển thị, không có dữ liệu thì nói thẳng là không có.

### 🛡️ Vai trò Lab Coach (người hướng dẫn)

1. Đăng nhập **Lab Coach** (hoặc gạt nút chuyển vai trò trên thanh trên cùng).
2. **Danh sách nhóm lab** — mọi nhóm đã phân tích: vòng tròn tỉ lệ cân bằng (xanh >70% / vàng 50-70% / đỏ <50%), điểm fit. Bấm vào nhóm để xem chi tiết, rồi bấm **"Đánh giá từ Coach"** để phê duyệt / yêu cầu phân công lại + ghi nhận xét (học viên sẽ thấy).
3. **Tickets hỗ trợ** — lọc Chưa xong/Đã xong, bấm dấu ✓ để đánh dấu xong nhanh, hoặc bấm vào ticket để viết phản hồi.

---

## 7. (Tuỳ chọn) Chạy bộ kiểm thử chất lượng AI

```bash
python scripts/run_eval.py
```

Chạy 26 câu thử (có tình huống bẫy: dữ liệu thiếu, câu mơ hồ, đòi xếp hạng người, đòi đáp án, tên kỹ năng viết lệch...) qua đúng AI của sản phẩm, in PASS/FAIL từng câu và ghi bảng vào `eval/results.md`. Chuẩn đạt của nhóm: **≥75% và AI không được bịa skill không có bằng chứng lần nào**.

Chạy một câu lẻ (không tốn nhiều lượt gọi API): `python scripts/run_eval.py N01 N02 G01`.

---

## 8. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách sửa |
|---|---|---|
| `python` không nhận lệnh | Chưa cài Python / quên tick "Add to PATH" | Cài lại Python, tick **Add Python to PATH** |
| Cảnh báo "GitHub API bị rate limit" | Chưa có `GITHUB_TOKEN` trong `.env` | Tạo token (mục 1), điền vào `.env`, **tắt app chạy lại** |
| Phân tích thất bại, báo lỗi key | `OPENAI_API_KEY` sai/thiếu | Kiểm tra lại `.env`, key phải bắt đầu bằng `sk-` |
| Sửa `.env` rồi vẫn lỗi | App chỉ đọc `.env` lúc khởi động | `Ctrl+C` tắt app, chạy lại `uvicorn server:app --port 8000` |
| Port 8000 bận | Có app khác đang chiếm | Đổi lệnh thành `--port 8080` rồi vào `localhost:8080` |
| Thành viên 0 commit, không skill | GitHub username sai chính tả | Kiểm tra lại username trên github.com |
| Chữ tiếng Việt trong cửa sổ lệnh bị lỗi | Bảng mã Windows | Kệ nó — chỉ là log, giao diện web vẫn hiển thị đúng |

---

## 9. Ứng dụng hoạt động ra sao? (đọc thêm)

```
Bạn điền: tên + GitHub username + link repo bài lab
        │
        ▼
[Luồng 1] Đọc GitHub THẬT từng người (commit, PR, ngôn ngữ — số liệu từ API, AI không tự đếm)
        → hồ sơ kỹ năng, mỗi skill kèm bằng chứng, không có bằng chứng thì không được ghi
        │
[Luồng 2] AI agent tự đọc README + chọn file .md cần thiết trong repo
        → tóm tắt bài lab + danh sách phần việc (Task Graph)
        │
[Dừng lại hỏi người] Kỹ năng nào cả nhóm còn hổng? Ai nhận học phần đó?
        → quyết định của nhóm được đưa vào bước ghép, AI không tự quyết thay
        │
[Luồng 3] Ghép người × việc → Fit Score + lý do trích dẫn bằng chứng
        → guardrail bằng code: ai cũng có việc; không ai giữ quá 50% khối lượng
          (chia không nổi thì nói thẳng lý do chứ không giấu)
        → hiệu chỉnh Fit theo bằng chứng thật: người nhận không có kỹ năng việc đó
          cần thì điểm bị hạ xuống dưới 50 và việc bị đánh dấu "phải học từ đầu",
          kèm điểm gốc AI đã chấm để đối chiếu
        │
        ▼
Kết quả chỉ là ĐỀ XUẤT — nhóm trưởng/Lab Coach duyệt và chỉnh mới chốt.
```

Nguyên tắc an toàn: thiếu dữ liệu thì AI **hỏi lại** chứ không đoán; không xếp hạng "ai giỏi hơn ai"; mọi con số đều từ GitHub thật.
