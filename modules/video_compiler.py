"""
=============================================================
  VIDEO_COMPILER.PY — Ghép video cuối cùng từ ảnh + audio
=============================================================
Sử dụng FFmpeg C-core trực tiếp để tạo video siêu tốc, kết hợp
hiệu ứng rung lắc (wobble) bằng toán học trên bộ lọc crop.
"""

import sys
import os
import json
import tempfile
import logging
import subprocess
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

# ── Thêm thư mục gốc project vào sys.path để import config ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

import imageio_ffmpeg
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# ── Logger ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TIỀN XỬ LÝ ẢNH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def preprocess_image_for_ffmpeg(
    image_path: str,
    target_w: int,
    target_h: int,
    padding: int
) -> str:
    """
    Resize và pad ảnh bằng Pillow một lần duy nhất trước khi đưa vào FFmpeg.
    """
    try:
        img = Image.open(image_path).convert("RGB")
        src_w, src_h = img.size

        # Scale cover
        padded_w = target_w + padding * 2
        padded_h = target_h + padding * 2
        
        scale = max(padded_w / src_w, padded_h / src_h)
        new_w = int(src_w * scale)
        new_h = int(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center-crop
        left = (new_w - padded_w) // 2
        top = (new_h - padded_h) // 2
        img = img.crop((left, top, left + padded_w, top + padded_h))

        # Lưu tạm
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="vid_img_")
        os.close(tmp_fd)
        img.save(tmp_path, "PNG")

        return tmp_path

    except Exception as exc:
        logger.error("Lỗi tiền xử lý ảnh %s: %s", image_path, exc)
        raise

