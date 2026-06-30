"""
=============================================================
  SCRIPT_GENERATOR.PY — Tạo kịch bản video bằng Gemini AI
=============================================================
Module này sử dụng Google Generative AI SDK để:
  1. Tạo 5 ý tưởng chủ đề viral về con người cổ đại (Stage 1)
  2. Tạo kịch bản tường thuật đầy đủ cho chủ đề đã chọn (Stage 2)
"""

import sys
import os
import json
import re

# Thêm thư mục gốc của dự án vào sys.path để import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

import google.generativeai as genai

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cấu hình Gemini API hoặc Web Gemini
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_use_web = True
_model = None


def call_gemini_web(prompt: str, task_type: str) -> str:
    """
    Gửi prompt lên FastAPI server hàng đợi Web Gemini, và chờ đợi Extension hoàn tất trên trình duyệt.
    """
    import requests
    import time
    server_url = "http://127.0.0.1:8085"
    print(f"[Web Gemini] Gửi prompt lên hàng đợi (loại={task_type})...")
    
    # 1. Thêm task vào hàng đợi
    try:
        r = requests.post(f"{server_url}/api/web-gemini/add-task", json={
            "task_type": task_type,
            "prompt": prompt
        })
        r.raise_for_status()
        task_id = r.json()["task_id"]
        print(f"[Web Gemini] Đã tạo Task ID: {task_id}.\n👉 ĐANG CHỜ EXTENSION THỰC THI TRÊN TRÌNH DUYỆT!\n💡 HƯỚNG DẪN: Bạn cần mở trang https://gemini.google.com hoặc https://aistudio.google.com bằng trình duyệt Chrome đã cài Extension, rồi bấm nút 'Kết nối' và 'Bắt đầu chạy' trên bảng điều khiển nổi ở góc bên phải để chạy tự động hóa.")
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
                print(f"[Web Gemini] Task {task_id} hoàn tất thành công!")
                return data["result"]
            elif status == "failed":
                raise RuntimeError(f"Task {task_id} thất bại trên trình duyệt: {data.get('error', 'Lỗi không xác định')}")
                
        except Exception as e:
            if "thất bại trên trình duyệt" in str(e):
                raise
            print(f"[Web Gemini] Lỗi khi check status: {e}. Sẽ thử lại sau 2 giây...")
            
        time.sleep(check_interval)
        elapsed += check_interval
        
    raise TimeoutError(f"Quá thời gian chờ {max_wait}s cho task Web Gemini {task_id}.")


def _extract_json_from_response(text: str) -> list[dict]:
    """
    Trích xuất mảng JSON từ response của Gemini.
    Gemini đôi khi bọc JSON trong markdown code block (```json ... ```),
    hàm này xử lý cả 2 trường hợp: có và không có code block.
    """
    # Thử tìm JSON trong code block markdown trước
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()
    else:
        # Tìm mảng JSON trực tiếp trong text
        bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
        if bracket_match:
            json_str = bracket_match.group(0).strip()
        else:
            raise ValueError(f"Không tìm thấy JSON hợp lệ trong response:\n{text[:500]}")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Lỗi parse JSON: {e}\nNội dung:\n{json_str[:500]}")

    if not isinstance(data, list):
        raise ValueError(f"JSON trả về không phải là mảng: {type(data)}")

    return data


