"""
=============================================================
  PROMPT_GENERATOR.PY — Tạo image prompt cho từng câu narration
=============================================================
Đọc timing.json → gửi lên Gemini → nhận về 1 image prompt / câu
→ lưu prompts.txt + prompts.json
"""

import sys
import os
import json
import re
import time
import logging
from typing import Optional

# Thêm thư mục gốc vào sys.path để import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

import google.generativeai as genai

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOGGING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONSTANTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BATCH_SIZE = 30  # Số câu tối đa mỗi lần gọi Gemini


def _seconds_to_mmss(seconds: float) -> str:
    """Chuyển giây thành định dạng MM:SS."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


def _build_system_prompt() -> str:
    """
    Xây dựng system prompt chi tiết cho Gemini,
    bao gồm Visual Style DNA và các quy tắc tạo prompt.
    """
    return f"""You are an expert image prompt writer for a hand-drawn 2D doodle cartoon YouTube channel.

{config.VISUAL_STYLE_DNA}

## YOUR TASK
You will receive a list of narration sentences, each prefixed with a timestamp [MM:SS].
For EACH timestamp line, generate exactly ONE image prompt that visually represents that sentence.

## STRICT RULES FOR EVERY PROMPT

1. **Start anchor** — Every prompt MUST begin with exactly:
   "{config.IMAGE_PROMPT_STYLE_ANCHOR}"

2. **End lock** — Every prompt MUST end with exactly:
   "{config.IMAGE_PROMPT_STYLE_LOCK}"

3. **Be specific** — Describe:
   - Characters: hair/outfit description (matching Visual Style DNA), expression (smiling, worried, surprised), pose, action
   - Objects: shape, color, size, position
   - Background: flat solid color zone (matching Visual Style DNA)
   - Any on-screen text: what it says, color (default RED), position

