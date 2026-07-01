"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RUN_PIPELINE.PY — Điều phối toàn bộ quy trình sản xuất video
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Chạy lệnh:
    python run_pipeline.py                  # Chạy toàn bộ pipeline từ đầu
    python run_pipeline.py --stage 2        # Chạy từ giai đoạn cụ thể (1-6)
    python run_pipeline.py --project "tên"  # Tiếp tục một dự án đã có
"""

import sys
import os

# Đảm bảo console luôn sử dụng encoding UTF-8 để tránh lỗi charmap trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import json
import argparse
import re

# Đảm bảo import config và modules từ đúng đường dẫn
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules.script_generator import generate_topics, select_topic, generate_script
from modules.audio_generator import generate_audio
from modules.prompt_generator import generate_image_prompts
from modules.image_downloader import download_images, check_images_ready
from modules.video_compiler import compile_video


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIỆN ÍCH HIỂN THỊ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def print_banner():
    """Hiển thị banner khởi động."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎬  DOODLE VIDEO AUTOMATION PIPELINE  🎬                   ║
║                                                              ║
║   Tự động hóa sản xuất video hoạt hình người que             ║
║   lịch sử tiền sử — từ ý tưởng đến video thành phẩm         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_stage(stage_num: int, title: str):
    """Hiển thị tiêu đề cho từng giai đoạn."""
    icons = {1: "💡", 2: "📝", 3: "🔊", 4: "🎨", 5: "🖼️", 6: "🎬"}
    icon = icons.get(stage_num, "▶")
    print(f"\n{'━' * 60}")
    print(f"  {icon}  GIAI ĐOẠN {stage_num}: {title}")
    print(f"{'━' * 60}\n")


def print_success(message: str):
    """Hiển thị thông báo thành công."""
    print(f"\n  ✅  {message}\n")


def print_warning(message: str):
    """Hiển thị cảnh báo."""
    print(f"\n  ⚠️  {message}\n")


def print_info(message: str):
    """Hiển thị thông tin."""
    print(f"  ℹ️  {message}")


