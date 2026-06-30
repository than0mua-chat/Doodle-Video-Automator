"""
=============================================================
  IMAGE_DOWNLOADER.PY — Tải/tạo ảnh từ prompts
=============================================================
Hai chế độ:
  • "api"    — Gọi Gemini Imagen API để tự động tạo ảnh
  • "export" — Xuất file prompts để dùng thủ công trên ImageFX
"""

import sys
import os
import json
import time
from typing import Union

# ── Thêm thư mục gốc project vào path để import config ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from tqdm import tqdm


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODE 1: API — Tạo ảnh bằng Gemini Imagen API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def generate_images_api(project_dir: str) -> list[str]:
    """
    Đọc prompts.json và gọi Imagen API để tạo ảnh cho từng prompt.

    Args:
        project_dir: Đường dẫn thư mục project (vd: output/my_project)

    Returns:
        Danh sách đường dẫn file ảnh đã tạo.

    Raises:
        FileNotFoundError: Nếu prompts.json không tồn tại.
        RuntimeError: Nếu API trả về lỗi hoặc không có ảnh.
    """
    from google import genai
    from google.genai import types

    prompts_path = os.path.join(project_dir, "prompts.json")
    images_dir = os.path.join(project_dir, "images")

    # ── Đọc file prompts ──
    if not os.path.exists(prompts_path):
        raise FileNotFoundError(f"Không tìm thấy file prompts: {prompts_path}")

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts_data = json.load(f)

    # prompts_data có thể là list[str] hoặc list[dict] — chuẩn hóa
    prompts: list[str] = _extract_prompt_texts(prompts_data)

    if not prompts:
        raise ValueError("File prompts.json rỗng hoặc không chứa prompt nào.")

    # ── Tạo thư mục images ──
    os.makedirs(images_dir, exist_ok=True)

    # ── Khởi tạo client Gemini ──
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    saved_paths: list[str] = []
    print(f"\n🎨 Đang tạo {len(prompts)} ảnh bằng Imagen API...")

    for idx, prompt_text in enumerate(tqdm(prompts, desc="Tạo ảnh", unit="ảnh")):
        output_path = os.path.join(images_dir, f"{idx}.png")

        # Bỏ qua nếu ảnh đã tồn tại
        if os.path.exists(output_path):
            tqdm.write(f"  ⏭️  Ảnh {idx}.png đã tồn tại, bỏ qua.")
            saved_paths.append(output_path)
            continue

        try:
            result = client.models.generate_images(
                model=config.GEMINI_IMAGE_MODEL,
                prompt=prompt_text,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                ),
            )

            # Kiểm tra kết quả trả về
            if not result.generated_images or len(result.generated_images) == 0:
                tqdm.write(f"  ⚠️  API không trả về ảnh cho prompt {idx}.")
                continue

            # Lưu ảnh (image data dạng bytes)
            image_data = result.generated_images[0].image.image_bytes
            with open(output_path, "wb") as img_file:
                img_file.write(image_data)

            saved_paths.append(output_path)
            tqdm.write(f"  ✅ Đã lưu: {idx}.png")

        except Exception as e:
            tqdm.write(f"  ❌ Lỗi tạo ảnh {idx}: {e}")
            continue

        # Delay giữa các lần gọi API để tránh rate-limit
        if idx < len(prompts) - 1:
            time.sleep(2)

    print(f"\n✅ Hoàn tất: {len(saved_paths)}/{len(prompts)} ảnh đã được tạo.")
    return saved_paths


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODE 2: EXPORT — Xuất prompts để dùng thủ công trên ImageFX
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def export_prompts_for_imagefx(project_dir: str) -> str:
    """
    Xuất prompts ra file text để người dùng paste thủ công vào ImageFX.

    Tạo 2 file:
      - imagefx_prompts.txt          — Mỗi prompt trên 1 dòng, cách nhau bằng dòng trống
      - imagefx_prompts_numbered.txt — Giống trên nhưng có đánh số thứ tự

    Args:
        project_dir: Đường dẫn thư mục project.

    Returns:
        Đường dẫn tới file imagefx_prompts.txt

    Raises:
        FileNotFoundError: Nếu prompts.json không tồn tại.
    """
    prompts_path = os.path.join(project_dir, "prompts.json")
    images_dir = os.path.join(project_dir, "images")

    # ── Đọc file prompts ──
    if not os.path.exists(prompts_path):
        raise FileNotFoundError(f"Không tìm thấy file prompts: {prompts_path}")

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts_data = json.load(f)

    prompts: list[str] = _extract_prompt_texts(prompts_data)

    if not prompts:
        raise ValueError("File prompts.json rỗng hoặc không chứa prompt nào.")

    # ── Tạo thư mục images (để user biết chỗ lưu ảnh) ──
    os.makedirs(images_dir, exist_ok=True)

    # ── File 1: Clean prompts (không đánh số) ──
    clean_path = os.path.join(project_dir, "imagefx_prompts.txt")
    with open(clean_path, "w", encoding="utf-8") as f:
        for i, prompt in enumerate(prompts):
            f.write(prompt.strip())
            if i < len(prompts) - 1:
                f.write("\n\n")  # Dòng trống giữa các prompt

    # ── File 2: Numbered prompts (có đánh số) ──
    numbered_path = os.path.join(project_dir, "imagefx_prompts_numbered.txt")
    with open(numbered_path, "w", encoding="utf-8") as f:
        for i, prompt in enumerate(prompts):
            f.write(f"[{i}] {prompt.strip()}")
            if i < len(prompts) - 1:
                f.write("\n\n")

    # ── In hướng dẫn cho user ──
    print("\n" + "=" * 60)
    print("📋 ĐÃ XUẤT PROMPTS CHO IMAGEFX")
    print("=" * 60)
    print(f"\n📄 File prompts (clean) : {clean_path}")
    print(f"📄 File prompts (numbered): {numbered_path}")
    print(f"📁 Thư mục lưu ảnh       : {images_dir}")
    print(f"📊 Tổng số prompts       : {len(prompts)}")
    print()
    print("📌 HƯỚNG DẪN:")
    print("   1. Mở ImageFX: https://aitestkitchen.withgoogle.com/tools/image-fx")
    print("   2. Dùng extension 'ImageFX Automator' hoặc paste từng prompt thủ công.")
    print(f"   3. Lưu ảnh vào thư mục: {images_dir}")
    print(f"      Đặt tên: 0.png, 1.png, 2.png, ... , {len(prompts) - 1}.png")
    print()
    print("💡 Sau khi lưu đủ ảnh, chạy check_images_ready() để kiểm tra.")
    print("=" * 60 + "\n")

    return clean_path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DISPATCHER — Chọn chế độ dựa trên config.IMAGE_MODE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def download_images(project_dir: str) -> Union[list[str], str]:
    """
    Dispatcher: tạo ảnh theo chế độ được cấu hình trong config.IMAGE_MODE.

    Args:
        project_dir: Đường dẫn thư mục project.

    Returns:
        - Mode "api":    list[str] — danh sách đường dẫn ảnh đã tạo.
        - Mode "export": str — đường dẫn file prompts đã xuất.

    Raises:
        ValueError: Nếu IMAGE_MODE không hợp lệ.
    """
    mode = getattr(config, "IMAGE_MODE", "export").lower().strip()

    if mode == "api":
        print(f"🖼️  Chế độ: API (Imagen model: {config.GEMINI_IMAGE_MODEL})")
        return generate_images_api(project_dir)
    elif mode == "export":
        print("🖼️  Chế độ: Export (xuất prompts cho ImageFX thủ công)")
        return export_prompts_for_imagefx(project_dir)
    else:
        raise ValueError(
            f"IMAGE_MODE không hợp lệ: '{mode}'. "
            f"Chọn 'api' hoặc 'export' trong config.py."
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UTILITY — Kiểm tra ảnh đã sẵn sàng chưa
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def check_images_ready(project_dir: str) -> tuple[bool, int, int]:
    """
    Kiểm tra xem tất cả ảnh đã có trong thư mục images/ chưa.

    Args:
        project_dir: Đường dẫn thư mục project.

    Returns:
        (all_ready, found_count, total_count)
        - all_ready: True nếu đã đủ ảnh
        - found_count: Số ảnh tìm thấy
        - total_count: Tổng số ảnh cần có
    """
    prompts_path = os.path.join(project_dir, "prompts.json")
    images_dir = os.path.join(project_dir, "images")

    # Đọc tổng số prompts
    if not os.path.exists(prompts_path):
        print(f"⚠️  Không tìm thấy file: {prompts_path}")
        return False, 0, 0

    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts_data = json.load(f)
        prompts = _extract_prompt_texts(prompts_data)
        total_count = len(prompts)
    except Exception as e:
        print(f"❌ Lỗi đọc prompts.json: {e}")
        return False, 0, 0

    if total_count == 0:
        print("⚠️  File prompts.json rỗng.")
        return False, 0, 0

    # Đếm ảnh đã có (kiểm tra 0.png, 1.png, ..., N-1.png)
    found_count = 0
    missing: list[int] = []
    for i in range(total_count):
        img_path = os.path.join(images_dir, f"{i}.png")
        if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
            found_count += 1
        else:
            missing.append(i)

    all_ready = found_count == total_count

    # In trạng thái
    if all_ready:
        print(f"✅ Đã đủ ảnh: {found_count}/{total_count}")
    else:
        print(f"⏳ Chưa đủ ảnh: {found_count}/{total_count}")
        if len(missing) <= 20:
            print(f"   Thiếu: {', '.join(str(m) + '.png' for m in missing)}")
        else:
            print(f"   Thiếu {len(missing)} ảnh (hiển thị 20 đầu): "
                  f"{', '.join(str(m) + '.png' for m in missing[:20])}, ...")

    return all_ready, found_count, total_count


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER — Trích xuất prompt text từ nhiều format
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _extract_prompt_texts(prompts_data: list) -> list[str]:
    """
    Chuẩn hóa dữ liệu prompts từ nhiều định dạng:
      - list[str]  → trả về trực tiếp
      - list[dict] → lấy giá trị từ key "prompt" hoặc "text"

    Args:
        prompts_data: Dữ liệu đọc từ prompts.json

    Returns:
        Danh sách các prompt text (string).
    """
    if not isinstance(prompts_data, list):
        raise ValueError(f"prompts.json phải chứa một list, nhận được: {type(prompts_data)}")

    prompts: list[str] = []
    for item in prompts_data:
        if isinstance(item, str):
            prompts.append(item)
        elif isinstance(item, dict):
            # Thử các key phổ biến
            text = item.get("prompt") or item.get("text") or item.get("description", "")
            if text:
                prompts.append(str(text))
            else:
                print(f"⚠️  Bỏ qua prompt dict không có key 'prompt'/'text': {item}")
        else:
            print(f"⚠️  Bỏ qua phần tử không hợp lệ: {item}")

    return prompts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST BLOCK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Image Downloader — Tạo ảnh từ prompts")
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=None,
        help="Đường dẫn thư mục project (vd: d:/Youtube/output/my_project)",
    )
    parser.add_argument(
        "--mode",
        choices=["api", "export", "check"],
        default=None,
        help="Chế độ chạy: api, export, hoặc check (kiểm tra ảnh)",
    )
    args = parser.parse_args()

    # ── Nếu không truyền project_dir, tạo thư mục test ──
    if args.project_dir is None:
        test_dir = os.path.join(config.BASE_OUTPUT_DIR, "_test_image_downloader")
        os.makedirs(os.path.join(test_dir, "images"), exist_ok=True)

        # Tạo file prompts.json mẫu
        test_prompts = [
            "A prehistoric cave painting showing hunters chasing mammoths, "
            "hand-drawn 2D doodle style, flat colors, bold outlines, 16:9",
            "An ancient human family sitting around a campfire at night, "
            "hand-drawn 2D doodle style, flat colors, bold outlines, 16:9",
            "Stone age tools arranged on a flat rock surface, "
            "hand-drawn 2D doodle style, flat colors, bold outlines, 16:9",
        ]
        prompts_file = os.path.join(test_dir, "prompts.json")
        with open(prompts_file, "w", encoding="utf-8") as f:
            json.dump(test_prompts, f, indent=2, ensure_ascii=False)

        print(f"📝 Đã tạo file test: {prompts_file}")
        project_dir = test_dir
    else:
        project_dir = args.project_dir

    # ── Chạy theo mode ──
    mode = args.mode

    if mode == "check":
        print("\n🔍 Kiểm tra ảnh...\n")
        ready, found, total = check_images_ready(project_dir)
        print(f"\n→ Kết quả: ready={ready}, found={found}, total={total}")

    elif mode == "api":
        print("\n🎨 Chạy chế độ API...\n")
        try:
            paths = generate_images_api(project_dir)
            print(f"\n→ Đã tạo {len(paths)} ảnh:")
            for p in paths:
                print(f"   {p}")
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")

    elif mode == "export":
        print("\n📋 Chạy chế độ Export...\n")
        try:
            result_path = export_prompts_for_imagefx(project_dir)
            print(f"\n→ File prompts: {result_path}")
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")

    else:
        # Không chỉ định mode → dùng dispatcher (theo config.IMAGE_MODE)
        print(f"\n🚀 Chạy dispatcher (config.IMAGE_MODE = '{config.IMAGE_MODE}')...\n")
        try:
            result = download_images(project_dir)
            if isinstance(result, list):
                print(f"\n→ Đã tạo {len(result)} ảnh.")
            else:
                print(f"\n→ File prompts: {result}")
        except Exception as e:
            print(f"\n❌ Lỗi: {e}")