4. **Translate abstract concepts into concrete visuals** — Represent abstract terms (e.g. \"survival\", \"finance\", \"evolution\") with simple, clear physical actions performed by the characters/objects defined in the Visual Style DNA.

5. **Match background tone to content:**
   - Outdoor / nature / wilderness → light blue sky + green trees + tan ground
   - Night / sleeping / calm → dark navy sky + yellow crescent moon + gray ground
   - Danger / sadness / hardship → gray rain cloud at top, blue raindrops falling
   - Neutral / concept / on-screen-text explanation → white or cream background
   - Or any background style specifically defined in the Visual Style DNA above.

6. **Scene continuity** — If consecutive timestamps describe the SAME moment or scene, keep the same background, character positions, and setting. Only change what the narration changes.

7. **Character consistency** — Follow the character descriptions and roles specified in the Visual Style DNA above. Keep the main character and all character variants consistent across all image prompts.

9. **Language of prompt** — The generated image description (between the anchor and the lock) MUST be written in English, even if the input narration sentences are in another language (e.g. Vietnamese).

## OUTPUT FORMAT
Return ONLY a valid JSON array, no markdown fences, no explanation. Each element:
{{"index": <0-based index matching input order>, "timestamp": "<MM:SS>", "prompt": "<full prompt text starting with anchor and ending with lock>"}}

Example:
[
  {{"index": 0, "timestamp": "00:00", "prompt": "{config.IMAGE_PROMPT_STYLE_ANCHOR} the main character as defined in visual style DNA standing on neutral background, looking curious, arms relaxed at sides, {config.IMAGE_PROMPT_STYLE_LOCK}"}},
  {{"index": 1, "timestamp": "00:05", "prompt": "{config.IMAGE_PROMPT_STYLE_ANCHOR} close-up of the main character's head, wide surprised eyes, white background, bold red text at top center reads WHAT IF, {config.IMAGE_PROMPT_STYLE_LOCK}"}}
]
"""


def _build_user_message(sentences: list[dict], batch_offset: int = 0) -> str:
    """
    Xây dựng user message chứa danh sách câu với timestamp.
    
    Args:
        sentences: Danh sách dict từ timing.json
        batch_offset: Offset index khi chia batch
    """
    lines = []
    for i, item in enumerate(sentences):
        timestamp = _seconds_to_mmss(item["start"])
        text = item["text"].strip()
        global_index = batch_offset + i
        lines.append(f"[{timestamp}] (index {global_index}) {text}")
    
    return "Generate one image prompt for each line below:\n\n" + "\n".join(lines)


def _parse_gemini_response(response_text: str) -> list[dict]:
    """
    Parse JSON array từ response của Gemini.
    Xử lý trường hợp response có markdown fences hoặc text thừa.
    """
    text = response_text.strip()
    
    # Loại bỏ markdown code fences nếu có
    # Pattern: ```json ... ``` hoặc ``` ... ```
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    fence_match = re.search(fence_pattern, text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    
    # Tìm JSON array trong text
    # Tìm vị trí [ đầu tiên và ] cuối cùng
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise ValueError(f"Không tìm thấy JSON array trong response:\n{text[:500]}")
    
    json_str = text[start_idx:end_idx + 1]
    
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Lỗi parse JSON: {e}\nJSON text:\n{json_str[:500]}")
    
    if not isinstance(result, list):
        raise ValueError(f"Response không phải là JSON array: {type(result)}")
    
    return result


def call_gemini_web(prompt: str, task_type: str) -> str:
    """
    Gửi prompt lên FastAPI server hàng đợi Web Gemini, và chờ đợi Extension hoàn tất trên trình duyệt.
    """
    import requests
    server_url = "http://127.0.0.1:8085"
    logger.info(f"[Web Gemini] Gửi prompt lên hàng đợi (loại={task_type})...")
    
    # 1. Thêm task vào hàng đợi
    try:
        r = requests.post(f"{server_url}/api/web-gemini/add-task", json={
            "task_type": task_type,
            "prompt": prompt
        })
        r.raise_for_status()
        task_id = r.json()["task_id"]
        logger.info(f"[Web Gemini] Đã tạo Task ID: {task_id}. Đang chờ Extension xử lý trên trình duyệt...")
    except Exception as e:
        raise RuntimeError(f"Không thể kết nối tới server Dashboard để tạo task Web Gemini: {e}")
        
    # 2. Vòng lặp chờ trạng thái hoàn thành
    check_interval = 2.0
    elapsed = 0.0
    max_wait = 600.0  # Chờ tối đa 10 phút
    
    while elapsed < max_wait:
        try:
            r = requests.get(f"{server_url}/api/web-gemini/status/{task_id}")
            r.raise_for_status()
            data = r.json()
            status = data["status"]
            
            if status == "completed":
                logger.info(f"[Web Gemini] Task {task_id} hoàn tất thành công!")
                return data["result"]
            elif status == "failed":
                raise RuntimeError(f"Task {task_id} thất bại trên trình duyệt: {data.get('error', 'Lỗi không xác định')}")
                
        except Exception as e:
            if "thất bại trên trình duyệt" in str(e):
                raise
            logger.warning(f"[Web Gemini] Lỗi khi check status: {e}. Sẽ thử lại sau 2 giây...")
            
        time.sleep(check_interval)
        elapsed += check_interval
        
    raise TimeoutError(f"Quá thời gian chờ {max_wait}s cho task Web Gemini {task_id}.")


def _call_gemini_batch(
    model: Optional[genai.GenerativeModel],
    sentences: list[dict],
    batch_offset: int = 0,
    max_retries: int = 3,
    batch_info: str = "1/1"
) -> list[dict]:
    """
    Gọi Gemini cho một batch câu, có hỗ trợ gọi qua Web Gemini nếu model=None.
    """
    system_prompt = _build_system_prompt()
    user_message = _build_user_message(sentences, batch_offset)
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"  Gọi Gemini batch [{batch_info}] (offset={batch_offset}, "
                f"size={len(sentences)}, attempt={attempt}/{max_retries})..."
            )
            
            if model is not None:
                response = model.generate_content(user_message)
                if not response.text:
                    raise ValueError("Gemini trả về response rỗng")
                response_text = response.text
            else:
                # Chế độ Web Gemini: Ghép cả system prompt vào cùng prompt gửi đi
                full_prompt = f"{system_prompt}\n\n{user_message}"
                response_text = call_gemini_web(full_prompt, f"prompt (Batch {batch_info})")
            
            prompts = _parse_gemini_response(response_text)
            
            # Validate: kiểm tra số lượng prompt trả về
            if len(prompts) != len(sentences):
                logger.warning(
                    f"  ⚠ Số prompt ({len(prompts)}) != số câu ({len(sentences)}). "
                    f"Chấp nhận kết quả."
                )
            
            # Validate: kiểm tra mỗi prompt có anchor và lock
            for p in prompts:
                prompt_text = p.get("prompt", "")
                if not prompt_text.startswith(config.IMAGE_PROMPT_STYLE_ANCHOR):
                    logger.warning(
                        f"  ⚠ Prompt index {p.get('index', '?')} thiếu style anchor, tự thêm."
                    )
                    p["prompt"] = config.IMAGE_PROMPT_STYLE_ANCHOR + " " + prompt_text
                
                if not prompt_text.rstrip().endswith(config.IMAGE_PROMPT_STYLE_LOCK):
                    logger.warning(
                        f"  ⚠ Prompt index {p.get('index', '?')} thiếu style lock, tự thêm."
                    )
                    if not p["prompt"].rstrip().endswith(config.IMAGE_PROMPT_STYLE_LOCK):
                        p["prompt"] = p["prompt"].rstrip() + " " + config.IMAGE_PROMPT_STYLE_LOCK
            
            logger.info(f"  ✓ Nhận được {len(prompts)} prompt từ batch này.")
            return prompts
            
        except Exception as e:
            logger.error(f"  ✗ Lỗi attempt {attempt}: {e}")
            err_msg = str(e).lower()
            if "429" in err_msg or "quota" in err_msg or "resourceexhausted" in err_msg or "resource exhausted" in err_msg:
                logger.info("⚠️  [Rate Limit Fallback] API bị quá giới hạn/hết quota (429). Tự động chuyển hướng yêu cầu sang Web Gemini (Gemini Web hoặc AI Studio) trên trình duyệt...")
                try:
                    full_prompt = f"{system_prompt}\n\n{user_message}"
                    response_text = call_gemini_web(full_prompt, f"prompt (Batch {batch_info})")
                    prompts = _parse_gemini_response(response_text)
                    for p in prompts:
                        prompt_text = p.get("prompt", "")
                        if not prompt_text.startswith(config.IMAGE_PROMPT_STYLE_ANCHOR):
                            p["prompt"] = config.IMAGE_PROMPT_STYLE_ANCHOR + " " + prompt_text
                        if not prompt_text.rstrip().endswith(config.IMAGE_PROMPT_STYLE_LOCK):
                            if not p["prompt"].rstrip().endswith(config.IMAGE_PROMPT_STYLE_LOCK):
                                p["prompt"] = p["prompt"].rstrip() + " " + config.IMAGE_PROMPT_STYLE_LOCK
                    logger.info(f"  ✓ Nhận được {len(prompts)} prompt từ Web Gemini.")
                    return prompts
                except Exception as web_err:
                    logger.error(f"  ✗ Lỗi khi fallback sang Web Gemini: {web_err}")

            if attempt < max_retries:
                if "429" in err_msg or "quota" in err_msg or "resourceexhausted" in err_msg or "resource exhausted" in err_msg:
                    wait_time = 45  # Đợi 45 giây để reset quota của Gemini Free Tier
                    logger.info(f"  [Rate Limit] Phát hiện lỗi 429/Quota. Đợi {wait_time}s để reset quota trước khi thử lại...")
                else:
                    wait_time = 2 ** attempt  # Exponential backoff thường: 2s, 4s...
                    logger.info(f"  Chờ {wait_time}s rồi thử lại...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(
                    f"Không thể tạo prompt sau {max_retries} lần thử. Lỗi cuối: {e}"
                )
    
    return []  # Không bao giờ đến đây nhưng để type checker vui


def generate_image_prompts(project_dir: str) -> list[dict]:
    """
    Đọc timing.json, gửi lên Gemini để tạo image prompt cho từng câu.
    
    Args:
        project_dir: Đường dẫn thư mục project (vd: d:/Youtube/output/my_project)
        
    Returns:
        Danh sách dict: [{"index": 0, "timestamp": "00:00", "prompt": "..."}]
    """
    # ── 1. Đọc timing.json ──
    timing_path = os.path.join(project_dir, "timing.json")
    if not os.path.exists(timing_path):
        raise FileNotFoundError(f"Không tìm thấy timing.json tại: {timing_path}")
    
    with open(timing_path, "r", encoding="utf-8") as f:
        timing_data = json.load(f)
    
    if not timing_data:
        raise ValueError("timing.json rỗng, không có câu nào để tạo prompt.")
    
    logger.info(f"📖 Đọc được {len(timing_data)} câu từ timing.json")
    
    # ── 2. Cấu hình Gemini hoặc Web Gemini ──
    use_web = (config.GEMINI_PROMPT_MODEL == "web-gemini")
    
    if not use_web:
        genai.configure(api_key=config.GEMINI_API_KEY)
        system_prompt = _build_system_prompt()
        model = genai.GenerativeModel(
            model_name=config.GEMINI_PROMPT_MODEL,
            system_instruction=system_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.9,
            ),
        )
    else:
        model = None
    
    # ── 3. Chia batch nếu cần và gọi Gemini ──
    all_prompts: list[dict] = []
    total_sentences = len(timing_data)
    
    if total_sentences <= BATCH_SIZE:
        # Chỉ cần 1 lần gọi
        logger.info(f"🎨 Tạo prompt cho {total_sentences} câu (1 batch)...")
        all_prompts = _call_gemini_batch(model, timing_data, batch_offset=0, batch_info="1/1")
    else:
        # Chia thành nhiều batch
        num_batches = (total_sentences + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(
            f"🎨 Tạo prompt cho {total_sentences} câu, chia thành {num_batches} batch "
            f"(mỗi batch tối đa {BATCH_SIZE} câu)..."
        )
        
        for batch_idx in range(num_batches):
            start = batch_idx * BATCH_SIZE
            end = min(start + BATCH_SIZE, total_sentences)
            batch = timing_data[start:end]
            
            logger.info(f"\n── Batch {batch_idx + 1}/{num_batches} (câu {start}–{end - 1}) ──")
            
            batch_prompts = _call_gemini_batch(
                model, 
                batch, 
                batch_offset=start, 
                batch_info=f"{batch_idx + 1}/{num_batches}"
            )
            all_prompts.extend(batch_prompts)
            
            # Ghi nhận kết quả từng phần (mỗi khi xong 1 batch) để frontend nhận diện được ngay
            partial_prompts = sorted(all_prompts, key=lambda x: x.get("index", 0))
            for p in partial_prompts:
                if "timestamp" not in p or not p["timestamp"]:
                    idx = p.get("index", 0)
                    if idx < len(timing_data):
                        p["timestamp"] = _seconds_to_mmss(timing_data[idx]["start"])
                        
            prompts_json_path = os.path.join(project_dir, "prompts.json")
            try:
                with open(prompts_json_path, "w", encoding="utf-8") as f:
                    json.dump(partial_prompts, f, indent=2, ensure_ascii=False)
                
                prompts_txt_path = os.path.join(project_dir, "prompts.txt")
                with open(prompts_txt_path, "w", encoding="utf-8") as f:
                    for i, p in enumerate(partial_prompts):
                        timestamp = p.get("timestamp", "??:??")
                        prompt_text = p.get("prompt", "")
                        f.write(f"[{timestamp}] {prompt_text}")
                        if i < len(partial_prompts) - 1:
                            f.write("\n\n")
            except Exception as save_err:
                logger.warning(f"Không thể lưu kết quả từng phần: {save_err}")
    
    # ── 4. Sắp xếp theo index ──
    all_prompts.sort(key=lambda x: x.get("index", 0))
    
    # ── 5. Đảm bảo mỗi prompt có timestamp ──
    for p in all_prompts:
        if "timestamp" not in p or not p["timestamp"]:
            idx = p.get("index", 0)
            if idx < len(timing_data):
                p["timestamp"] = _seconds_to_mmss(timing_data[idx]["start"])
    
    # ── 6. Lưu prompts.txt ──
    prompts_txt_path = os.path.join(project_dir, "prompts.txt")
    with open(prompts_txt_path, "w", encoding="utf-8") as f:
        for i, p in enumerate(all_prompts):
            timestamp = p.get("timestamp", "??:??")
            prompt_text = p.get("prompt", "")
            f.write(f"[{timestamp}] {prompt_text}")
            if i < len(all_prompts) - 1:
                f.write("\n\n")  # Dòng trống giữa các prompt
    
    logger.info(f"📝 Đã lưu {len(all_prompts)} prompt vào: {prompts_txt_path}")
    
    # ── 7. Lưu prompts.json ──
    prompts_json_path = os.path.join(project_dir, "prompts.json")
    with open(prompts_json_path, "w", encoding="utf-8") as f:
        json.dump(all_prompts, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📋 Đã lưu structured data vào: {prompts_json_path}")
    logger.info(f"✅ Hoàn thành! Tổng cộng {len(all_prompts)} image prompt.")
    
    return all_prompts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST BLOCK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Tạo image prompt cho từng câu trong timing.json"
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=None,
        help="Đường dẫn thư mục project (chứa timing.json)"
    )
    args = parser.parse_args()
    
    # Nếu không có argument, tạo test data
    if args.project_dir:
        project_dir = args.project_dir
    else:
        # Tạo thư mục test với timing.json mẫu
        test_dir = os.path.join(config.BASE_OUTPUT_DIR, "_test_prompts")
        os.makedirs(test_dir, exist_ok=True)
        
        # Tạo timing.json mẫu
        sample_timing = [
            {"text": "You wake up when your body is ready.", "start": 0.0, "end": 2.5},
            {"text": "No alarm, no schedule, no boss.", "start": 2.5, "end": 5.0},
            {"text": "For 99 percent of human history, this wasn't a hypothetical.", "start": 5.0, "end": 9.0},
            {"text": "Your ancestors slept under the stars.", "start": 9.0, "end": 12.0},
            {"text": "They hunted when they were hungry.", "start": 12.0, "end": 14.5},
            {"text": "Survival was hard, but life was simple.", "start": 14.5, "end": 18.0},
        ]
        
        timing_path = os.path.join(test_dir, "timing.json")
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(sample_timing, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📂 Tạo test data tại: {test_dir}")
        project_dir = test_dir
    
    try:
        results = generate_image_prompts(project_dir)
        
        print("\n" + "=" * 60)
        print("KẾT QUẢ")
        print("=" * 60)
        for p in results:
            print(f"\n[{p.get('timestamp', '??:??')}] (index {p.get('index', '?')})")
            print(f"  {p.get('prompt', 'N/A')[:120]}...")
        print(f"\n✅ Tổng: {len(results)} prompt")
        
    except FileNotFoundError as e:
        logger.error(f"❌ {e}")
    except RuntimeError as e:
        logger.error(f"❌ Pipeline lỗi: {e}")
    except Exception as e:
        logger.error(f"❌ Lỗi không mong đợi: {e}", exc_info=True)
