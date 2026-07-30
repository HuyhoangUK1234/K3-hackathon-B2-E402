**Họ và tên:** Nguyễn Văn Tiến
**Mã học viên:** 2A202601433
**Vai trò:** AI Engineer (LLM Core & Profile)

## 1. Công việc đã thực hiện

- Thiết lập module kết nối cốt lõi với OpenAI API (`src/llm.py`).
- Định nghĩa các Schema bằng Pydantic (`src/schemas.py`) để ép LLM trả về đúng định dạng JSON chuẩn xác.
- Viết prompt và luồng logic để AI đọc dữ liệu GitHub thô, bóc tách ra các kỹ năng (skills) và tính cách thực tế của developer (`src/dev_analyzer.py`).

## 2. Khó khăn gặp phải

LLM (cụ thể là các model GPT) thỉnh thoảng bị ảo giác (hallucination) hoặc trả về định dạng JSON bị hỏng (thiếu dấu phẩy, thiếu ngoặc). Hơn nữa, việc ép AI phải luôn luôn cung cấp "bằng chứng" (evidence) cho mỗi skill mà nó kết luận không hề đơn giản, đôi khi AI tự bịa ra bằng chứng không có trong data gốc.

## 3. Cách giải quyết & Bài học rút ra

Mình đã phải áp dụng Pydantic strict mode và bật tính năng JSON mode của OpenAI, kết hợp với cơ chế retry (thử lại 1-2 lần nếu parse JSON lỗi). Trong prompt, mình nhấn mạnh rule "Tuyệt đối không suy diễn, chỉ trích xuất từ dữ liệu đầu vào". Điều này giúp mình hiểu sâu sắc tầm quan trọng của Guardrails và Structured Output khi làm việc với Generative AI trong môi trường production.
