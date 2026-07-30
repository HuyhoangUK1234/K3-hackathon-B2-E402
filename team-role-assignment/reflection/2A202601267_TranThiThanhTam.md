**Họ và tên:** Trần Thị Thanh Tâm
**Mã học viên:** 2A202601267
**Vai trò:** Frontend Developer

## 1. Công việc đã thực hiện

- Chịu trách nhiệm chính trong việc thiết kế và phát triển giao diện Web tương tác cho hệ thống phân công (`static/index.html`).
- Xây dựng file dữ liệu mẫu (`demo/`) để kiểm thử các luồng hiển thị trước khi ráp nối với Backend.
- Tối ưu hóa trải nghiệm người dùng (UX) khi xem danh sách task và Fit Score do AI trả về.

## 2. Khó khăn gặp phải

Ban đầu, việc hiển thị dữ liệu JSON lồng ghép phức tạp (từ kết quả trả về của AI) lên giao diện thuần HTML/JS khá khó khăn. Dữ liệu từ API đôi khi bị thiếu trường hoặc chậm do LLM xử lý lâu, gây ra hiện tượng giật lag trên UI.

## 3. Cách giải quyết & Bài học rút ra

Mình đã học được cách sử dụng các trạng thái loading (spinners) để báo cho người dùng biết AI đang xử lý. Đồng thời, phối hợp chặt chẽ với Việt (Backend) để thống nhất cấu trúc dữ liệu trả về, giúp việc parse JSON trên Frontend an toàn hơn, tránh lỗi `undefined`. Trải nghiệm làm việc với giao diện cho các sản phẩm AI đòi hỏi sự kiên nhẫn và khả năng xử lý bất đồng bộ tốt.
