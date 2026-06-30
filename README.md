# 🎨 Doodle Video Automator (Trình tự động hóa sản xuất Video Hoạt hình Người que)

Hệ thống tự động hóa sản xuất video hoạt hình giải thích/học tập (YouTube Explainer) phong cách vẽ tay (doodle người que) từ ý tưởng ban đầu đến video hoàn thiện 100%.

## 🚀 Các tính năng chính

Hệ thống bao gồm 6 giai đoạn sản xuất khép kín:
1. **Giai đoạn 1: Lên ý tưởng & Kịch bản (Gemini API & Web Fallback)**
   * Tạo 5 ý tưởng chủ đề viral dựa trên từ khóa yêu cầu.
   * Tạo kịch bản chi tiết gồm danh sách các phân cảnh, lời thoại lồng tiếng và prompt hình ảnh tương ứng.
2. **Giai đoạn 2: Lồng tiếng & Phân tích khớp thời gian (Microsoft Edge TTS)**
   * Chuyển đổi lời thoại lồng tiếng sang file âm thanh chất lượng cao bằng giọng đọc tiếng Việt/tiếng Anh tự nhiên.
   * Phân tích khớp thời gian chi tiết từng từ (Word-level timing) để đồng bộ phụ đề và chuyển cảnh.
3. **Giai đoạn 3: Tối ưu hóa prompt vẽ tranh (Gemini Prompt Enhancer)**
   * Tự động dịch thuật và tinh chỉnh kịch bản hình ảnh sang prompts tiếng Anh chi tiết theo phong cách vẽ doodle độc đáo.
4. **Giai đoạn 4: Sinh ảnh tự động trên Google ImageFX (Chrome Extension)**
   * Extension tùy biến giúp điền kịch bản prompt vào ImageFX bằng CDP debugger.
   * Tải ảnh về tự động 100%, có cơ chế đối khớp từ khóa thông minh tránh tải nhầm/tải thiếu ảnh, hỗ trợ chạy song song 2 trình duyệt cùng lúc.
   * Tích hợp nút **"Thử lại"** (Retry) trên Extension để xóa ảnh cũ và sinh lại ảnh đẹp hơn ngay lập tức.
5. **Giai đoạn 5: Tải về & Đồng bộ hóa Dashboard**
   * Theo dõi tiến trình tải ảnh thời gian thực, đảm bảo đầy đủ tài nguyên hình ảnh trước khi render.
6. **Giai đoạn 6: Ghép video hoàn chỉnh (MoviePy Engine)**
   * Đồng bộ hình ảnh với giọng đọc dựa trên timing.
   * Tạo hiệu ứng vẽ hoạt hình doodle rung lắc nhẹ sinh động (wobble camera effect).
   * Tạo phụ đề Karaoke thời gian thực chạy mượt mà theo giọng lồng tiếng.

---

## 🛠️ Yêu cầu hệ thống & Cài đặt

1. **Yêu cầu môi trường:**
   * Python từ 3.10 trở lên.
   * Trình duyệt Google Chrome để chạy Extension sinh ảnh.
   * ffmpeg cài đặt sẵn trên hệ thống (để MoviePy ghép video).

2. **Cài đặt thư viện:**
   ```powershell
   pip install -r requirements.txt
   ```

---

## 🖥️ Hướng dẫn Khởi chạy

1. **Khởi chạy Giao diện Dashboard (Web UI):**
   ```powershell
   python dashboard.py
   ```
   * Truy cập giao diện quản trị tại địa chỉ: `http://127.0.0.1:8085`

2. **Cài đặt Chrome Extension (ImageFX Automator):**
   * Mở trình duyệt Chrome truy cập `chrome://extensions/`.
   * Bật **Developer Mode** (Chế độ nhà phát triển) ở góc trên bên phải.
   * Bấm **Load unpacked** (Tải tiện ích đã giải nén) và chọn thư mục: `D:\Youtube\extensions\imagefx_automator`.
   * Truy cập [Google ImageFX](https://aitestkitchen.withgoogle.com/tools/image-fx), bảng điều khiển sẽ xuất hiện ở góc phải màn hình, bấm **Kết nối** để nhận danh sách prompt sinh ảnh từ Dashboard.

---

## 📂 Cấu trúc thư mục dự án

```text
├── dashboard.py           # Web Server quản trị FastAPI
├── run_pipeline.py        # Tiến trình điều hướng chạy 6 giai đoạn
├── config.py              # Cấu hình hệ thống (API key, kích thước video, font)
├── requirements.txt       # Danh sách thư viện Python cần thiết
├── static/                # Mã nguồn giao diện Web Dashboard (HTML/JS/CSS)
├── extensions/            # Tiện ích mở rộng Chrome sinh ảnh tự động
└── modules/               # Các module xử lý logic nghiệp vụ
    ├── script_generator.py # Tạo kịch bản bằng Gemini
    ├── audio_generator.py  # Tạo giọng đọc TTS bằng Edge TTS
    ├── prompt_generator.py # Tối ưu hóa prompt vẽ tranh doodle
    ├── image_downloader.py # Đồng bộ ảnh ImageFX / Imagen API
    └── video_compiler.py   # Ghép video, tạo phụ đề & wobble effect
```