def generate_topics(language: str = "vi") -> list[dict]:
    """
    Stage 1: Tạo 5 ý tưởng chủ đề viral về con người cổ đại / tiền sử.

    Returns:
        list[dict]: Danh sách 5 dict có dạng [{"id": 1, "title": "..."}, ...]
    """
    lang_desc = "Vietnamese" if language == "vi" else "English"
    lang_prompt = "The analysis and title must be in Vietnamese." if language == "vi" else "The analysis and title must be in English. For English, address the viewer as 'you'."

    prompt = f"""{config.TOPIC_STRATEGIST_PERSONA}

{config.CHANNEL_KNOWLEDGE_BASE}

{config.PROVEN_VIRAL_TOPIC_ANGLES}

Based on the channel DNA and proven viral angles above, generate exactly 5 fresh, \
unique, and highly clickable video title ideas.
For each title idea, provide a brief analysis (1-2 sentences in {lang_desc} explaining why this topic will go viral, e.g., what human curiosity/desire/fear it triggers) and a virality score (a float between 1.0 and 10.0, e.g. 9.5).

Requirements:
- Each title must be specific, vivid, and curiosity-driven.
- Avoid generic or overused topics. Go for surprising, counterintuitive, or taboo angles.
- {lang_prompt}
- Return ONLY a valid JSON array with no extra text, no markdown, no explanation.

Output format (strict JSON, nothing else):
[
  {{
    "id": 1,
    "title": "Tên chủ đề hoặc Title ở đây",
    "analysis": "Phân tích lý do thu hút người xem bằng ngôn ngữ yêu cầu",
    "score": 9.5
  }},
  {{
    "id": 2,
    "title": "Tên chủ đề hoặc Title thứ hai",
    "analysis": "Phân tích lý do thu hút bằng ngôn ngữ yêu cầu",
    "score": 8.8
  }},
  {{
    "id": 3,
    "title": "Tên chủ đề hoặc Title thứ ba",
    "analysis": "Phân tích lý do thu hút bằng ngôn ngữ yêu cầu",
    "score": 9.2
  }},
  {{
    "id": 4,
    "title": "Tên chủ đề hoặc Title thứ tư",
    "analysis": "Phân tích lý do thu hút bằng ngôn ngữ yêu cầu",
    "score": 9.0
  }},
  {{
    "id": 5,
    "title": "Tên chủ đề hoặc Title thứ năm",
    "analysis": "Phân tích lý do thu hút bằng ngôn ngữ yêu cầu",
    "score": 9.6
  }}
]"""

    print("🧠 Đang tạo 5 ý tưởng chủ đề viral...")

    try:
        if _model is not None:
            try:
                response = _model.generate_content(prompt)
                response_text = response.text
            except Exception as api_err:
                err_msg = str(api_err).lower()
                if "429" in err_msg or "quota" in err_msg or "resourceexhausted" in err_msg or "resource_exhausted" in err_msg:
                    print("⚠️  [Rate Limit Fallback] API bị quá giới hạn/hết quota (429). Tự động chuyển hướng yêu cầu sang Web Gemini (Gemini Web hoặc AI Studio) trên trình duyệt...")
                    response_text = call_gemini_web(prompt, "script")
                else:
                    raise api_err
        else:
            response_text = call_gemini_web(prompt, "script")
            
        topics = _extract_json_from_response(response_text)

        # Đảm bảo chỉ lấy đúng 5 topic
        topics = topics[:5]

        # Hiển thị danh sách chủ đề
        print("\n" + "=" * 60)
        print("📋 CÁC CHỦ ĐỀ GỢI Ý:")
        print("=" * 60)
        for topic in topics:
            print(f"  {topic['id']}. {topic['title']}")
        print("=" * 60 + "\n")

        return topics

    except Exception as e:
        print(f"❌ Lỗi khi tạo chủ đề: {e}")
        raise


