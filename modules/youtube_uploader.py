# -*- coding: utf-8 -*-
"""
=============================================================
  YOUTUBE_UPLOADER.PY — Tự động hóa đăng video lên YouTube Studio
=============================================================
Sử dụng Playwright để điều khiển Chrome tự động điền metadata,
tải video lên và xuất bản, vượt qua các giới hạn quota API.
"""

import os
import sys
import json
import time
import asyncio
import logging

# Thêm thư mục gốc vào sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from modules.prompt_generator import call_gemini_web

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YouTubeUploader")

def _seconds_to_mmss(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"

# ---------- A. TỰ ĐỘNG TẠO METADATA QUA GEMINI ----------
def generate_youtube_metadata(project_dir: str) -> dict:
    """
    Đọc kịch bản và sinh Tiêu đề, Mô tả, Thẻ tags cho video.
    Lưu kết quả vào metadata.json.
    """
    script_path = os.path.join(project_dir, "script.txt")
    timing_path = os.path.join(project_dir, "timing.json")
    metadata_path = os.path.join(project_dir, "metadata.json")
    
    # 1. Đọc nội dung kịch bản
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Không tìm thấy kịch bản script.txt tại {script_path}")
    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read().strip()
        
    # 2. Đọc timing để trích xuất mốc chương (Chapters)
    chapters_text = ""
    if os.path.isfile(timing_path):
        try:
            with open(timing_path, "r", encoding="utf-8") as f:
                timing_data = json.load(f)
            sentences = timing_data if isinstance(timing_data, list) else timing_data.get("sentences", [])
            
            # Chọn khoảng 5-8 mốc thời gian cách đều nhau làm chương video
            num_sentences = len(sentences)
            if num_sentences > 5:
                step = max(1, num_sentences // 6)
                selected_sentences = [sentences[0]]
                for idx in range(step, num_sentences - step, step):
                    selected_sentences.append(sentences[idx])
                selected_sentences.append(sentences[-1])
                
                # Định dạng danh sách chương
                chapters_lines = []
                for s in selected_sentences:
                    timestamp = _seconds_to_mmss(s["start"])
                    # Trích xuất 5 từ đầu của câu làm tiêu đề chương
                    words = s["text"].split()[:5]
                    title = " ".join(words).replace('"', '').replace("'", "") + "..."
                    chapters_lines.append(f"{timestamp} - {title}")
                chapters_text = "\n".join(chapters_lines)
        except Exception as e:
            logger.warning(f"Lỗi khi trích xuất chapters từ timing.json: {e}")

    # Đọc cấu hình ngôn ngữ từ project_info.json
    language = "vi"
    info_path = os.path.join(project_dir, "project_info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            language = info.get("language", "vi")
        except Exception:
            pass

    lang_desc = "Vietnamese" if language == "vi" else "English"
    lang_prompt = (
        "The generated title and description MUST be written in Vietnamese." 
        if language == "vi" else 
        "The generated title and description MUST be written in English."
    )

    # 3. Xây dựng Prompt gửi Gemini
    prompt = f"""You are a professional YouTube growth expert and SEO specialist.
I will provide you with a video narration script and some chapter timestamps.
Your task is to generate:
1. A highly clickable, viral YouTube Video Title (must be under 100 characters, ideally under 70 characters. It should contain curiosity, hook, or reframe).
2. A high-converting YouTube Video Description (2-3 paragraphs summarize the video, weave in relevant search keywords naturally, include the chapters timestamps provided below, and add 3 relevant hashtags).
3. A list of 10-15 highly relevant YouTube SEO Tags (keywords) as a JSON array of strings.

Narrative Script:
\"\"\"
{script_text[:4000]}
\"\"\"

Chapter Timestamps:
\"\"\"
{chapters_text or "00:00 - Introduction"}
\"\"\"

STRICT REQUIREMENTS:
- Language: {lang_prompt}
- Output format: Return ONLY a valid JSON object matching the format below with no markdown, no explanation, no backticks.

Output JSON format:
{{
  "title": "Your Generated Viral Title Here",
  "description": "Your Generated SEO Description Here\\n\\nTIMESTAMPS:\\n00:00 - Intro\\n...",
  "tags": ["keyword1", "keyword2", "keyword3"]
}}"""

    logger.info("🧠 Đang gọi Gemini Web để tự động thiết kế YouTube SEO Metadata...")
    response_text = call_gemini_web(prompt, "youtube_metadata")
    
    # Clean response
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        # remove markdown blocks
        clean_text = re.sub(r"^```(?:json)?\s*\n", "", clean_text)
        clean_text = re.sub(r"\n\s*```$", "", clean_text).strip()
        
    # Find JSON bounds
    start_idx = clean_text.find("{")
    end_idx = clean_text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        clean_text = clean_text[start_idx:end_idx + 1]
        
    try:
        metadata = json.loads(clean_text)
        # Verify structure
        if not isinstance(metadata, dict) or "title" not in metadata or "description" not in metadata:
            raise ValueError("Cấu trúc JSON không hợp lệ")
    except Exception as e:
        logger.error(f"Lỗi parse JSON metadata từ Gemini: {e}. Nội dung thô: {response_text[:300]}")
        # Fallback
        project_name = os.path.basename(os.path.normpath(project_dir))
        metadata = {
            "title": project_name.replace("_", " ").title(),
            "description": f"Video generated by Doodle Video Automator.\n\nChapters:\n{chapters_text or '00:00 - Start'}",
            "tags": ["doodle video", "prehistory", "ancient humans"]
        }
        
    # Lưu metadata.json
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        
    logger.info(f"💾 Đã lưu YouTube Metadata vào {metadata_path}")
    return metadata


# ---------- B. PLAYWRIGHT AUTOMATION UPLOADER ----------
async def run_playwright_upload(project_dir: str, privacy: str = "public") -> bool:
    """
    Sử dụng Playwright để tự động tải video lên YouTube Studio.
    """
    # 1. Tìm video
    project_name = os.path.basename(os.path.normpath(project_dir))
    video_path = os.path.join(project_dir, f"{project_name}.mp4")
    if not os.path.isfile(video_path):
        # Fallback to look for any .mp4 file in project_dir
        mp4_files = [f for f in os.listdir(project_dir) if f.endswith(".mp4")]
        if mp4_files:
            video_path = os.path.join(project_dir, mp4_files[0])
        else:
            logger.error(f"Không tìm thấy file video MP4 nào tại thư mục: {project_dir}")
            return False
            
    video_path = os.path.abspath(video_path)
    logger.info(f"📹 Đường dẫn video tải lên: {video_path}")

    # 2. Đọc metadata
    metadata_path = os.path.join(project_dir, "metadata.json")
    if not os.path.isfile(metadata_path):
        logger.info("Chưa có file metadata.json, tự động khởi tạo...")
        try:
            metadata = generate_youtube_metadata(project_dir)
        except Exception as e:
            logger.error(f"Lỗi tạo metadata: {e}")
            return False
    else:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
    title = metadata.get("title", project_name.replace("_", " ").title())
    description = metadata.get("description", "")
    tags = metadata.get("tags", [])
    
    # 3. Khởi tạo Playwright
    from playwright.async_api import async_playwright
    
    user_data_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "chrome_profiles", "youtube_upload"))
    logger.info(f"📂 Thư mục Chrome Profile lưu Session: {user_data_dir}")
    os.makedirs(user_data_dir, exist_ok=True)
    
    async with async_playwright() as p:
        logger.info("🚀 Đang khởi động trình duyệt Chrome thực tế...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,  # Bắt buộc False để người dùng có thể can thiệp đăng nhập nếu cần
            channel="chrome",  # Sử dụng Chrome chính cài trên máy
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]  # Giảm thiểu phát hiện bot
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        logger.info("🔗 Đang truy cập YouTube Studio...")
        await page.goto("https://studio.youtube.com", timeout=60000)
        
        # 4. Kiểm tra xem có cần Đăng nhập hay không
        await asyncio.sleep(3)
        current_url = page.url
        if "accounts.google.com" in current_url or "signin" in current_url.lower():
            logger.warning("⚠️ CHƯA ĐĂNG NHẬP: Phát hiện cửa sổ Đăng nhập tài khoản Google!")
            print("\n" + "="*80)
            print(" 👉 YÊU CẦU: Vui lòng đăng nhập tài khoản YouTube của bạn trong cửa sổ Chrome vừa mở.")
            print(" 👉 Sau khi đăng nhập thành công và nhìn thấy bảng điều khiển YouTube Studio, hãy quay lại đây.")
            print("="*80 + "\n")
            
            # Đợi đến khi URL thuộc studio.youtube.com hoặc người dùng bấm Enter
            is_logged_in = False
            for _ in range(300): # Chờ tối đa 10 phút
                await asyncio.sleep(2)
                if "studio.youtube.com" in page.url:
                    is_logged_in = True
                    break
            
            if not is_logged_in:
                logger.error("Quá thời gian chờ đăng nhập (10 phút). Tiến trình dừng.")
                await context.close()
                return False
                
        logger.info("✓ Đăng nhập thành công! Đang đồng bộ trạng thái trang...")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        # 5. Mở modal tải lên video
        logger.info("📂 Đang mở Form tải lên...")
        # Cách nhanh nhất: Navigate thẳng vào Upload url
        await page.goto("https://studio.youtube.com/channel/UC/videos?d=ud", timeout=60000)
        await asyncio.sleep(3)
        
        # Tìm input type="file"
        file_input = page.locator('input[type="file"]')
        try:
            await file_input.wait_for(state="attached", timeout=15000)
            logger.info("✓ Tìm thấy ô chọn file. Đang tải video lên...")
            await file_input.set_input_files(video_path)
        except Exception as e:
            logger.error(f"Không tìm thấy form upload của YouTube: {e}")
            await context.close()
            return False
            
        # Đợi modal điền chi tiết xuất hiện
        logger.info("⏳ Chờ hộp thoại nhập thông tin xuất hiện...")
        title_textarea = page.locator('ytcp-social-suggestions-textbox[textbox-id="title-textarea"] div[contenteditable="true"]')
        try:
            await title_textarea.wait_for(state="visible", timeout=30000)
        except Exception:
            # Fallback selector khác
            title_textarea = page.locator('#title-textarea div[contenteditable="true"]')
            await title_textarea.wait_for(state="visible", timeout=15000)
            
        logger.info("✓ Bắt đầu điền thông tin video...")
        
        # 6. Điền tiêu đề
        await title_textarea.click()
        # Xóa nội dung mặc định (tên file)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await title_textarea.fill(title)
        logger.info(f"   - Đã điền Tiêu đề: \"{title}\"")
        await asyncio.sleep(1)
        
        # 7. Điền mô tả
        desc_textarea = page.locator('ytcp-social-suggestions-textbox[textbox-id="description-textarea"] div[contenteditable="true"]')
        if not await desc_textarea.count():
            desc_textarea = page.locator('#description-textarea div[contenteditable="true"]')
        await desc_textarea.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await desc_textarea.fill(description)
        logger.info("   - Đã điền Mô tả thành công.")
        await asyncio.sleep(1)
        
        # 8. Không dành cho trẻ em (Audience: Not made for kids)
        logger.info("   - Đang cấu hình đối tượng người xem (Không dành cho trẻ em)...")
        # Radio button: "No, it's not made for kids"
        not_for_kids_radio = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_FALSE"]')
        if await not_for_kids_radio.count():
            await not_for_kids_radio.click()
        else:
            # Fallback click text trực tiếp
            no_kids_text = page.locator('text="No, it\'s not made for kids"').first
            if await no_kids_text.count():
                await no_kids_text.click()
            else:
                no_kids_vi = page.locator('text="Không, nội dung này không dành cho trẻ em"').first
                if await no_kids_vi.count():
                    await no_kids_vi.click()
                    
        await asyncio.sleep(1)
        
        # 9. Điền Tags (Cần nhấn nút Show More / Hiện thêm)
        logger.info("   - Đang hiển thị cài đặt nâng cao để nhập Tags...")
        show_more_btn = page.locator('ytcp-button#toggle-button')
        if await show_more_btn.count():
            await show_more_btn.scroll_into_view_if_needed()
            await show_more_btn.click()
            await asyncio.sleep(1.5)
            
        tags_input = page.locator('ytcp-form-input-container#tags-container input#text-input')
        if await tags_input.count() and tags:
            await tags_input.scroll_into_view_if_needed()
            await tags_input.click()
            tags_str = ",".join(tags) + ","
            await tags_input.fill(tags_str)
            logger.info(f"   - Đã điền {len(tags)} thẻ tags.")
            await asyncio.sleep(1)
            
        # 10. Click Next để qua các bước phụ (Bấm Next 3 lần)
        logger.info("⏭️ Đang đi qua các bước cài đặt bản quyền...")
        next_button = page.locator('ytcp-button#next-button')
        
        # Bước 1 (Details -> Video Elements)
        await next_button.click()
        await asyncio.sleep(1.5)
        
        # Bước 2 (Video Elements -> Checks)
        await next_button.click()
        await asyncio.sleep(1.5)
        
        # Bước 3 (Checks -> Visibility)
        await next_button.click()
        await asyncio.sleep(1.5)
        
        # 11. Đặt chế độ hiển thị (Visibility)
        logger.info(f"🛡️ Đặt chế độ hiển thị: {privacy.upper()}")
        privacy_upper = privacy.lower()
        
        if privacy_upper == "public":
            radio_selector = 'tp-yt-paper-radio-button[name="PUBLIC"]'
            label_text = "Public"
            label_text_vi = "Công khai"
        elif privacy_upper == "unlisted":
            radio_selector = 'tp-yt-paper-radio-button[name="UNLISTED"]'
            label_text = "Unlisted"
            label_text_vi = "Không công khai"
        else: # private
            radio_selector = 'tp-yt-paper-radio-button[name="PRIVATE"]'
            label_text = "Private"
            label_text_vi = "Riêng tư"
            
        radio_btn = page.locator(radio_selector)
        if await radio_btn.count():
            await radio_btn.click()
        else:
            # Fallback text
            lbl = page.locator(f'text="{label_text}"').first
            if await lbl.count():
                await lbl.click()
            else:
                lbl_vi = page.locator(f'text="{label_text_vi}"').first
                if await lbl_vi.count():
                    await lbl_vi.click()
                    
        await asyncio.sleep(1.5)
        
        # 12. Theo dõi tiến trình tải lên trước khi bấm Done
        logger.info("⏳ Đang theo dõi tiến độ tải lên video...")
        progress_label = page.locator('span.ytcp-video-upload-progress')
        
        upload_finished = False
        start_time = time.time()
        max_upload_wait = 1800 # 30 phút tối đa cho các file siêu nặng
        
        while time.time() - start_time < max_upload_wait:
            if await progress_label.count():
                txt = await progress_label.inner_text()
                logger.info(f"   [Tiến trình tải lên] {txt.strip()}")
                
                # Nếu hiển thị "Upload complete", "Processing", "Checks complete"
                txt_lower = txt.lower()
                if ("complete" in txt_lower or "xử lý" in txt_lower or "hoàn tất" in txt_lower or "kiểm tra" in txt_lower or "%" not in txt_lower):
                    # Đã tải xong hoặc bắt đầu xử lý
                    upload_finished = True
                    break
            else:
                # Không thấy progress label nữa, có thể đã tải xong
                logger.info("   Không thấy thanh tiến độ, coi như tải lên xong.")
                upload_finished = True
                break
            await asyncio.sleep(10)
            
        if not upload_finished:
            logger.warning("⚠️ Tiến trình tải lên quá lâu, sẽ tự động bấm Xuất bản để YouTube tự xử lý tiếp.")
            
        # 13. Bấm Done / Publish / Save
        logger.info("💾 Đang lưu cấu hình và xuất bản video...")
        done_button = page.locator('ytcp-button#done-button')
        if not await done_button.count():
            done_button = page.locator('ytcp-button#publish-button')
            
        await done_button.click()
        logger.info("🎉 Đã nhấn nút Xuất bản thành công!")
        await asyncio.sleep(5)
        
        # Đóng trình duyệt
        await context.close()
        logger.info("🚀 Đã hoàn tất đăng video lên YouTube Studio thành công!")
        return True

def upload_video_sync(project_dir: str, privacy: str = "public") -> bool:
    """Đăng chạy đồng bộ Playwright trong thread riêng."""
    try:
        return asyncio.run(run_playwright_upload(project_dir, privacy))
    except Exception as e:
        logger.error(f"Lỗi thực thi Playwright: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: python youtube_uploader.py <project_dir> [privacy]")
        sys.exit(1)
        
    p_dir = sys.argv[1]
    priv = sys.argv[2] if len(sys.argv) > 2 else "public"
    success = upload_video_sync(p_dir, priv)
    sys.exit(0 if success else 1)
