"""
=============================================================
  VIDEO_COMPILER.PY — Ghép video cuối cùng từ ảnh + audio
=============================================================
Sử dụng MoviePy v2 để tạo video từ các ảnh minh họa và file
giọng đọc, áp dụng hiệu ứng rung lắc (wobble) nhẹ.
"""

import sys
import os
import json
import math
import tempfile
import logging
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
)

# ── Thêm thư mục gốc project vào sys.path để import config ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ── Logger ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TIỀN XỬ LÝ ẢNH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def preprocess_image(
    image_path: str,
    target_w: int,
    target_h: int,
) -> str:
    """
    Mở ảnh, resize giữ tỷ lệ rồi center-crop về đúng kích thước đích.

    Args:
        image_path: Đường dẫn ảnh gốc.
        target_w:   Chiều rộng mong muốn (px).
        target_h:   Chiều cao mong muốn (px).

    Returns:
        Đường dẫn file ảnh đã xử lý (PNG, lưu trong thư mục tạm).
    """
    try:
        img = Image.open(image_path).convert("RGB")
        src_w, src_h = img.size

        # ── Tính tỷ lệ scale sao cho ảnh ≥ target (cover) ──
        scale = max(target_w / src_w, target_h / src_h)
        new_w = int(src_w * scale)
        new_h = int(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # ── Center-crop ──
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))

        # ── Lưu tạm ──
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="vid_img_")
        os.close(tmp_fd)
        img.save(tmp_path, "PNG")

        logger.info("Đã tiền xử lý ảnh: %s → %s (%dx%d)", image_path, tmp_path, target_w, target_h)
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
    """
    Tạo ảnh placeholder màu trắng với dòng chữ đỏ ở giữa.

    Args:
        text:       Nội dung câu (sentence) cần hiển thị.
        target_w:   Chiều rộng (px).
        target_h:   Chiều cao (px).
        output_path: Nơi lưu ảnh.

    Returns:
        output_path đã lưu.
    """
    try:
        img = Image.new("RGB", (target_w, target_h), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # ── Tìm font ──
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

        # ── Wrap text nếu quá dài ──
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

        # ── Vẽ text vào giữa ──
        line_height = font_size + 10
        total_text_h = line_height * len(lines)
        y_start = (target_h - total_text_h) // 2

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (target_w - text_w) // 2
            y = y_start + i * line_height
            draw.text((x, y), line, fill=(224, 48, 43), font=font)  # Đỏ #E0302B

        img.save(output_path, "PNG")
        logger.info("Đã tạo placeholder: %s", output_path)
        return output_path

    except Exception as exc:
        logger.error("Lỗi tạo placeholder: %s", exc)
        raise


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HIỆU ỨNG WOBBLE / BREATHING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _make_wobble_frame(
    base_frame: np.ndarray,
    t: float,
    intensity: int,
    target_w: int,
    target_h: int,
) -> np.ndarray:
    """
    Áp dụng hiệu ứng wobble lên 1 frame tại thời điểm t.

    Kết hợp 2 hiệu ứng:
      1. Subtle zoom oscillation (scale 1.0 → ~1.02, chu kỳ 2 giây)
      2. Sine-wave position offset (dịch chuyển 1-3 pixel)

    Args:
        base_frame: Mảng numpy (H, W, 3) của ảnh gốc.
        t:          Thời điểm hiện tại trong clip (giây).
        intensity:  Cường độ wobble (pixel).
        target_w:   Chiều rộng video.
        target_h:   Chiều cao video.

    Returns:
        Frame đã áp dụng hiệu ứng (H, W, 3).
    """
    # ── Zoom oscillation (chu kỳ 2s, biên độ nhỏ) ──
    zoom_period = 2.0
    zoom_amplitude = 0.005 * (intensity / 3.0)  # ~0.5% tại intensity=3
    scale = 1.0 + zoom_amplitude * math.sin(2 * math.pi * t / zoom_period)

    # ── Position offset (dịch sin với tần số khác nhau theo X, Y) ──
    dx = intensity * math.sin(2 * math.pi * t / 1.7 + 0.3)
    dy = intensity * math.cos(2 * math.pi * t / 2.3 + 0.7)

    h, w = base_frame.shape[:2]

    # ── Tính vùng crop từ ảnh gốc sau khi zoom ──
    new_w = int(w / scale)
    new_h = int(h / scale)

    # Tâm crop dịch theo dx, dy
    cx = w / 2 + dx
    cy = h / 2 + dy

    x1 = int(cx - new_w / 2)
    y1 = int(cy - new_h / 2)

    # Clamp biên
    x1 = max(0, min(x1, w - new_w))
    y1 = max(0, min(y1, h - new_h))
    x2 = x1 + new_w
    y2 = y1 + new_h

    cropped = base_frame[y1:y2, x1:x2]

    # ── Resize lại về kích thước target ──
    from PIL import Image as _PILImage

    pil_img = _PILImage.fromarray(cropped)
    pil_img = pil_img.resize((target_w, target_h), _PILImage.BILINEAR)

    return np.array(pil_img)


def _create_wobble_clip(
    image_path: str,
    duration: float,
    start_time: float,
    intensity: int,
    target_w: int,
    target_h: int,
) -> ImageClip:
    """
    Tạo ImageClip với hiệu ứng wobble (nếu intensity > 0).

    Ảnh gốc được pad thêm biên trước để wobble không bị cắt mép đen.

    Args:
        image_path: Đường dẫn ảnh đã preprocess.
        duration:   Thời lượng clip (giây).
        start_time: Thời điểm bắt đầu trong video (giây).
        intensity:  Cường độ wobble.
        target_w:   Chiều rộng video.
        target_h:   Chiều cao video.

    Returns:
        MoviePy ImageClip đã áp dụng hiệu ứng.
    """
    if intensity <= 0:
        # Không wobble → trả về ImageClip tĩnh
        clip = (
            ImageClip(image_path)
            .with_duration(duration)
            .with_start(start_time)
        )
        return clip

    # ── Pad ảnh gốc thêm biên để wobble có khoảng trống ──
    pad = intensity + 15  # pixel padding (đủ cho zoom + offset)
    img = Image.open(image_path).convert("RGB")
    padded_w = target_w + pad * 2
    padded_h = target_h + pad * 2

    # Resize ảnh gốc lên kích thước padded (cover + center-crop)
    src_w, src_h = img.size
    scale = max(padded_w / src_w, padded_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.LANCZOS)
    rw, rh = resized.size
    left = (rw - padded_w) // 2
    top = (rh - padded_h) // 2
    padded_img = resized.crop((left, top, left + padded_w, top + padded_h))
    base_frame = np.array(padded_img)

    # ── Tạo clip với make_frame ──
    def make_frame(t: float) -> np.ndarray:
        return _make_wobble_frame(base_frame, t, intensity, target_w, target_h)

    from moviepy import VideoClip

    clip = (
        VideoClip(make_frame, duration=duration)
        .with_start(start_time)
        .with_fps(config.VIDEO_FPS)
    )
    return clip


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GHÉP VIDEO CHÍNH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compile_video(project_dir: str) -> str:
    """
    Ghép video cuối cùng từ ảnh + audio cho 1 project.

    Quy trình:
      1. Đọc timing.json
      2. Load voice.mp3
      3. Tạo ImageClip cho mỗi câu (có wobble nếu bật)
      4. Ghép (concatenate/compose) → gắn audio → xuất MP4

    Args:
        project_dir: Thư mục project (chứa timing.json, voice.mp3, images/).

    Returns:
        Đường dẫn tuyệt đối đến file final_video.mp4.

    Raises:
        FileNotFoundError: Nếu timing.json hoặc voice.mp3 không tồn tại.
        RuntimeError:      Nếu quá trình render thất bại.
    """
    # ── Kiểm tra file đầu vào ──
    timing_path = os.path.join(project_dir, "timing.json")
    voice_path = os.path.join(project_dir, "voice.mp3")
    images_dir = os.path.join(project_dir, "images")
    project_name = os.path.basename(os.path.normpath(project_dir))
    output_path = os.path.join(project_dir, f"{project_name}.mp4")

    if not os.path.isfile(timing_path):
        raise FileNotFoundError(f"Không tìm thấy timing.json: {timing_path}")
    if not os.path.isfile(voice_path):
        raise FileNotFoundError(f"Không tìm thấy voice.mp3: {voice_path}")

    os.makedirs(images_dir, exist_ok=True)

    # ── Đọc timing ──
    with open(timing_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)

    # timing_data: list of {"index": int, "text": str, "start": float, "end": float}
    sentences: List[dict] = timing_data if isinstance(timing_data, list) else timing_data.get("sentences", [])

    if not sentences:
        raise ValueError("timing.json trống hoặc không hợp lệ.")

    logger.info("Bắt đầu ghép video: %d câu, project=%s", len(sentences), project_dir)

    target_w = config.VIDEO_WIDTH
    target_h = config.VIDEO_HEIGHT
    wobble = config.WOBBLE_INTENSITY

    # ── Load audio ──
    audio_clip = AudioFileClip(voice_path)

    # ── Danh sách file tạm cần dọn dẹp ──
    temp_files: List[str] = []

    # ── Tạo clip cho từng câu ──
    clips: List = []

    try:
        for entry in sentences:
            idx = entry.get("index", 0)
            text = entry.get("text", "")
            start = float(entry.get("start", 0))
            end = float(entry.get("end", 0))
            duration = end - start

            if duration <= 0:
                logger.warning("Câu %d có duration <= 0, bỏ qua.", idx)
                continue

            # ── Tìm file ảnh (png hoặc jpg) ──
            img_path: Optional[str] = None
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                candidate = os.path.join(images_dir, f"{idx}{ext}")
                if os.path.isfile(candidate):
                    img_path = candidate
                    break

            # ── Nếu không có ảnh → tạo placeholder ──
            if img_path is None:
                placeholder_path = os.path.join(images_dir, f"{idx}_placeholder.png")
                img_path = create_placeholder_image(text, target_w, target_h, placeholder_path)
                temp_files.append(placeholder_path)
                logger.warning("Không tìm thấy ảnh cho câu %d, dùng placeholder.", idx)

            # ── Preprocess (resize + center-crop) ──
            processed_path = preprocess_image(img_path, target_w, target_h)
            temp_files.append(processed_path)

            # ── Tạo clip (có wobble nếu bật) ──
            clip = _create_wobble_clip(
                image_path=processed_path,
                duration=duration,
                start_time=start,
                intensity=wobble,
                target_w=target_w,
                target_h=target_h,
            )
            clips.append(clip)
            logger.info(
                "  Câu %d: %.2fs → %.2fs (%.2fs) — %s",
                idx, start, end, duration,
                "wobble" if wobble > 0 else "static",
            )

        if not clips:
            raise RuntimeError("Không có clip nào được tạo.")

        # ── Ghép video ──
        logger.info("Đang ghép %d clips...", len(clips))
        final_clip = CompositeVideoClip(clips, size=(target_w, target_h))

        # ── Gắn audio ──
        final_clip = final_clip.with_duration(audio_clip.duration)
        final_clip = final_clip.with_audio(audio_clip)

        # ── Xuất file MP4 ──
        logger.info("Đang render video → %s", output_path)
        cpu_threads = os.cpu_count() or 4
        final_clip.write_videofile(
            output_path,
            fps=config.VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            bitrate="5000k",
            threads=cpu_threads,
            preset="ultrafast",
            logger="bar",  # Hiện progress bar
        )

        logger.info("✅ Hoàn thành! Video: %s", output_path)
        return output_path

    except Exception as exc:
        logger.error("❌ Lỗi khi ghép video: %s", exc)
        raise RuntimeError(f"Ghép video thất bại: {exc}") from exc

    finally:
        # ── Dọn dẹp file tạm ──
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
    """
    Test nhanh: tạo project mẫu với ảnh placeholder + timing giả,
    rồi gọi compile_video() để kiểm tra flow.
    """
    import shutil

    test_project = os.path.join(config.BASE_OUTPUT_DIR, "_test_video_compiler")
    test_images = os.path.join(test_project, "images")
    os.makedirs(test_images, exist_ok=True)

    # ── Tạo timing.json mẫu ──
    sample_timing = [
        {"index": 0, "text": "You wake up when your body is ready.", "start": 0.0, "end": 3.0},
        {"index": 1, "text": "No alarm. No schedule.", "start": 3.0, "end": 5.5},
        {"index": 2, "text": "For 99% of human history, this was normal.", "start": 5.5, "end": 9.0},
    ]
    with open(os.path.join(test_project, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(sample_timing, f, indent=2)

    # ── Tạo ảnh placeholder cho câu 0 và 2 (câu 1 sẽ dùng auto-placeholder) ──
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

    # ── Tạo file audio giả (im lặng) bằng MoviePy ──
    try:
        from moviepy import ColorClip

        silent_clip = ColorClip(
            size=(320, 240),
            color=(0, 0, 0),
            duration=9.0,
        )
        silent_video_path = os.path.join(test_project, "voice.mp4")
        silent_clip.write_videofile(
            silent_video_path,
            fps=1,
            codec="libx264",
            audio=False,
            logger=None,
        )
        # Dùng ffmpeg tạo audio rỗng (nếu có ffmpeg)
        voice_path = os.path.join(test_project, "voice.mp3")
        os.system(
            f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=mono -t 9 "{voice_path}" -loglevel quiet'
        )
        if os.path.isfile(silent_video_path):
            os.remove(silent_video_path)

        if not os.path.isfile(voice_path):
            print("⚠️  Không thể tạo voice.mp3 giả (cần ffmpeg). Bỏ qua test render.")
            print("   Tuy nhiên các hàm preprocess_image / create_placeholder đã OK.")
        else:
            # ── Chạy compile ──
            result = compile_video(test_project)
            print(f"\n🎬 Video test đã tạo: {result}")
            print(f"   Kích thước: {os.path.getsize(result) / 1024:.0f} KB")

    except Exception as e:
        print(f"⚠️  Test compile_video gặp lỗi: {e}")
        print("   Các hàm tiện ích (preprocess_image, create_placeholder) vẫn hoạt động.")

    finally:
        # Dọn thư mục test (bỏ comment nếu muốn)
        # shutil.rmtree(test_project, ignore_errors=True)
        print(f"\n📁 Thư mục test: {test_project}")
