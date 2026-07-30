**Họ và tên:** Nguyễn Duy Hải Bằng
**Mã học viên:** 2A202601225
**Vai trò:** Algorithm Engineer / Evaluator

## 1. Công việc đã thực hiện

- Lên ý tưởng và code thuật toán "Match" (ghép nối) giữa profile của lập trình viên và task của dự án để đưa ra Fit Score (`src/matcher.py`).
- Xây dựng bộ công cụ kiểm thử tự động (Smoke Test) và các script đánh giá (`scripts/run_eval.py`).
- Lập bảng Golden Set để làm tiêu chuẩn chấm điểm độ chính xác của AI (`eval/`).

## 2. Khó khăn gặp phải

Làm sao để lượng hóa độ phù hợp (Fit Score) một cách khách quan nhất? Ban đầu, AI cho điểm khá cảm tính và mọi lập trình viên đều được chấm 80-90% cho bất kỳ task nào, khiến thuật toán Matcher mất đi ý nghĩa phân loại. Đồng thời, việc viết script tự động so sánh kết quả AI với Golden Set cũng gặp khó vì text do AI sinh ra mỗi lần lại khác nhau một chút.

## 3. Cách giải quyết & Bài học rút ra

Mình đã tinh chỉnh lại prompt của phần Matcher, yêu cầu AI phải chấm điểm dựa trên một rubric khắt khe (ví dụ: chỉ có bằng chứng cụ thể mới được cộng điểm). Ở phần kiểm thử, thay vì so sánh text tuyệt đối (exact match), mình dùng một mô hình LLM khác (LLM-as-a-judge) để chấm điểm ngữ nghĩa so với Golden Set. Đây là bài học lớn đối với mình về cách thiết lập tư duy Observability và Đánh giá (Evaluation) trong các dự án ứng dụng LLM.
