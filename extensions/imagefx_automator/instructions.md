# HƯỚNG DẪN CÀI ĐẶT & SỬ DỤNG IMAGEFX AUTOMATOR

Tiện ích này giúp bạn **tự động hóa 100%** việc tạo hình ảnh hoạt hình người que trên Google ImageFX và tải trực tiếp về thư mục dự án Doodle Video trên máy tính.

---

## 🛠️ BƯỚC 1: Cài đặt Extension vào Chrome

Do đây là tiện ích nội bộ phát triển riêng cho Dashboard của bạn, bạn cần cài đặt dưới dạng **Developer Mode (Chế độ nhà phát triển)** theo các bước sau:

1. Mở trình duyệt Google Chrome (hoặc Microsoft Edge, Brave, v.v.).
2. Truy cập vào trang quản lý tiện ích bằng cách sao chép địa chỉ sau và dán vào thanh địa chỉ:
   ```text
   chrome://extensions/
   ```
3. Ở góc trên bên phải màn hình quản lý, bật nút **"Developer mode" (Chế độ nhà phát triển)**.
4. Bấm vào nút **"Load unpacked" (Tải tiện ích đã giải nén)** ở góc trên bên trái.
5. Chọn thư mục chứa extension này trên máy tính của bạn:
   * Đường dẫn thư mục: `D:\Youtube\extensions\imagefx_automator`
6. Bấm **Select Folder** (Chọn thư mục). Bạn sẽ thấy tiện ích **Doodle Video Automator** xuất hiện trong danh sách.

---

## 🎬 BƯỚC 2: Sử dụng để sinh ảnh tự động

1. Đảm bảo rằng **Dashboard** của bạn đang chạy ở địa chỉ `http://127.0.0.1:8085` và dự án bạn muốn sinh ảnh đang được mở.
2. Truy cập vào trang web **Google ImageFX**:
   [https://aitestkitchen.withgoogle.com/tools/image-fx](https://aitestkitchen.withgoogle.com/tools/image-fx)
3. Đăng nhập tài khoản Google của bạn (nếu được yêu cầu).
4. Bạn sẽ thấy một bảng điều khiển nhỏ màu đen bóng mờ mang tên **🎨 ImageFX Automator** xuất hiện ở góc trên bên phải màn hình ImageFX.
5. Trên bảng điều khiển:
   * Địa chỉ mặc định là `http://127.0.0.1:8085`. Bấm **"Kết nối"**.
   * Bảng điều khiển sẽ hiển thị tên dự án và danh sách tất cả prompts của video.
6. Cách thức hoạt động:
   * **Tự động hóa 100%:** Hệ thống tự động điền prompt, bấm sinh ảnh, chờ khi ảnh tạo xong, tự động kiểm tra đối khớp từ khóa ảnh, tải lên Dashboard, sau đó tự nhảy sang prompt tiếp theo cho đến khi hoàn tất.
   * **Nút "Thử lại" (Retry):** Nếu bạn thấy cụm ảnh sinh ra bị lỗi hoặc không đẹp, bấm nút **"Thử lại"** màu vàng trên bảng nổi. Tiện ích sẽ tạm dừng, xóa file lỗi cũ trên server, dán lại prompt và sinh mới cụm ảnh khác, sau đó tự chạy tiếp tục.
7. Bấm **"Bắt đầu chạy"** để khởi động quy trình!

---

## 💡 Lưu ý quan trọng
* Hãy đảm bảo tab Google ImageFX luôn hoạt động (active) trên màn hình để extension chạy trơn tru.
* Nếu nút Generate của Google ImageFX bị giới hạn hoặc hiển thị CAPTCHA, hãy bấm **"Dừng"** trên Extension, giải quyết thủ công và bấm **"Bắt đầu chạy"** lại từ prompt đó.
* Các ảnh được upload sẽ lưu trực tiếp vào thư mục dự án: `output/<tên_dự_án>/images/` dưới tên `0.png`, `1.png`, v.v... đúng định dạng đầu vào để dựng video!