def sanitize_dirname(title: str) -> str:
    """Chuyển tiêu đề thành tên thư mục an toàn."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '_', slug)
    slug = slug.strip('_')
    return slug[:80] if slug else "untitled_project"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CÁC GIAI ĐOẠN PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def stage_1_topic_selection() -> tuple[str, str]:
    """
    Giai đoạn 1: Tạo ý tưởng và chọn chủ đề.
    Returns: (topic_title, project_dir)
    """
    print_stage(1, "TẠO Ý TƯỞNG & CHỌN CHỦ ĐỀ")

    print("  Đang gọi Gemini để tạo 5 ý tưởng video viral...\n")
    topics = generate_topics()

    if not topics:
        print("  ❌  Không thể tạo ý tưởng. Kiểm tra API Key của bạn.")
        sys.exit(1)

    selected = select_topic(topics)
    topic_title = selected["title"]

    # Tạo thư mục dự án
    project_name = sanitize_dirname(topic_title)
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, project_name)
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "images"), exist_ok=True)

    # Lưu thông tin dự án
    project_info = {
        "topic_title": topic_title,
        "project_name": project_name,
        "project_dir": project_dir,
        "current_stage": 1,
        "tts_engine": config.TTS_ENGINE,
        "image_mode": config.IMAGE_MODE,
        "active_profile": config.ACTIVE_PROFILE_ID,
    }
    with open(os.path.join(project_dir, "project_info.json"), "w", encoding="utf-8") as f:
        json.dump(project_info, f, ensure_ascii=False, indent=2)

    print_success(f"Đã chọn chủ đề: \"{topic_title}\"")
    print_info(f"Thư mục dự án: {project_dir}")

    return topic_title, project_dir


def stage_2_script_generation(topic_title: str, project_dir: str, force: bool = False):
    """Giai đoạn 2: Viết kịch bản tường thuật."""
    print_stage(2, "VIẾT KỊCH BẢN TƯỜNG THUẬT")

    script_path = os.path.join(project_dir, "script.txt")
    if os.path.exists(script_path):
        print_info(f"Đã tìm thấy kịch bản cũ tại: {script_path}")
        if not force:
            overwrite = input("  Bạn muốn viết lại kịch bản? (y/n): ").strip().lower()
            if overwrite != 'y':
                print_info("Giữ nguyên kịch bản cũ, chuyển sang giai đoạn tiếp theo.")
                return
        else:
            print_info("Chế độ tự động (force=True): Ghi đè kịch bản cũ...")

    print(f"  Đang viết kịch bản cho: \"{topic_title}\"...")
    print("  (Quá trình này mất khoảng 30-60 giây)\n")

    script_text = generate_script(topic_title, project_dir)

    if script_text:
        word_count = len(script_text.split())
        print_success(f"Kịch bản hoàn thành! ({word_count} từ)")
        print_info(f"Đã lưu tại: {os.path.join(project_dir, 'script.txt')}")
        print(f"\n  --- Xem trước 200 ký tự đầu ---")
        print(f"  {script_text[:200]}...")
    else:
        print("  ❌  Lỗi khi tạo kịch bản. Vui lòng thử lại.")
        sys.exit(1)

    # Cập nhật stage
    _update_project_stage(project_dir, 2)


def stage_3_audio_generation(project_dir: str, force: bool = False):
    """Giai đoạn 3: Tạo giọng đọc và trích xuất mốc thời gian."""
    print_stage(3, "TẠO GIỌNG ĐỌC & TRÍCH XUẤT THỜI GIAN")

    # Đọc kịch bản
    script_path = os.path.join(project_dir, "script.txt")
    if not os.path.exists(script_path):
        print("  ❌  Không tìm thấy script.txt. Hãy chạy giai đoạn 2 trước.")
        sys.exit(1)

    voice_path = os.path.join(project_dir, "voice.mp3")
    if os.path.exists(voice_path):
        print_info(f"Đã tìm thấy file âm thanh cũ tại: {voice_path}")
        if not force:
            overwrite = input("  Bạn muốn tạo lại giọng đọc? (y/n): ").strip().lower()
            if overwrite != 'y':
                print_info("Giữ nguyên giọng đọc cũ, chuyển sang giai đoạn tiếp theo.")
                return
        else:
            print_info("Chế độ tự động (force=True): Tạo lại giọng đọc...")

    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read().strip()

    engine_name = config.TTS_ENGINE.upper()
    print(f"  Đang sử dụng engine: {engine_name}")
    if config.TTS_ENGINE == "edge-tts":
        print(f"  Giọng đọc: {config.EDGE_TTS_VOICE}")
    else:
        print(f"  Voice ID: {config.ELEVENLABS_VOICE_ID}")
    print("  (Quá trình này mất khoảng 30-90 giây)\n")

    audio_path, timing_data = generate_audio(script_text, project_dir)

    if audio_path and timing_data:
        print_success(f"Giọng đọc đã được tạo thành công!")
        print_info(f"File âm thanh: {audio_path}")
        print_info(f"Số câu đã timestamp: {len(timing_data)}")
        print_info(f"File timing: {os.path.join(project_dir, 'timing.json')}")

        # Hiển thị vài dòng mẫu
        print(f"\n  --- Xem trước mốc thời gian ---")
        for entry in timing_data[:5]:
            start = entry.get("start", 0)
            minutes = int(start) // 60
            seconds = start - (minutes * 60)
            text_preview = entry.get("text", "")[:60]
            print(f"  [{minutes:02d}:{seconds:05.2f}] {text_preview}...")
        if len(timing_data) > 5:
            print(f"  ... và {len(timing_data) - 5} câu nữa")
    else:
        print("  ❌  Lỗi khi tạo giọng đọc.")
        sys.exit(1)

    _update_project_stage(project_dir, 3)


def stage_4_prompt_generation(project_dir: str, force: bool = False):
    """Giai đoạn 4: Tạo prompt ảnh cho từng câu kịch bản."""
    print_stage(4, "TẠO PROMPT HÌNH ẢNH")

    prompts_path = os.path.join(project_dir, "prompts.json")
    if os.path.exists(prompts_path):
        print_info(f"Đã tìm thấy file prompts cũ tại: {prompts_path}")
        if not force:
            overwrite = input("  Bạn muốn tạo lại prompts? (y/n): ").strip().lower()
            if overwrite != 'y':
                print_info("Giữ nguyên prompts cũ, chuyển sang giai đoạn tiếp theo.")
                return
        else:
            print_info("Chế độ tự động (force=True): Tạo lại prompts...")

    timing_path = os.path.join(project_dir, "timing.json")
    if not os.path.exists(timing_path):
        print("  ❌  Không tìm thấy timing.json. Hãy chạy giai đoạn 3 trước.")
        sys.exit(1)

    print("  Đang tạo prompt hình ảnh cho từng câu kịch bản...")
    print("  (Quá trình này mất khoảng 1-3 phút tùy độ dài kịch bản)\n")

    prompts = generate_image_prompts(project_dir)

    if prompts:
        print_success(f"Đã tạo {len(prompts)} prompt hình ảnh!")
        print_info(f"File prompts (text): {os.path.join(project_dir, 'prompts.txt')}")
        print_info(f"File prompts (JSON): {os.path.join(project_dir, 'prompts.json')}")

        # Hiển thị 2 prompt mẫu
        print(f"\n  --- Xem trước prompt ---")
        for p in prompts[:2]:
            ts = p.get("timestamp", "00:00")
            prompt_text = p.get("prompt", "")[:120]
            print(f"  [{ts}] {prompt_text}...")
        if len(prompts) > 2:
            print(f"  ... và {len(prompts) - 2} prompt nữa")
    else:
        print("  ❌  Lỗi khi tạo prompt hình ảnh.")
        sys.exit(1)

    _update_project_stage(project_dir, 4)


def stage_5_image_generation(project_dir: str, force: bool = False):
    """Giai đoạn 5: Tải/tạo hình ảnh."""
    print_stage(5, "TẠO HÌNH ẢNH")

    prompts_path = os.path.join(project_dir, "prompts.json")
    if not os.path.exists(prompts_path):
        print("  ❌  Không tìm thấy prompts.json. Hãy chạy giai đoạn 4 trước.")
        sys.exit(1)

    # Kiểm tra xem ảnh đã có chưa
    all_ready, found, total = check_images_ready(project_dir)
    if all_ready and found > 0:
        print_success(f"Đã có đủ {found}/{total} ảnh trong thư mục images/!")
        if not force:
            skip = input("  Bạn muốn bỏ qua và dựng video luôn? (y/n): ").strip().lower()
            if skip == 'y':
                return
        else:
            print_info("Chế độ tự động (force=True): Đã đủ ảnh, bỏ qua tạo ảnh mới.")
            return
    elif found > 0:
        print_warning(f"Đã tìm thấy {found}/{total} ảnh. Còn thiếu {total - found} ảnh.")

    mode_name = config.IMAGE_MODE.upper()
    print(f"  Chế độ tạo ảnh: {mode_name}")

    if config.IMAGE_MODE == "export":
        print("  Đang xuất file prompts cho ImageFX...\n")
    else:
        print("  Đang tạo ảnh qua API (quá trình này có thể mất nhiều phút)...\n")

    result = download_images(project_dir)

    if config.IMAGE_MODE == "export":
        print_success("Đã xuất file prompts!")
        print_info(f"File prompts: {result}")
        print()
        print("  ┌──────────────────────────────────────────────────────────┐")
        print("  │  HƯỚNG DẪN TIẾP THEO:                                  │")
        print("  │                                                          │")
        print("  │  1. Mở file prompts đã xuất ở trên                      │")
        print("  │  2. Dùng ImageFX Automator Extension hoặc paste thủ công │")
        print("  │     vào https://aitestkitchen.withgoogle.com/tools/image-fx │")
        print("  │  3. Lưu ảnh vào thư mục images/ với tên 0.png, 1.png... │")
        print("  │  4. Khi đã có đủ ảnh, chạy lại với --stage 6            │")
        print("  │                                                          │")
        print("  └──────────────────────────────────────────────────────────┘")
        print()

        if force or not sys.stdin.isatty():
            print_info("Đang chờ bạn sinh và tải ảnh từ Chrome Extension (Doodle Video Automator)...")
            import time
            last_found = -1
            while True:
                all_ready, found, total = check_images_ready(project_dir)
                if found != last_found:
                    print(f"  [Tiến độ] Đã tải về {found}/{total} ảnh...")
                    last_found = found
                if all_ready and found > 0:
                    print_success(f"✓ Đã có đầy đủ {found}/{total} ảnh!")
                    break
                time.sleep(2)
            return

        # Hỏi người dùng muốn chờ hay tiếp tục
        wait = input("  Ảnh đã sẵn sàng trong thư mục images/? (y = tiếp tục dựng video / n = thoát): ").strip().lower()
        if wait != 'y':
            print_info("Thoát. Chạy lại với: python run_pipeline.py --stage 6 --project <tên>")
            sys.exit(0)
    else:
        if result:
            print_success(f"Đã tạo {len(result)} ảnh qua API!")
        else:
            print("  ❌  Lỗi khi tạo ảnh qua API.")
            sys.exit(1)

    _update_project_stage(project_dir, 5)


def stage_6_video_compilation(project_dir: str, force: bool = False):
    """Giai đoạn 6: Dựng video thành phẩm."""
    print_stage(6, "DỰNG VIDEO THÀNH PHẨM")

    # Kiểm tra ảnh
    all_ready, found, total = check_images_ready(project_dir)
    if not all_ready:
        print_warning(f"Chỉ tìm thấy {found}/{total} ảnh. Các ảnh thiếu sẽ được thay bằng placeholder.")
        if not force:
            cont = input("  Tiếp tục dựng video? (y/n): ").strip().lower()
            if cont != 'y':
                sys.exit(0)
        else:
            print_info("Chế độ tự động (force=True): Tiếp tục dựng video với ảnh thay thế...")

    print(f"  Cấu hình video:")
    print(f"    Độ phân giải: {config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT}")
    print(f"    FPS: {config.VIDEO_FPS}")
    print(f"    Wobble: {'Bật (cường độ ' + str(config.WOBBLE_INTENSITY) + ')' if config.WOBBLE_INTENSITY > 0 else 'Tắt'}")
    print()
    print("  Đang dựng video (quá trình này mất 2-10 phút)...\n")

    video_path = compile_video(project_dir)

    if video_path and os.path.exists(video_path):
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print_success(f"Video thành phẩm đã xuất!")
        print_info(f"File: {video_path}")
        print_info(f"Kích thước: {file_size_mb:.1f} MB")
        print()
        print("  ╔══════════════════════════════════════════════════════════╗")
        print("  ║                                                          ║")
        print("  ║   🎉  VIDEO ĐÃ HOÀN THÀNH!  🎉                         ║")
        print("  ║                                                          ║")
        print("  ║   Bước tiếp theo:                                        ║")
        print("  ║   1. Xem lại video thành phẩm                           ║")
        print("  ║   2. Chỉnh sửa thêm trong CapCut / Premiere nếu cần    ║")
        print("  ║   3. Tải lên YouTube với metadata đã tạo                ║")
        print("  ║                                                          ║")
        print("  ╚══════════════════════════════════════════════════════════╝")
    else:
        print("  ❌  Lỗi khi dựng video.")
        sys.exit(1)

    _update_project_stage(project_dir, 6)


def stage_7_youtube_upload(project_dir: str, force: bool = False):
    """Giai đoạn 7: Đăng video lên YouTube."""
    print_stage(7, "ĐĂNG VIDEO LÊN YOUTUBE")
    
    privacy = config._get_setting("YOUTUBE_PRIVACY", "public")
    print(f"  Đang chuẩn bị và đăng tải video lên YouTube ở chế độ: {privacy.upper()}")
    
    from modules.youtube_uploader import upload_video_sync
    success = upload_video_sync(project_dir, privacy=privacy)
    
    if success:
        print_success("Đăng video lên YouTube thành công!")
        _update_project_stage(project_dir, 7)
    else:
        print_error("Đăng video lên YouTube thất bại.")
        sys.exit(1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIỆN ÍCH DỰ ÁN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _update_project_stage(project_dir: str, stage: int):
    """Cập nhật giai đoạn hiện tại của dự án."""
    info_path = os.path.join(project_dir, "project_info.json")
    if os.path.exists(info_path):
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)
        info["current_stage"] = stage
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)


def find_project_dir(project_name: str) -> str | None:
    """Tìm thư mục dự án dựa trên tên."""
    output_dir = config.BASE_OUTPUT_DIR
    if not os.path.exists(output_dir):
        return None

    # Thử tìm trực tiếp
    direct = os.path.join(output_dir, project_name)
    if os.path.isdir(direct):
        return direct

    # Tìm theo từ khóa
    for entry in os.listdir(output_dir):
        full_path = os.path.join(output_dir, entry)
        if os.path.isdir(full_path) and project_name.lower() in entry.lower():
            return full_path

    return None


def list_projects():
    """Liệt kê tất cả các dự án."""
    output_dir = config.BASE_OUTPUT_DIR
    if not os.path.exists(output_dir):
        print("  Chưa có dự án nào.")
        return

    projects = []
    for entry in sorted(os.listdir(output_dir)):
        full_path = os.path.join(output_dir, entry)
        if os.path.isdir(full_path):
            info_path = os.path.join(full_path, "project_info.json")
            stage = "?"
            title = entry
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                    stage = info.get("current_stage", "?")
                    title = info.get("topic_title", entry)
            projects.append((entry, title, stage))

    if not projects:
        print("  Chưa có dự án nào.")
        return

    print("\n  📁  Danh sách dự án:\n")
    print(f"  {'Tên thư mục':<40} {'Giai đoạn':<12} {'Chủ đề'}")
    print(f"  {'─' * 40} {'─' * 12} {'─' * 40}")
    for name, title, stage in projects:
        stage_labels = {1: "1-Ý tưởng", 2: "2-Kịch bản", 3: "3-Âm thanh",
                        4: "4-Prompts", 5: "5-Ảnh", 6: "6-Hoàn thành",
                        7: "7-Đăng YouTube"}
        stage_label = stage_labels.get(stage, f"Stage {stage}")
        print(f"  {name:<40} {stage_label:<12} {title[:40]}")
    print()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CHẠY CHƯƠNG TRÌNH CHÍNH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(
        description="🎬 Doodle Video Automation Pipeline — Tự động hóa sản xuất video hoạt hình người que"
    )
    parser.add_argument(
        "--stage", type=int, choices=[1, 2, 3, 4, 5, 6, 7],
        help="Bắt đầu từ giai đoạn cụ thể (1-7)"
    )
    parser.add_argument(
        "--project", type=str,
        help="Tên thư mục dự án đã có (để tiếp tục từ giai đoạn chỉ định)"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Liệt kê tất cả các dự án đã tạo"
    )
    parser.add_argument(
        "--tts", type=str, choices=["edge-tts", "elevenlabs"],
        help="Chọn engine TTS (ghi đè config)"
    )
    parser.add_argument(
        "--image-mode", type=str, choices=["api", "export"],
        help="Chọn chế độ tạo ảnh (ghi đè config)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Tự động đồng ý / ghi đè các bước và không hỏi lại trên terminal"
    )
    parser.add_argument(
        "--single-stage", action="store_true",
        help="Chỉ chạy duy nhất giai đoạn chỉ định rồi thoát"
    )
    parser.add_argument(
        "--profile", type=str, default=None,
        help="Hồ sơ kênh DNA cần nạp (ví dụ: ancient_history)"
    )

    args = parser.parse_args()

    # Ghi đè config nếu có tham số dòng lệnh
    if args.tts:
        config.TTS_ENGINE = args.tts
    if args.image_mode:
        config.IMAGE_MODE = args.image_mode
    if args.profile:
        print_info(f"Nạp hồ sơ kênh DNA chỉ định từ CLI: '{args.profile}'")
        config.load_channel_profile(args.profile)

    # Hiển thị banner
    print_banner()

    # Liệt kê dự án
    if args.list:
        list_projects()
        return

    # Xác định điểm khởi đầu
    start_stage = args.stage or 1
    topic_title = None
    project_dir = None

    # Nếu có tên dự án, tìm thư mục
    if args.project:
        project_dir = find_project_dir(args.project)
        if not project_dir:
            print(f"  ❌  Không tìm thấy dự án: {args.project}")
            list_projects()
            sys.exit(1)

        # Đọc thông tin dự án
        info_path = os.path.join(project_dir, "project_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            topic_title = info.get("topic_title", "Unknown")
            print_info(f"Tiếp tục dự án: \"{topic_title}\"")
            print_info(f"Thư mục: {project_dir}")
            
            # Tự động nạp profile kênh tương ứng nếu chưa nạp qua CLI
            if not args.profile:
                project_profile = info.get("active_profile", "ancient_history")
                print_info(f"Tự động nạp hồ sơ kênh của dự án: '{project_profile}'")
                config.load_channel_profile(project_profile)
        else:
            topic_title = args.project
            print_info(f"Thư mục dự án: {project_dir}")

    # Kiểm tra API Key
    if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("\n  ❌  Chưa cấu hình GEMINI_API_KEY!")
        print("  Cách cấu hình:")
        print("    1. Mở file config.py")
        print("    2. Thay 'YOUR_GEMINI_API_KEY_HERE' bằng API Key thật")
        print("    3. Hoặc set biến môi trường: set GEMINI_API_KEY=your_key_here")
        print("\n  Lấy API Key miễn phí tại: https://aistudio.google.com/apikey\n")
        sys.exit(1)

    # ━━━ CHẠY TỪNG GIAI ĐOẠN ━━━

    try:
        # Giai đoạn 1: Chọn chủ đề
        if (start_stage == 1) or (not args.single_stage and start_stage <= 1):
            topic_title, project_dir = stage_1_topic_selection()
            if args.single_stage:
                sys.exit(0)

        # Kiểm tra project_dir đã có chưa
        if not project_dir:
            print("  ❌  Cần chỉ định dự án. Dùng --project <tên> hoặc bắt đầu từ --stage 1")
            sys.exit(1)

        # Giai đoạn 2: Viết kịch bản
        if (start_stage == 2) or (not args.single_stage and start_stage <= 2):
            if not topic_title:
                # Đọc từ project_info.json
                info_path = os.path.join(project_dir, "project_info.json")
                if os.path.exists(info_path):
                    with open(info_path, "r", encoding="utf-8") as f:
                        topic_title = json.load(f).get("topic_title", "Unknown Topic")
                else:
                    topic_title = os.path.basename(project_dir).replace("_", " ").title()
            stage_2_script_generation(topic_title, project_dir, force=args.force)
            if args.single_stage:
                sys.exit(0)

        # Giai đoạn 3: Tạo giọng đọc
        if (start_stage == 3) or (not args.single_stage and start_stage <= 3):
            stage_3_audio_generation(project_dir, force=args.force)
            if args.single_stage:
                sys.exit(0)

        # Giai đoạn 4: Tạo prompt ảnh
        if (start_stage == 4) or (not args.single_stage and start_stage <= 4):
            stage_4_prompt_generation(project_dir, force=args.force)
            if args.single_stage:
                sys.exit(0)

        # Giai đoạn 5: Tải/tạo ảnh
        if (start_stage == 5) or (not args.single_stage and start_stage <= 5):
            stage_5_image_generation(project_dir, force=args.force)
            if args.single_stage:
                sys.exit(0)

        # Giai đoạn 6: Dựng video
        if (start_stage == 6) or (not args.single_stage and start_stage <= 6):
            stage_6_video_compilation(project_dir, force=args.force)
            if args.single_stage:
                sys.exit(0)

        # Giai đoạn 7: Đăng video lên YouTube
        if (start_stage == 7) or (not args.single_stage and start_stage <= 7):
            stage_7_youtube_upload(project_dir, force=args.force)

    except KeyboardInterrupt:
        print("\n\n  ⏹  Pipeline bị dừng bởi người dùng.")
        if project_dir:
            print_info(f"Tiếp tục sau: python run_pipeline.py --project \"{os.path.basename(project_dir)}\"")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ❌  Lỗi không mong đợi: {e}")
        import traceback
        traceback.print_exc()
        if project_dir:
            print_info(f"Thử lại: python run_pipeline.py --project \"{os.path.basename(project_dir)}\" --stage <N>")
        sys.exit(1)


if __name__ == "__main__":
    main()