def create_placeholder_image(
    text: str,
    target_w: int,
    target_h: int,
    output_path: str,
) -> str:
    try:
        img = Image.new("RGB", (target_w, target_h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        font_size = 40
        font: Optional[ImageFont.FreeTypeFont] = None
        for font_name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()

        max_chars_per_line = target_w // (font_size // 2 + 2)
        lines: List[str] = []
        words = text.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) <= max_chars_per_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        line_height = font_size + 10
        total_text_h = line_height * len(lines)
        y_start = (target_h - total_text_h) // 2

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (target_w - text_w) // 2
            y = y_start + i * line_height
            draw.text((x, y), line, fill=(224, 48, 43), font=font)

        img.save(output_path, "PNG")
        return output_path

    except Exception as exc:
        logger.error("Lỗi tạo placeholder: %s", exc)
        raise

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GHÉP VIDEO CHÍNH (PURE FFMPEG)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compile_video(project_dir: str) -> str:
    """
    Sử dụng FFmpeg trực tiếp để xử lý video nhanh gấp 10-20 lần.
    """
    logger.info("Bắt đầu compile_video cho project: %s", project_dir)

    timing_path = os.path.join(project_dir, "timing.json")
    voice_path = os.path.join(project_dir, "voice.mp3")
    images_dir = os.path.join(project_dir, "images")
    output_path = os.path.join(project_dir, "final.mp4")

    if not os.path.isfile(timing_path):
        raise FileNotFoundError(f"Không tìm thấy file: {timing_path}")
    if not os.path.isfile(voice_path):
        raise FileNotFoundError(f"Không tìm thấy file: {voice_path}")

    # Cấu hình video
    target_w = config.VIDEO_WIDTH
    target_h = config.VIDEO_HEIGHT
    wobble = config.WOBBLE_INTENSITY

    with open(timing_path, "r", encoding="utf-8") as f:
        sentences = json.load(f)

    if not sentences:
        raise ValueError("timing.json rỗng, không có dữ liệu để ghép video.")

    temp_files = []
    video_segments = []

    try:
        padding = wobble + 15 if wobble > 0 else 0

        # Tính toán ffmpeg crop expression cho hiệu ứng wobble
        # (Chạy real-time bằng C core của FFmpeg)
        crop_expr = f"crop={target_w}:{target_h}:x='(iw-ow)/2 + {wobble}*sin(2*PI*t/1.7 + 0.3)':y='(ih-oh)/2 + {wobble}*cos(2*PI*t/2.3 + 0.7)'"
        if wobble <= 0:
            crop_expr = f"crop={target_w}:{target_h}:(iw-ow)/2:(ih-oh)/2"

        logger.info("Đang xử lý tạo clip thành phần bằng FFmpeg...")

        for entry in sentences:
            idx = entry.get("index", 0)
            text = entry.get("text", "")
            start = float(entry.get("start", 0))
            end = float(entry.get("end", 0))
            duration = end - start

            if duration <= 0:
                logger.warning("Câu %d có duration <= 0, bỏ qua.", idx)
                continue

            img_path: Optional[str] = None
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                candidate = os.path.join(images_dir, f"{idx}{ext}")
                if os.path.isfile(candidate):
                    img_path = candidate
                    break

            if img_path is None:
                placeholder_path = os.path.join(images_dir, f"{idx}_placeholder.png")
                img_path = create_placeholder_image(text, target_w, target_h, placeholder_path)
                temp_files.append(placeholder_path)
                logger.warning("Dùng placeholder cho câu %d.", idx)

            # 1. Preprocess ảnh (resize & pad)
            processed_path = preprocess_image_for_ffmpeg(img_path, target_w, target_h, padding)
            temp_files.append(processed_path)

            # 2. Tạo đoạn video bằng FFmpeg
            fd_vid, seg_vid_path = tempfile.mkstemp(suffix=".mp4", prefix=f"seg_{idx}_")
            os.close(fd_vid)
            temp_files.append(seg_vid_path)

            cmd = [
                FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1",
                "-framerate", str(config.VIDEO_FPS),
                "-i", processed_path,
                "-t", str(duration),
                "-vf", crop_expr,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                seg_vid_path
            ]
            subprocess.run(cmd, check=True)
            video_segments.append(seg_vid_path)
            logger.info("  => Xong đoạn %d (%.2fs)", idx, duration)

        if not video_segments:
            raise RuntimeError("Không có clip nào được tạo.")

        # 3. Tạo file list concat
        fd_list, list_path = tempfile.mkstemp(suffix=".txt", prefix="concat_list_")
        os.close(fd_list)
        temp_files.append(list_path)

        with open(list_path, "w", encoding="utf-8") as f:
            for seg in video_segments:
                # Cần chuẩn hóa đường dẫn cho FFmpeg
                normalized_path = seg.replace('\\', '/')
                f.write(f"file '{normalized_path}'\n")

        # 4. Nối video và ghép âm thanh
        logger.info("Đang ghép các clip và trộn âm thanh thành video hoàn chỉnh...")
        concat_cmd = [
            FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-i", voice_path,
            "-c:v", "copy",       # Copy nguyên stream video đã render, siêu nhanh
            "-c:a", "aac",
            "-shortest",          # Cắt độ dài vừa bằng stream ngắn nhất (audio/video)
            output_path
        ]
        subprocess.run(concat_cmd, check=True)

        logger.info("✅ Hoàn thành! Video: %s", output_path)
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error("❌ Lỗi thực thi FFmpeg: %s", e)
        raise RuntimeError("Ghép video thất bại do lỗi FFmpeg.") from e
    except Exception as exc:
        logger.error("❌ Lỗi khi ghép video: %s", exc)
        raise RuntimeError(f"Ghép video thất bại: {exc}") from exc

    finally:
        # Dọn dẹp file tạm
        for tmp in temp_files:
            try:
                if os.path.isfile(tmp):
                    os.remove(tmp)
            except OSError:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST ĐỘC LẬP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import shutil

    test_project = os.path.join(config.BASE_OUTPUT_DIR, "_test_video_compiler")
    test_images = os.path.join(test_project, "images")
    os.makedirs(test_images, exist_ok=True)

    sample_timing = [
        {"index": 0, "text": "You wake up when your body is ready.", "start": 0.0, "end": 3.0},
        {"index": 1, "text": "No alarm. No schedule.", "start": 3.0, "end": 5.5},
        {"index": 2, "text": "For 99% of human history, this was normal.", "start": 5.5, "end": 9.0},
    ]
    with open(os.path.join(test_project, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(sample_timing, f, indent=2)

    create_placeholder_image(
        sample_timing[0]["text"],
        config.VIDEO_WIDTH,
        config.VIDEO_HEIGHT,
        os.path.join(test_images, "0.png"),
    )
    create_placeholder_image(
        sample_timing[2]["text"],
        config.VIDEO_WIDTH,
        config.VIDEO_HEIGHT,
        os.path.join(test_images, "2.png"),
    )

    # Dùng ffmpeg tạo audio tĩnh
    voice_path = os.path.join(test_project, "voice.mp3")
    try:
        subprocess.run([
            FFMPEG_EXE, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "9", "-loglevel", "quiet", voice_path
        ], check=True)
    except Exception:
        print("Không tạo được audio test.")

    print(f"Bắt đầu render test tại: {test_project}")
    try:
        out_path = compile_video(test_project)
        print(f"Thành công! Đường dẫn video test: {out_path}")
    except Exception as e:
        print(f"Lỗi: {e}")