def generate_script(topic_title: str, project_dir: str) -> str:
    """
    Stage 2: Tạo kịch bản tường thuật đầy đủ cho chủ đề đã chọn.

    Args:
        topic_title: Tiêu đề chủ đề đã chọn.
        project_dir: Đường dẫn thư mục dự án để lưu script.txt.

    Returns:
        str: Nội dung kịch bản hoàn chỉnh.
    """
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

    lang_instruction = ""
    if language == "vi":
        lang_instruction = "\n8. LANGUAGE: The entire script MUST be written in Vietnamese. Translate all stories and scientific details into natural, fluent Vietnamese. Address the viewer as 'bạn', 'tổ tiên của bạn', 'cơ thể của bạn', 'não bộ của bạn'. Never use 'chúng tôi', 'tôi', or 'ta'."
    else:
        lang_instruction = "\n8. LANGUAGE: The entire script MUST be written in English. Address the viewer as 'you', 'your ancestors', 'your body', 'your brain'. Never use 'we', 'I', or 'our'."

    prompt = f"""{config.SCRIPTWRITER_PERSONA}

{config.CHANNEL_KNOWLEDGE_BASE}

Write a complete narration script for this video topic:
"{topic_title}"

STRICT REQUIREMENTS:
1. LENGTH: The script must be between 1500 and 2400 words. Aim for approximately 1800-2000 words.
2. PERSPECTIVE: Write entirely in 2nd person — address the viewer as "you", "your ancestors", \
"your body", "your brain". Never use "we", "I", or "our".
3. VOICE: Calm, intelligent, slightly poetic. As if a thoughtful friend is explaining something \
fascinating over a late-night campfire.
4. RHYTHM PATTERN: Follow this sentence rhythm consistently:
   Short sentence. Short sentence. One longer sentence that builds depth and detail. \
Short sentence. Question?
5. EVIDENCE RULE: Weave in at least 3 real, named researchers, studies, or archaeological sites \
naturally into the narration. Never invent names — only use real ones.
6. NARRATIVE ARC:
   - Hook: Open by dropping the viewer inside an ancestral sensory moment in 2nd person.
   - Reframe: Pivot with a striking contrast or statistic.
   - Evidence stack: Named study → cross-cultural / skeletal / archaeological confirmation.
   - Scene reconstruction: "So let's reconstruct..." — a vivid, concrete scene.
   - Counterintuitive twist: Flip an assumption.
   - Modern mirror: Reflect the ancient truth onto something the viewer does today.
   - Closing line: Echo the very first line, completely reframed.
7. FORMAT: Pure narration ONLY. No markdown formatting. No headers. No section titles. \
No stage directions. No asterisks. No bold or italic markers. No "[pause]" or "(beat)" notes. \
No music cues. Just clean, flowing narration text that can be read aloud directly by a TTS engine.{lang_instruction}

Write the complete script now:"""

    print(f"✍️  Đang viết kịch bản cho: \"{topic_title}\"...")
    print("    (Quá trình này có thể mất 30-60 giây...)")

    try:
        if _model is not None:
            try:
                response = _model.generate_content(prompt)
                script_text = response.text.strip()
            except Exception as api_err:
                err_msg = str(api_err).lower()
                if "429" in err_msg or "quota" in err_msg or "resourceexhausted" in err_msg or "resource_exhausted" in err_msg:
                    print("⚠️  [Rate Limit Fallback] API bị quá giới hạn/hết quota (429). Tự động chuyển hướng yêu cầu sang Web Gemini (Gemini Web hoặc AI Studio) trên trình duyệt...")
                    script_text = call_gemini_web(prompt, "script").strip()
                else:
                    raise api_err
        else:
            script_text = call_gemini_web(prompt, "script").strip()

        # Tạo thư mục dự án nếu chưa có
        os.makedirs(project_dir, exist_ok=True)

        # Lưu kịch bản vào file
        script_path = os.path.join(project_dir, "script.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_text)

        # Đếm số từ và hiển thị thông tin
        word_count = len(script_text.split())
        print(f"\n✅ Kịch bản đã được tạo thành công!")
        print(f"   📝 Số từ: {word_count}")
        print(f"   💾 Đã lưu tại: {script_path}")

        return script_text

    except Exception as e:
        print(f"❌ Lỗi khi tạo kịch bản: {e}")
        raise


def select_topic(topics: list[dict]) -> dict:
    """
    Hiển thị danh sách chủ đề và cho người dùng chọn.

    Args:
        topics: Danh sách các dict chủ đề [{"id": 1, "title": "..."}, ...]

    Returns:
        dict: Chủ đề được chọn.
    """
    while True:
        try:
            choice = input("👉 Chọn chủ đề (nhập số 1-5): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= 5:
                # Tìm topic theo id hoặc theo vị trí index
                selected = None
                for topic in topics:
                    if topic.get("id") == choice_num:
                        selected = topic
                        break

                # Fallback: dùng index nếu không tìm thấy theo id
                if selected is None:
                    selected = topics[choice_num - 1]

                print(f"\n✅ Đã chọn: \"{selected['title']}\"\n")
                return selected
            else:
                print("⚠️  Vui lòng nhập số từ 1 đến 5.")

        except ValueError:
            print("⚠️  Vui lòng nhập một số hợp lệ.")
        except (IndexError, KeyError):
            print("⚠️  Lựa chọn không hợp lệ. Vui lòng thử lại.")


def _sanitize_dirname(title: str) -> str:
    """
    Chuyển tiêu đề thành tên thư mục an toàn.
    Loại bỏ ký tự đặc biệt, thay khoảng trắng bằng gạch dưới, giới hạn độ dài.
    """
    # Loại bỏ ký tự không phải chữ, số, khoảng trắng, hoặc gạch ngang
    safe_name = re.sub(r"[^\w\s-]", "", title)
    # Thay khoảng trắng bằng gạch dưới
    safe_name = re.sub(r"\s+", "_", safe_name.strip())
    # Giới hạn độ dài 80 ký tự
    safe_name = safe_name[:80]
    return safe_name


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STANDALONE TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print("=" * 60)
    print("🎬 SCRIPT GENERATOR — Video Automation Pipeline")
    print("=" * 60)

    # Stage 1: Tạo danh sách chủ đề
    topics = generate_topics()

    # Stage 2: Người dùng chọn chủ đề
    selected = select_topic(topics)

    # Tạo thư mục dự án
    project_name = _sanitize_dirname(selected["title"])
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, project_name)
    os.makedirs(project_dir, exist_ok=True)
    print(f"📁 Thư mục dự án: {project_dir}")

    # Stage 3: Tạo kịch bản
    script = generate_script(selected["title"], project_dir)

    # Hiển thị preview
    print("\n" + "=" * 60)
    print("📖 PREVIEW (500 ký tự đầu tiên):")
    print("=" * 60)
    print(script[:500] + "...")
    print("=" * 60)
    print("\n🎉 Hoàn tất! Pipeline sẵn sàng cho bước tiếp theo.")
