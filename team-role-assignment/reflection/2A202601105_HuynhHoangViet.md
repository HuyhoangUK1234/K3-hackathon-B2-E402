**Họ và tên:** Huỳnh Hoàng Việt
**Mã học viên:** 2A202601105
**Vai trò:** Backend Engineer / System Integrator (Trưởng nhóm)

## 1. Công việc đã thực hiện

- Khởi tạo kiến trúc dự án và xây dựng API bằng FastAPI (`server.py`).
- Viết luồng thực thi chính (`src/pipeline.py`), đóng vai trò như một "nhạc trưởng" gọi tuần tự các module từ việc kéo data, phân tích AI đến lúc trả kết quả.
- Hỗ trợ review code, xử lý conflict khi các thành viên push code lên nhánh chính (`git pull`, merge).

## 2. Khó khăn gặp phải

Trở ngại lớn nhất là việc tích hợp các luồng độc lập (LLM, Fetcher, Matcher) vào một pipeline thống nhất. Lúc đầu, luồng chạy tuần tự quá chậm (mất tới gần 20 giây để AI đọc xong mọi thứ). Bên cạnh đó, việc quản lý source code của 4 thành viên khác đôi khi gây ra conflict lớn.

## 3. Cách giải quyết & Bài học rút ra

Mình đã cấu trúc lại pipeline để một số thao tác gọi API (như fetch data GitHub của nhiều người) có thể chạy bất đồng bộ (async). Về mặt quản lý nhóm, mình nhận ra tầm quan trọng của việc chia module rạch ròi ngay từ đầu (mỗi người một file/folder riêng) để hạn chế tối đa Git conflict. Qua Hackathon này, kỹ năng hệ thống hóa và tư duy kiến trúc của mình đã tăng lên đáng kể.
