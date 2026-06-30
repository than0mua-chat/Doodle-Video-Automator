"""
=============================================================
  DASHBOARD.PY — Backend Server cho Web Dashboard Video Doodle
=============================================================
Khởi chạy server bằng lệnh:
    python dashboard.py
    Hoặc: uvicorn dashboard:app --reload --port 8000
"""

import os
import sys

# Đảm bảo console luôn sử dụng encoding UTF-8 để tránh lỗi charmap trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import json
import subprocess
import re
import glob
import shutil
import asyncio
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Query, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Đảm bảo import config và các module khác đúng đường dẫn
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

app = FastAPI(
    title="Doodle Video Automator",
    description="Giao diện quản lý quy trình sản xuất video hoạt hình người que"
)

# Cấu hình CORS để chạy thử nghiệm dễ dàng
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# QUẢN LÝ TIẾN TRÌNH CHẠY PIPELINE (BACKGROUND PROCESSES)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Lưu thông tin tiến trình đang chạy dưới dạng: { project_name: (subprocess.Popen, log_file_handle) }
active_processes = {}
active_project_name = None

async def monitor_process(project_name: str, process: subprocess.Popen, log_file):
    """Giám sát tiến trình chạy trong background và đóng file log khi hoàn tất."""
    try:
        while process.poll() is None:
            await asyncio.sleep(0.5)
    except Exception as e:
        print(f"Error monitoring process {project_name}: {e}")
    finally:
        log_file.close()
        if project_name in active_processes:
            del active_processes[project_name]
        print(f"Process for project '{project_name}' finished.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API CẤU HÌNH HỆ THỐNG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONFIG_KEYS = [
    "GEMINI_API_KEY", "ELEVENLABS_API_KEY", "TTS_ENGINE", "EDGE_TTS_VOICE",
    "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL_ID", "IMAGE_MODE",
    "GEMINI_SCRIPT_MODEL", "GEMINI_PROMPT_MODEL", "GEMINI_IMAGE_MODEL",
    "VIDEO_WIDTH", "VIDEO_HEIGHT", "VIDEO_FPS", "WOBBLE_INTENSITY",
    "CHANNEL_KNOWLEDGE_BASE", "PROVEN_VIRAL_TOPIC_ANGLES", "VISUAL_STYLE_DNA",
    "IMAGE_PROMPT_STYLE_ANCHOR", "IMAGE_PROMPT_STYLE_LOCK", "PROPOSED_IDEAS"
]

@app.get("/api/config")
def get_dashboard_config():
    """Lấy cấu hình hiện tại."""
    data = {}
    for key in CONFIG_KEYS:
        data[key] = getattr(config, key, "")
    return data

@app.post("/api/config")
def update_dashboard_config(update_data: dict):
    """Cập nhật cấu hình và lưu vào settings.json."""
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
    
    # Chuẩn hóa kiểu dữ liệu số
    for key in ["VIDEO_WIDTH", "VIDEO_HEIGHT", "VIDEO_FPS", "WOBBLE_INTENSITY"]:
        if key in update_data:
            try:
                update_data[key] = int(update_data[key])
            except (ValueError, TypeError):
                pass

    # Lưu xuống settings.json
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(update_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể ghi file settings.json: {e}")

    # Cập nhật trực tiếp vào bộ nhớ module config để các module khác nhận được ngay lập tức
    for key, val in update_data.items():
        if key in CONFIG_KEYS:
            setattr(config, key, val)

    return {"status": "success", "message": "Đã cập nhật và lưu cấu hình hệ thống!"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API QUẢN LÝ HỒ SƠ KÊNH (PROFILE MANAGEMENT)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

active_profile_id = "ancient_history"

@app.get("/api/profiles")
def get_profiles():
    """Liệt kê các hồ sơ kênh có sẵn."""
    profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
    if not os.path.exists(profiles_dir):
        os.makedirs(profiles_dir, exist_ok=True)
        
    profiles = []
    for entry in os.listdir(profiles_dir):
        if entry.lower().endswith(".json"):
            path = os.path.join(profiles_dir, entry)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile_info = data.copy()
                profile_info["profile_id"] = data.get("profile_id", entry[:-5])
                profile_info["profile_name"] = data.get("profile_name", entry[:-5])
                profile_info["profile_description"] = data.get("profile_description", "")
                profiles.append(profile_info)
            except Exception:
                pass
    return profiles

class CreateProfilePayload(BaseModel):
    profile_id: str
    profile_name: str
    profile_description: str
    use_ai: bool = False
    ai_prompt: Optional[str] = None
    reference_url: Optional[str] = None
    profile_data: Optional[dict] = None

def extract_metadata_from_url(url: str) -> str:
    """Cào thông tin cơ bản từ URL (tiêu đề, mô tả, nội dung mẫu)."""
    if not url or not url.strip():
        return ""
    import requests
    from bs4 import BeautifulSoup
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        title = soup.title.string if soup.title else ""
        
        meta_desc = ""
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc_tag:
            meta_desc = meta_desc_tag.get('content', '')
            
        # Lấy một ít văn bản thô mẫu
        for s in soup(['script', 'style', 'nav', 'footer']):
            s.decompose()
        text = soup.get_text(separator=' ')
        text = ' '.join(text.split())
        clean_text = text[:3000]
        
        return f"\n--- REFERENCE CONTENT FROM URL ({url}) ---\nTitle: {title}\nDescription: {meta_desc}\nText Sample:\n{clean_text}\n"
    except Exception as e:
        return f"\n--- REFERENCE CONTENT FROM URL ({url}) ---\n(Lỗi khi cào dữ liệu URL: {e})\n"

@app.post("/api/profiles")
def create_profile(payload: CreateProfilePayload):
    """Tạo hồ sơ kênh mới, hỗ trợ tự sinh bằng AI."""
    profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    
    profile_id = re.sub(r"[^\w-]", "", payload.profile_id.lower().strip())
    if not profile_id:
        raise HTTPException(status_code=400, detail="ID hồ sơ không hợp lệ")
        
    profile_path = os.path.join(profiles_dir, f"{profile_id}.json")
    
    if payload.use_ai:
        if not payload.ai_prompt or not payload.ai_prompt.strip():
            raise HTTPException(status_code=400, detail="Cần nhập mô tả ngách để AI sinh nội dung")
            
        if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE" or not config.GEMINI_API_KEY.strip():
            raise HTTPException(status_code=400, detail="Chưa cấu hình GEMINI_API_KEY để dùng AI!")
            
        try:
            # Thu thập nội dung từ URL tham chiếu nếu có
            url_context = ""
            if payload.reference_url and payload.reference_url.strip():
                url_context = extract_metadata_from_url(payload.reference_url.strip())
            
            import google.generativeai as genai
            genai.configure(api_key=config.GEMINI_API_KEY)
            model = genai.GenerativeModel(config.GEMINI_SCRIPT_MODEL)
            
            prompt = f"""You are a branding expert and YouTube content director. Based on this niche description:
"{payload.ai_prompt}"
{url_context}

Generate a complete Channel DNA profile JSON.
The JSON must follow this exact structure (do not add extra keys):
{{
  "profile_id": "{profile_id}",
  "profile_name": "{payload.profile_name}",
  "profile_description": "{payload.profile_description}",
  "TOPIC_STRATEGIST_PERSONA": "A detailed role instruction (1-2 sentences) for generating viral, clickable YouTube video title ideas about this niche.",
  "SCRIPTWRITER_PERSONA": "A detailed role instruction (1-2 sentences) for writing YouTube explainer narration scripts in the 2nd person (you, your...) about this niche.",
  "CHANNEL_KNOWLEDGE_BASE": "Detailed scriptwriting rules (Markdown format), including: Niche definition, Video Format, Hook formula, Script rhythm, Narrative arc (Hook -> Reframe -> evidence/studies -> concrete scene -> counterintuitive twist -> modern mirror -> final echo), and evidence rules.",
  "PROVEN_VIRAL_TOPIC_ANGLES": "At least 5 specific video title angles/templates with curiosity-gaps that work well in this niche.",
  "VISUAL_STYLE_DNA": "Detailed art style guidelines (Markdown format) for a hand-drawn 2D doodle cartoon animation with flat solid colors and bold black outlines. Define the main character ('you') with specific features/outfits tailored to this niche, character variants, animals/objects, backgrounds with emotional color schemes, on-screen text instructions, and a specific color palette (hex codes).",
  "IMAGE_PROMPT_STYLE_ANCHOR": "Hand-drawn 2D doodle cartoon animation, flat solid colors, bold black hand-drawn outlines, slightly wobbly imperfect marker lines,",
  "IMAGE_PROMPT_STYLE_LOCK": "no gradients, no drop shadows, no photographic textures, no photorealism, no 3D render, no realistic faces, no anime, 16:9 widescreen, simple educational YouTube explainer doodle style.",
  "TTS_ENGINE": "edge-tts",
  "EDGE_TTS_VOICE": "vi-VN-HoaiAnNeural",
  "ELEVENLABS_VOICE_ID": "pNInz6obpgDQGcFmaJgB",
  "ELEVENLABS_MODEL_ID": "eleven_multilingual_v2",
  "PROPOSED_IDEAS": "Detailed evaluation of 5 proposed script ideas for this channel (Markdown format). For each idea, provide: 1. Title/Concept; 2. Proposed Reason & Appeal; 3. Scoring (scale 1-10) for Virality Potential, Feasibility, and Audience Engagement; 4. Production Limits & Peak Points (high-retention moments); 5. Productivity & Efficiency Tips (how to create faster, reuse assets)."
}}

STRICT RULES:
- Make all visual styling and script DNA perfectly aligned with the requested niche '{payload.ai_prompt}' and the reference link context if provided.
- The visual style must STILL BE DOODLE (hand-drawn 2D cartoon, flat solid colors, bold black outlines) but the specific character clothing, hair, objects, and backgrounds should be adjusted to fit the niche (e.g. for finance: suit stick figure, gold coins, graph charts background, etc.).
- Do not output markdown fences or wrap the JSON in ```json ... ```. Just return the raw JSON object string.
"""
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", response_text, re.DOTALL)
            if code_block_match:
                json_str = code_block_match.group(1).strip()
            else:
                bracket_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if bracket_match:
                    json_str = bracket_match.group(0).strip()
                else:
                    json_str = response_text
                    
            profile_data = json.loads(json_str)
            profile_data["profile_id"] = profile_id
            profile_data["profile_name"] = payload.profile_name
            profile_data["profile_description"] = payload.profile_description
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi AI sinh profile: {e}")
    else:
        if payload.profile_data:
            profile_data = payload.profile_data
            profile_data["profile_id"] = profile_id
            profile_data["profile_name"] = payload.profile_name
            profile_data["profile_description"] = payload.profile_description
        else:
            profile_data = {
                "profile_id": profile_id,
                "profile_name": payload.profile_name,
                "profile_description": payload.profile_description,
                "TOPIC_STRATEGIST_PERSONA": "You are a YouTube content strategist specializing in viral educational videos.",
                "SCRIPTWRITER_PERSONA": "You are an expert YouTube scriptwriter.",
                "CHANNEL_KNOWLEDGE_BASE": "### CONTENT & SCRIPT DNA\n- **Niche:** " + payload.profile_description,
                "PROVEN_VIRAL_TOPIC_ANGLES": "### PROVEN VIRAL TOPIC ANGLES\n1. Angle...",
                "VISUAL_STYLE_DNA": "### VISUAL STYLE DNA\n- **Art style:** Hand-drawn 2D doodle cartoon animation — flat solid colors, bold outlines.",
                "IMAGE_PROMPT_STYLE_ANCHOR": "Hand-drawn 2D doodle cartoon animation, flat solid colors, bold black hand-drawn outlines, slightly wobbly imperfect marker lines,",
                "IMAGE_PROMPT_STYLE_LOCK": "no gradients, no drop shadows, no photographic textures, no photorealism, no 3D render, no realistic faces, no anime, 16:9 widescreen, simple educational YouTube explainer doodle style.",
                "TTS_ENGINE": "edge-tts",
                "EDGE_TTS_VOICE": "vi-VN-HoaiAnNeural",
                "ELEVENLABS_VOICE_ID": "pNInz6obpgDQGcFmaJgB",
                "ELEVENLABS_MODEL_ID": "eleven_multilingual_v2",
                "PROPOSED_IDEAS": "### ĐỀ XUẤT 5 KỊCH BẢN & PHÂN TÍCH\n1. Ý tưởng 1...\n"
            }
            
    try:
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể ghi file profile: {e}")
        
    return {"status": "success", "profile_id": profile_id, "profile_path": profile_path}

class AnalyzeStylePayload(BaseModel):
    url: str

@app.post("/api/profiles/analyze-style")
def analyze_style_api(payload: AnalyzeStylePayload):
    """Phân tích phong cách từ video/playlist mẫu bằng AI và gợi ý thông tin kênh."""
    if not payload.url or not payload.url.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập link URL hợp lệ!")
        
    if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE" or not config.GEMINI_API_KEY.strip():
        raise HTTPException(status_code=400, detail="Chưa cấu hình GEMINI_API_KEY để dùng AI!")
        
    # 1. Thu thập metadata từ URL
    meta = extract_metadata_from_url(payload.url.strip())
    
    # 2. Gọi Gemini để phân tích và đề xuất
    import google.generativeai as genai
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_PROMPT_MODEL)
    
    prompt = f"""
Bạn là một đạo diễn nội dung và chuyên gia xây dựng kênh hoạt hình vẽ tay.
Hãy phân tích thông tin cào được từ URL mẫu sau:
{meta}

Dựa trên chủ đề của video/playlist đó, hãy gợi ý cấu hình để tạo một kênh hoạt hình người que vẽ tay (doodle cartoon) học hỏi/bắt chước phong cách đó.
Hãy trả về một đối tượng JSON thô (không có block ```json), gồm các trường sau:
{{
  "suggested_id": "Mã ID kênh viết liền, không dấu, chữ thường, dùng tiếng Anh hoặc không dấu viết liền (ví dụ: tai_chinh_ca_nhan, lich_su_viet_nam)",
  "suggested_name": "Tên kênh hiển thị tiếng Việt ngắn gọn, thu hút (ví dụ: Tài Chính Cá Nhân, Lịch Sử Hùng Tráng)",
  "suggested_description": "Mô tả ngắn gọn ngách nội dung kênh (khoảng 1 câu)",
  "suggested_concept_prompt": "Mô tả chi tiết bằng tiếng Việt về concept kênh và phong cách visual để đưa vào AI sinh DNA (khoảng 3-4 câu). Mô tả rõ: nhân vật chính (người que mặc đồ gì, hoạt cảnh xung quanh là gì phù hợp chủ đề), cách viết kịch bản hướng tới đối tượng nào, màu sắc chủ đạo là gì)."
}}
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Loại bỏ code block nếu có
        code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1).strip()
        else:
            bracket_match = re.search(r"\{.*\}", text, re.DOTALL)
            if bracket_match:
                json_str = bracket_match.group(0).strip()
            else:
                json_str = text
                
        result = json.loads(json_str)
        return {
            "status": "success",
            "suggested_id": result.get("suggested_id", "kenh_moi"),
            "suggested_name": result.get("suggested_name", "Kênh Mới"),
            "suggested_description": result.get("suggested_description", ""),
            "suggested_concept_prompt": result.get("suggested_concept_prompt", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích style bằng AI: {e}")

@app.get("/api/active-profile")
def get_active_profile():
    """Lấy thông tin profile đang hoạt động hiện tại."""
    global active_profile_id
    profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
    profile_path = os.path.join(profiles_dir, f"{active_profile_id}.json")
    
    if not os.path.exists(profile_path):
        active_profile_id = "ancient_history"
        profile_path = os.path.join(profiles_dir, "ancient_history.json")
        
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc profile hoạt động: {e}")

class SetActiveProfilePayload(BaseModel):
    profile_id: str

@app.post("/api/active-profile")
def set_active_profile(payload: SetActiveProfilePayload):
    """Thiết lập profile đang hoạt động."""
    global active_profile_id
    profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
    profile_path = os.path.join(profiles_dir, f"{payload.profile_id}.json")
    
    if not os.path.exists(profile_path):
        raise HTTPException(status_code=404, detail="Hồ sơ không tồn tại")
        
    active_profile_id = payload.profile_id
    config.load_channel_profile(active_profile_id)
    return {"status": "success", "active_profile_id": active_profile_id}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API TẠO CHỦ ĐỀ (STAGE 1)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GenerateTopicsPayload(BaseModel):
    language: Optional[str] = "vi"

@app.post("/api/projects/generate-topics")
def api_generate_topics(payload: GenerateTopicsPayload):
    """Stage 1: Tạo 5 gợi ý chủ đề từ Gemini."""
    if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE" or not config.GEMINI_API_KEY.strip():
        raise HTTPException(status_code=400, detail="Chưa cấu hình GEMINI_API_KEY! Vui lòng mở tab Cấu hình hệ thống để thiết lập.")

    try:
        # Import cục bộ để tránh lỗi khởi động nếu API Key chưa đúng
        from modules.script_generator import generate_topics
        topics = generate_topics(language=payload.language)
        return {"status": "success", "topics": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi gọi API Gemini tạo chủ đề: {str(e)}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API QUẢN LÝ DỰ ÁN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CreateProjectPayload(BaseModel):
    topic_title: str
    project_name: Optional[str] = None
    active_profile: Optional[str] = None
    language: Optional[str] = "vi"

def sanitize_dirname(title: str) -> str:
    """Tạo tên thư mục an toàn từ tiêu đề."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '_', slug)
    slug = slug.strip('_')
    return slug[:80] if slug else "untitled_project"

@app.get("/api/projects")
def list_projects():
    """Liệt kê các dự án hiện có và thông tin tóm tắt."""
    output_dir = config.BASE_OUTPUT_DIR
    if not os.path.exists(output_dir):
        return []

    projects = []
    for entry in os.listdir(output_dir):
        project_dir = os.path.join(output_dir, entry)
        if os.path.isdir(project_dir):
            info_path = os.path.join(project_dir, "project_info.json")
            info = {}
            if os.path.exists(info_path):
                try:
                    with open(info_path, "r", encoding="utf-8") as f:
                        info = json.load(f)
                except Exception:
                    pass
            
            # Tính toán dung lượng thư mục (KB/MB)
            total_size = 0
            for root, dirs, files in os.walk(project_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    total_size += os.path.getsize(fp)
            size_mb = total_size / (1024 * 1024)

            # Lấy ngày cập nhật cuối cùng (mtime của project_info.json hoặc chính thư mục)
            last_mod = os.path.getmtime(info_path if os.path.exists(info_path) else project_dir)

            projects.append({
                "project_name": entry,
                "topic_title": info.get("topic_title", entry.replace("_", " ").title()),
                "current_stage": info.get("current_stage", 1),
                "folder_size_mb": round(size_mb, 2),
                "last_updated": last_mod,
                "is_running": entry in active_processes
            })

    # Sắp xếp theo ngày cập nhật mới nhất
    projects.sort(key=lambda x: x["last_updated"], reverse=True)
    return projects

@app.post("/api/projects/create")
def create_project(payload: CreateProjectPayload):
    """Khởi tạo một dự án mới."""
    topic_title = payload.topic_title.strip()
    if not topic_title:
        raise HTTPException(status_code=400, detail="Chủ đề không được để trống")

    name = payload.project_name
    if not name or not name.strip():
        name = sanitize_dirname(topic_title)
    else:
        name = sanitize_dirname(name)

    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "images"), exist_ok=True)

    # Khởi tạo thông tin dự án
    project_info = {
        "topic_title": topic_title,
        "project_name": name,
        "project_dir": project_dir,
        "current_stage": 1,
        "tts_engine": config.TTS_ENGINE,
        "image_mode": config.IMAGE_MODE,
        "active_profile": payload.active_profile or active_profile_id,
        "language": payload.language or "vi"
    }
    
    info_path = os.path.join(project_dir, "project_info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(project_info, f, ensure_ascii=False, indent=2)

    # Tạo một file log rỗng
    log_path = os.path.join(project_dir, "pipeline.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Dự án '{topic_title}' đã được tạo.\n")

    return {"status": "success", "project_name": name, "project_dir": project_dir}

@app.get("/api/projects/{name}")
def get_project_details(name: str):
    """Lấy toàn bộ thông tin chi tiết và tài nguyên của một dự án."""
    global active_project_name
    active_project_name = name
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    # 1. Đọc project_info.json
    info_path = os.path.join(project_dir, "project_info.json")
    info = {}
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
        except Exception:
            pass

    # Nạp nóng profile của dự án này vào config
    project_profile = info.get("active_profile", "ancient_history")
    config.load_channel_profile(project_profile)

    # Đọc chi tiết của profile đang dùng
    profile_data = {}
    profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
    profile_path = os.path.join(profiles_dir, f"{project_profile}.json")
    if os.path.exists(profile_path):
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
        except Exception:
            pass

    # 2. Đọc kịch bản script.txt
    script_text = ""
    script_path = os.path.join(project_dir, "script.txt")
    if os.path.exists(script_path):
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                script_text = f.read()
        except Exception:
            pass

    # 3. Đọc timestamps timing.json
    timing = []
    timing_path = os.path.join(project_dir, "timing.json")
    if os.path.exists(timing_path):
        try:
            with open(timing_path, "r", encoding="utf-8") as f:
                timing = json.load(f)
        except Exception:
            pass

    # 4. Đọc prompts prompts.json
    prompts = []
    prompts_path = os.path.join(project_dir, "prompts.json")
    if os.path.exists(prompts_path):
        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                prompts = json.load(f)
        except Exception:
            pass

    # 5. Đếm hình ảnh trong thư mục images/ và nhóm theo phiên bản
    images_dir = os.path.join(project_dir, "images")
    existing_images = []
    image_map = {}
    
    # Khởi tạo map cho tất cả prompts
    for idx in range(len(prompts)):
        image_map[str(idx)] = {
            "active": None,
            "versions": []
        }

    if os.path.exists(images_dir):
        existing_images = [f for f in os.listdir(images_dir) if f.lower().endswith(".png")]
        
        # Phân loại ảnh chính và ảnh phiên bản
        for f in existing_images:
            # Check version file, e.g., "5_v0.png"
            version_match = re.match(r"^(\d+)_v(\d+)\.png$", f, re.IGNORECASE)
            if version_match:
                idx_str = version_match.group(1)
                if idx_str in image_map:
                    image_map[idx_str]["versions"].append(f)
            else:
                # Check active file, e.g., "5.png"
                active_match = re.match(r"^(\d+)\.png$", f, re.IGNORECASE)
                if active_match:
                    idx_str = active_match.group(1)
                    if idx_str in image_map:
                        image_map[idx_str]["active"] = f
                        
        # Đảm bảo danh sách versions được sắp xếp theo số phiên bản v0, v1, v2...
        for idx_str in image_map:
            image_map[idx_str]["versions"].sort(key=lambda x: int(re.search(r"_v(\d+)\.png$", x, re.IGNORECASE).group(1)))
            # Hỗ trợ tương thích ngược: nếu có ảnh chính {idx}.png nhưng chưa có bản version nào (như các dự án cũ)
            # thì coi như ảnh đó có phiên bản là chính nó
            if image_map[idx_str]["active"] and not image_map[idx_str]["versions"]:
                image_map[idx_str]["versions"] = [image_map[idx_str]["active"]]

    # Tự động tăng stage từ 5 lên 6 nếu đã hoàn tất ảnh
    if _check_and_promote_stage_5(project_dir, info):
        info_path = os.path.join(project_dir, "project_info.json")
        try:
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # 6. Kiểm tra file voice.mp3 và video thành phẩm
    voice_exists = os.path.exists(os.path.join(project_dir, "voice.mp3"))
    
    video_filename = None
    if os.path.exists(os.path.join(project_dir, f"{name}.mp4")):
        video_filename = f"{name}.mp4"
    elif os.path.exists(os.path.join(project_dir, "final_video.mp4")):
        video_filename = "final_video.mp4"

    return {
        "info": info,
        "channel_profile": profile_data,
        "script_text": script_text,
        "voice_exists": voice_exists,
        "video_exists": video_filename is not None,
        "video_filename": video_filename or f"{name}.mp4",
        "timing": timing,
        "prompts": prompts,
        "images_count": len(existing_images),
        "existing_images": existing_images,
        "image_map": image_map,
        "is_running": name in active_processes
    }

@app.get("/api/active-project")
def get_active_project():
    """Lấy thông tin của dự án đang active hiện tại (được mở gần nhất trên Dashboard)."""
    global active_project_name
    if not active_project_name:
        # Nếu chưa mở dự án nào, lấy dự án mới nhất
        projects = list_projects()
        if projects:
            active_project_name = projects[0]["project_name"]
        else:
            raise HTTPException(status_code=404, detail="Không tìm thấy dự án active nào")
    return get_project_details(active_project_name)

@app.delete("/api/projects/{name}")
def delete_project(name: str):
    """Xóa hoàn toàn một dự án và các tệp tin của nó."""
    # Kiểm tra xem dự án đang chạy không
    if name in active_processes:
        raise HTTPException(status_code=400, detail="Không thể xóa dự án khi đang chạy tiến trình pipeline")

    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    try:
        shutil.rmtree(project_dir)
        return {"status": "success", "message": f"Đã xóa hoàn toàn dự án '{name}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể xóa thư mục dự án: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API LƯU/CHỈNH SỬA TÀI NGUYÊN DỰ ÁN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ScriptSavePayload(BaseModel):
    script_text: str

@app.post("/api/projects/{name}/save-script")
def save_script(name: str, payload: ScriptSavePayload):
    """Lưu chỉnh sửa kịch bản thủ công."""
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    script_path = os.path.join(project_dir, "script.txt")
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(payload.script_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể ghi file script.txt: {e}")

    # Cập nhật stage lên 2 nếu đang ở stage nhỏ hơn
    info_path = os.path.join(project_dir, "project_info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            if info.get("current_stage", 1) < 2:
                info["current_stage"] = 2
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return {"status": "success", "message": "Đã lưu kịch bản thành công!"}

@app.post("/api/projects/{name}/save-prompts")
def save_prompts(name: str, prompts: list[dict]):
    """Lưu chỉnh sửa prompts tạo ảnh thủ công."""
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    prompts_path = os.path.join(project_dir, "prompts.json")
    try:
        # Lưu JSON prompts
        with open(prompts_path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, ensure_ascii=False, indent=2)

        # Đồng bộ ra prompts.txt và các file text xuất cho ImageFX
        prompts_txt = []
        imagefx_prompts = []
        imagefx_prompts_numbered = []

        for p in prompts:
            p_text = p.get("prompt", "").strip()
            idx = p.get("index", 0)
            prompts_txt.append(p_text)
            imagefx_prompts.append(p_text)
            imagefx_prompts_numbered.append(f"[{idx}] {p_text}")

        with open(os.path.join(project_dir, "prompts.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(prompts_txt))
        with open(os.path.join(project_dir, "imagefx_prompts.txt"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(imagefx_prompts))
        with open(os.path.join(project_dir, "imagefx_prompts_numbered.txt"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(imagefx_prompts_numbered))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu các tệp tin prompts: {e}")

    return {"status": "success", "message": "Đã lưu danh sách prompts mới!"}

@app.post("/api/projects/{name}/upload-image")
async def upload_image(name: str, index: int = Query(...), version: Optional[int] = Query(None), file: UploadFile = File(...)):
    """Kéo thả và upload ảnh tương ứng với số thứ tự index (Ví dụ: 0.png, 1.png...)."""
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    images_dir = os.path.join(project_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # Đọc project_info.json để cập nhật active_image_versions
    info_path = os.path.join(project_dir, "project_info.json")
    info = {}
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
        except Exception:
            pass

    try:
        content = await file.read()
        
        # Giải phóng khóa (lock) sinh ảnh nếu có
        global image_generation_locks
        lock_key = f"{name}:{index}"
        if "image_generation_locks" in globals() and lock_key in image_generation_locks:
            try:
                del image_generation_locks[lock_key]
            except Exception:
                pass
        
        # Nếu có truyền tham số version
        if version is not None:
            v_filename = f"{index}_v{version}.png"
            v_path = os.path.join(images_dir, v_filename)
            with open(v_path, "wb") as f:
                f.write(content)
                
            # Nếu là version 0 hoặc file chính chưa tồn tại, copy bản này thành file chính
            active_filename = f"{index}.png"
            active_path = os.path.join(images_dir, active_filename)
            if version == 0 or not os.path.exists(active_path):
                shutil.copy2(v_path, active_path)
                
                # Cập nhật project_info
                info["active_image_versions"] = info.get("active_image_versions", {})
                info["active_image_versions"][str(index)] = version
                _check_and_promote_stage_5(project_dir, info)
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                    
            return {"status": "success", "filename": v_filename, "message": f"Đã tải lên {v_filename} thành công!"}
            
        else:
            # Nếu không truyền version (từ kéo thả thủ công)
            # Tự động gán version tiếp theo bằng cách đếm số lượng version hiện có
            existing_v_files = glob.glob(os.path.join(images_dir, f"{index}_v*.png"))
            next_v = len(existing_v_files)
            
            v_filename = f"{index}_v{next_v}.png"
            v_path = os.path.join(images_dir, v_filename)
            with open(v_path, "wb") as f:
                f.write(content)
                
            # Ghi đè trực tiếp lên file chính
            active_filename = f"{index}.png"
            active_path = os.path.join(images_dir, active_filename)
            with open(active_path, "wb") as f:
                f.seek(0)
                f.write(content)
                
            # Cập nhật project_info
            info["active_image_versions"] = info.get("active_image_versions", {})
            info["active_image_versions"][str(index)] = next_v
            _check_and_promote_stage_5(project_dir, info)
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
                
            return {"status": "success", "filename": active_filename, "message": f"Đã tải lên {active_filename} và lưu thành bản v{next_v}!"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể lưu file ảnh: {e}")


class SetActiveImagePayload(BaseModel):
    index: int
    version: int

@app.post("/api/projects/{name}/set-active-image")
def set_active_image(name: str, payload: SetActiveImagePayload):
    """Thiết lập ảnh phiên bản được chọn làm ảnh hoạt động chính."""
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    images_dir = os.path.join(project_dir, "images")
    v_filename = f"{payload.index}_v{payload.version}.png"
    v_path = os.path.join(images_dir, v_filename)
    active_path = os.path.join(images_dir, f"{payload.index}.png")

    if not os.path.exists(v_path):
        raise HTTPException(status_code=404, detail=f"Ảnh phiên bản v{payload.version} không tồn tại")

    try:
        shutil.copy2(v_path, active_path)
        
        # Cập nhật project_info.json
        info_path = os.path.join(project_dir, "project_info.json")
        info = {}
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
            except Exception:
                pass
                
        info["active_image_versions"] = info.get("active_image_versions", {})
        info["active_image_versions"][str(payload.index)] = payload.version
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể chuyển đổi ảnh hoạt động chính: {e}")

    return {"status": "success", "message": f"Đã thiết lập v{payload.version} làm ảnh hoạt động chính!"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API PREVIEW TÀI NGUYÊN (MEDIA/IMAGES)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/projects/{name}/file")
def get_project_file(name: str, path: str = Query(...)):
    """API an toàn để trả về tệp tin tài nguyên (ảnh, audio, video)."""
    project_dir = os.path.abspath(os.path.join(config.BASE_OUTPUT_DIR, name))
    requested_path = os.path.abspath(os.path.join(project_dir, path))

    # Bảo mật: Ngăn chặn directory traversal
    if not requested_path.startswith(project_dir):
        raise HTTPException(status_code=403, detail="Tru cập bị từ chối")

    if not os.path.exists(requested_path):
        raise HTTPException(status_code=404, detail="File không tồn tại")

    return FileResponse(requested_path)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API CHẠY PIPELINE (STAGE RUNNER)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RunStagePayload(BaseModel):
    stage: int

@app.post("/api/projects/{name}/run-stage")
def run_stage(name: str, payload: RunStagePayload, background_tasks: BackgroundTasks):
    """Chạy một giai đoạn cụ thể của dự án dưới background subprocess."""
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    # Kiểm tra xem dự án này có đang chạy stage nào khác không
    if name in active_processes:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Dự án này đã có một tiến trình pipeline đang chạy!"}
        )

    stage = payload.stage
    if stage not in [2, 3, 4, 5, 6]:
        raise HTTPException(status_code=400, detail="Stage không hợp lệ (Chỉ hỗ trợ chạy Stage 2 đến Stage 6 từ giao diện)")

    # Kiểm tra tính sẵn sàng của API Keys trước khi chạy các stage gọi API
    if stage in [2, 4, 5] and config.IMAGE_MODE == "api":
        if config.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE" or not config.GEMINI_API_KEY.strip():
            raise HTTPException(status_code=400, detail="Chưa cấu hình GEMINI_API_KEY! Hãy nhập API Key trong tab Cấu hình.")
    
    if stage == 3 and config.TTS_ENGINE == "elevenlabs":
        if not config.ELEVENLABS_API_KEY.strip():
            raise HTTPException(status_code=400, detail="Chưa cấu hình ELEVENLABS_API_KEY cho engine ElevenLabs! Vui lòng bổ sung khóa API.")

    # Chuẩn bị file log (ghi đè log cũ bằng log mới của stage vừa chạy)
    log_path = os.path.join(project_dir, "pipeline.log")
    try:
        log_file = open(log_path, "w", encoding="utf-8")
        log_file.write(f"=== BẮT ĐẦU CHẠY GIAI ĐOẠN {stage} ===\n")
        log_file.flush()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể khởi tạo file log: {e}")

    cmd = [
        sys.executable,
        "-u",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_pipeline.py"),
        "--stage", str(stage),
        "--project", name,
        "--force",
        "--single-stage"
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,  # Chuyển stderr vào chung file log
            text=True,
            encoding="utf-8",
            bufsize=1,  # Ghi đệm dòng để frontend cập nhật tức thì
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        active_processes[name] = (process, log_file)
        
        # Thêm task theo dõi tiến trình
        background_tasks.add_task(monitor_process, name, process, log_file)

        return {
            "status": "success",
            "message": f"Đã kích hoạt Giai đoạn {stage} thành công!",
            "is_running": True
        }
    except Exception as e:
        log_file.close()
        raise HTTPException(status_code=500, detail=f"Không thể khởi chạy tiến trình: {e}")

@app.post("/api/projects/{name}/stop-stage")
def stop_stage(name: str):
    """Dừng tiến trình đang chạy của dự án."""
    if name not in active_processes:
        return {"status": "success", "message": "Không có tiến trình nào đang chạy cho dự án này"}
        
    try:
        process, log_file = active_processes[name]
        
        # Kill process tree on Windows/Linux
        try:
            import psutil
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except Exception:
            process.kill()
            
        try:
            log_file.close()
        except Exception:
            pass
            
        if name in active_processes:
            del active_processes[name]
            
        # Ghi log dừng vào file log để frontend hiển thị và đóng stream
        log_path = os.path.join(config.BASE_OUTPUT_DIR, name, "pipeline.log")
        if os.path.exists(log_path):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n\n=== PIPELINE BỊ DỪNG BỞI NGƯỜI DÙNG ===\n=== HOÀN TẤT ===\n")
            except Exception:
                pass
            
        return {"status": "success", "message": "Đã dừng tiến trình thành công!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi dừng tiến trình: {e}")

@app.post("/api/projects/{name}/delete-image/{index}")
def delete_project_image(name: str, index: int):
    """Xóa ảnh cũ tương ứng với số thứ tự index để cho phép sinh lại."""
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")
    
    images_dir = os.path.join(project_dir, "images")
    if os.path.exists(images_dir):
        files = glob.glob(os.path.join(images_dir, f"{index}.png")) + glob.glob(os.path.join(images_dir, f"{index}_v*.png"))
        for f in files:
            try:
                os.remove(f)
            except Exception:
                pass
    
    # Cập nhật project_info.json để bỏ đánh dấu hoàn thành
    info_path = os.path.join(project_dir, "project_info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            if "active_image_versions" in info and str(index) in info["active_image_versions"]:
                del info["active_image_versions"][str(index)]
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
    return {"status": "success", "message": f"Đã xóa ảnh #{index} thành công!"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SERVER-SENT EVENTS (SSE) STREAMING LOGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/projects/{name}/logs")
async def stream_logs(name: str):
    """SSE endpoint để truyền trực tiếp nội dung file log về frontend theo thời gian thực."""
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    log_path = os.path.join(project_dir, "pipeline.log")

    async def log_generator():
        # Đợi file log xuất hiện
        for _ in range(10):
            if os.path.exists(log_path):
                break
            await asyncio.sleep(0.5)

        if not os.path.exists(log_path):
            yield "data: {\"log\": \"Chưa tìm thấy file log cho dự án này.\"}\n\n"
            return

        # Đọc toàn bộ nội dung hiện tại trước
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.read()
            yield f"data: {json.dumps({'log': lines, 'is_running': name in active_processes})}\n\n"
            
            # Tiếp tục theo dõi dòng mới
            while True:
                line = f.readline()
                if not line:
                    # Kiểm tra xem tiến trình đã kết thúc chưa
                    if name not in active_processes:
                        # Đọc nốt dòng cuối cùng có thể ghi đè lúc hoàn tất
                        extra = f.read()
                        if extra:
                            yield f"data: {json.dumps({'log': extra, 'is_running': False})}\n\n"
                        done_msg = json.dumps({'log': '\n=== HOÀN TẤT ===\n', 'is_running': False})
                        yield f"data: {done_msg}\n\n"
                        break
                    await asyncio.sleep(0.5)
                    continue
                
                yield f"data: {json.dumps({'log': line, 'is_running': True})}\n\n"

    return StreamingResponse(log_generator(), media_type="text/event-stream")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEB GEMINI AUTOMATION ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WebGeminiTask:
    def __init__(self, task_id: str, task_type: str, prompt: str):
        self.task_id = task_id
        self.task_type = task_type
        self.prompt = prompt
        self.status = "pending"  # "pending", "running", "completed", "failed"
        self.result = None
        self.error = None

# Biến toàn cục để lưu trữ active web task
active_web_task: Optional[WebGeminiTask] = None

# Khóa sinh ảnh dùng cho ImageFX Automator chạy song song
image_generation_locks = {}  # key: f"{project_name}:{prompt_index}", value: timestamp (float) khi hết hạn khóa

class AddTaskPayload(BaseModel):
    task_type: str
    prompt: str

class CompleteTaskPayload(BaseModel):
    task_id: str
    result: Optional[str] = None
    error: Optional[str] = None

@app.post("/api/web-gemini/add-task")
def add_web_task(payload: AddTaskPayload):
    global active_web_task
    import time
    task_id = str(int(time.time() * 1000))
    active_web_task = WebGeminiTask(
        task_id=task_id,
        task_type=payload.task_type,
        prompt=payload.prompt
    )
    return {"status": "success", "task_id": task_id}

@app.get("/api/web-gemini/pending")
def get_pending_web_task():
    global active_web_task
    if active_web_task and active_web_task.status == "pending":
        active_web_task.status = "running"
        return {
            "task_id": active_web_task.task_id,
            "task_type": active_web_task.task_type,
            "prompt": active_web_task.prompt
        }
    return Response(status_code=204)

@app.post("/api/web-gemini/complete")
def complete_web_task(payload: CompleteTaskPayload):
    global active_web_task
    if not active_web_task or active_web_task.task_id != payload.task_id:
        raise HTTPException(status_code=404, detail="Task không tồn tại hoặc đã hết hạn")
    
    if payload.error:
        active_web_task.status = "failed"
        active_web_task.error = payload.error
    else:
        active_web_task.status = "completed"
        active_web_task.result = payload.result
        
    return {"status": "success"}

@app.get("/api/web-gemini/status/{task_id}")
def get_web_task_status(task_id: str):
    global active_web_task
    if not active_web_task or active_web_task.task_id != task_id:
        raise HTTPException(status_code=404, detail="Task không tìm thấy")
    
    return {
        "task_id": active_web_task.task_id,
        "status": active_web_task.status,
        "result": active_web_task.result,
        "error": active_web_task.error
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESILIENT IMAGE GENERATION & CONFIG ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _check_and_promote_stage_5(project_dir: str, info: dict):
    """Kiểm tra xem tất cả ảnh đã có đủ chưa, nếu đủ thì chuyển stage từ 5 lên 6."""
    prompts_path = os.path.join(project_dir, "prompts.json")
    images_dir = os.path.join(project_dir, "images")
    if os.path.exists(prompts_path):
        try:
            with open(prompts_path, "r", encoding="utf-8") as f:
                prompts_data = json.load(f)
            total_prompts = len(prompts_data)
            if total_prompts > 0:
                all_ready = True
                for i in range(total_prompts):
                    img_path = os.path.join(images_dir, f"{i}.png")
                    if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
                        all_ready = False
                        break
                if all_ready and info.get("current_stage", 1) == 5:
                    info["current_stage"] = 6
                    return True
        except Exception:
            pass
    return False

def update_and_sync_prompts(project_dir: str, index: int, new_prompt_text: str):
    prompts_path = os.path.join(project_dir, "prompts.json")
    if not os.path.exists(prompts_path):
        return False
        
    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts_data = json.load(f)
            
        updated = False
        for idx, p in enumerate(prompts_data):
            if isinstance(p, dict):
                if p.get("index") == index:
                    p["prompt"] = new_prompt_text
                    updated = True
            elif isinstance(p, str) and idx == index:
                prompts_data[idx] = new_prompt_text
                updated = True
                
        if not updated:
            return False
            
        # Save back to prompts.json
        with open(prompts_path, "w", encoding="utf-8") as f:
            json.dump(prompts_data, f, ensure_ascii=False, indent=2)
            
        # Sync other files
        prompts_txt = []
        imagefx_prompts = []
        imagefx_prompts_numbered = []
        
        for idx, p in enumerate(prompts_data):
            if isinstance(p, str):
                p_text = p.strip()
                p_idx = idx
            else:
                p_text = p.get("prompt", "").strip()
                p_idx = p.get("index", idx)
                
            prompts_txt.append(p_text)
            imagefx_prompts.append(p_text)
            imagefx_prompts_numbered.append(f"[{p_idx}] {p_text}")
            
        with open(os.path.join(project_dir, "prompts.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(prompts_txt))
        with open(os.path.join(project_dir, "imagefx_prompts.txt"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(imagefx_prompts))
        with open(os.path.join(project_dir, "imagefx_prompts_numbered.txt"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(imagefx_prompts_numbered))
            
        return True
    except Exception as e:
        print(f"Lỗi khi cập nhật và đồng bộ prompts: {e}")
        return False

@app.get("/api/projects/{name}/next-pending-prompt")
def get_next_pending_prompt(name: str):
    import time
    global image_generation_locks

    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    prompts_path = os.path.join(project_dir, "prompts.json")
    if not os.path.exists(prompts_path):
        return {"status": "empty", "message": "Không tìm thấy prompts.json"}

    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            prompts_data = json.load(f)
    except Exception as e:
        return {"status": "empty", "message": f"Lỗi đọc prompts.json: {e}"}

    images_dir = os.path.join(project_dir, "images")

    now = time.time()
    for idx, p in enumerate(prompts_data):
        if isinstance(p, str):
            prompt_text = p
            prompt_index = idx
        elif isinstance(p, dict):
            prompt_text = p.get("prompt", "")
            prompt_index = p.get("index", idx)
        else:
            continue

        # 1. Kiểm tra xem ảnh {prompt_index}.png đã tồn tại và có kích thước lớn hơn 0 chưa
        img_path = os.path.join(images_dir, f"{prompt_index}.png")
        if os.path.exists(img_path) and os.path.getsize(img_path) > 0:
            continue

        # 2. Kiểm tra xem prompt này có đang bị khóa bởi tab khác không
        lock_key = f"{name}:{prompt_index}"
        lock_expire = image_generation_locks.get(lock_key, 0)
        if lock_expire > now:
            # Vẫn đang bị khóa, bỏ qua
            continue

        # 3. Khóa prompt này lại trong 90 giây
        image_generation_locks[lock_key] = now + 90
        return {
            "status": "success",
            "index": prompt_index,
            "prompt": prompt_text
        }

    return {"status": "empty", "message": "Tất cả ảnh đã được sinh xong hoặc đang được xử lý"}

class RewritePromptPayload(BaseModel):
    index: int
    prompt: str

@app.post("/api/projects/{name}/rewrite-prompt")
def rewrite_prompt_api(name: str, payload: RewritePromptPayload):
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    import google.generativeai as genai
    try:
        # Gọi Gemini để viết lại prompt tránh lỗi kiểm duyệt
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            config.GEMINI_PROMPT_MODEL,
            system_instruction=(
                "You are an expert AI image prompt engineer. Your task is to rewrite the input image prompt "
                "to bypass safety filters (such as Google ImageFX or DALL-E policy blocks) while keeping "
                "the exact same visual meaning, style, and structure. Avoid sensitive words, violence, "
                "weapons, blood, nudity, copyright names, or policy-triggering keywords. Rephrase them "
                "using safe, descriptive, artistic synonyms. "
                "Return ONLY the rewritten prompt. Do NOT include any explanations, introduction, markdown blocks, or quotes."
            )
        )
        response = model.generate_content(payload.prompt)
        new_prompt = response.text.strip()
        
        # Nếu mô hình trả về chuỗi trống hoặc lỗi, quăng exception
        if not new_prompt:
            raise ValueError("Mô hình không trả về kết quả")
            
        # Cập nhật và đồng bộ vào file dự án
        success = update_and_sync_prompts(project_dir, payload.index, new_prompt)
        if not success:
            raise ValueError("Không thể đồng bộ prompt mới vào tệp tin dự án")
            
        return {
            "status": "success",
            "index": payload.index,
            "original_prompt": payload.prompt,
            "rewritten_prompt": new_prompt
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi viết lại prompt bằng Gemini: {e}")

class UpdateImageConfigPayload(BaseModel):
    image_mode: str
    active_profile: str

@app.post("/api/projects/{name}/update-image-config")
def update_image_config(name: str, payload: UpdateImageConfigPayload):
    project_dir = os.path.join(config.BASE_OUTPUT_DIR, name)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Dự án không tồn tại")

    info_path = os.path.join(project_dir, "project_info.json")
    if not os.path.exists(info_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy project_info.json")

    try:
        with open(info_path, "r", encoding="utf-8") as f:
            info = json.load(f)

        # Cập nhật config cục bộ cho dự án
        info["image_mode"] = payload.image_mode
        info["active_profile"] = payload.active_profile

        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        # Đồng bộ biến môi trường / config toàn cục của python (để pipeline chạy đúng)
        config.IMAGE_MODE = payload.image_mode
        config.ACTIVE_PROFILE_ID = payload.active_profile
        # Tải lại profile để config áp dụng ngay lập tức
        config.load_channel_profile(payload.active_profile)

        return {
            "status": "success",
            "message": "Cấu hình ảnh đã được cập nhật thành công!",
            "image_mode": payload.image_mode,
            "active_profile": payload.active_profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể lưu cấu hình ảnh: {e}")


class OpenChromePayload(BaseModel):
    profile_folder: str

class CreateChromeProfilePayload(BaseModel):
    name: str

@app.get("/api/chrome-profiles")
def get_chrome_profiles_api():
    """Lấy danh sách các profile Chrome riêng của dự án trong thư mục chrome_profiles."""
    profiles_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profiles"))
    os.makedirs(profiles_dir, exist_ok=True)
    
    profiles = []
    try:
        for entry in os.scandir(profiles_dir):
            if entry.is_dir() and not entry.name.startswith("."):
                profiles.append({
                    "folder": entry.name,
                    "name": entry.name.replace("_", " "),
                })
    except Exception as e:
        print(f"Lỗi quét thư mục chrome_profiles: {e}")
        
    profiles.sort(key=lambda x: x["folder"].lower())
    return {"status": "success", "profiles": profiles}

@app.post("/api/chrome-profiles/create")
def create_chrome_profile_api(payload: CreateChromeProfilePayload):
    """Tạo một profile Chrome mới trong thư mục chrome_profiles."""
    # Loại bỏ ký tự đặc biệt khỏi tên thư mục
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", payload.name)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Tên profile không hợp lệ!")
        
    profiles_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profiles"))
    profile_path = os.path.join(profiles_dir, safe_name)
    
    if os.path.exists(profile_path):
        raise HTTPException(status_code=400, detail="Profile này đã tồn tại!")
        
    try:
        os.makedirs(profile_path, exist_ok=True)
        return {"status": "success", "message": f"Đã tạo profile '{payload.name}' thành công!", "folder": safe_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể tạo thư mục profile: {e}")

@app.post("/api/open-chrome")
def open_chrome_api(payload: OpenChromePayload):
    """Mở trình duyệt Google Chrome với profile riêng tại trang ImageFX."""
    url = "https://aitestkitchen.withgoogle.com/tools/image-fx"
    
    profiles_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profiles"))
    profile_path = os.path.join(profiles_dir, payload.profile_folder)
    
    if not os.path.exists(profile_path):
        raise HTTPException(status_code=404, detail="Profile không tồn tại!")
        
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        "chrome.exe"
    ]
    
    chrome_bin = None
    for path in chrome_paths:
        if path == "chrome.exe" or os.path.exists(path):
            chrome_bin = path
            break
            
    if not chrome_bin:
        raise HTTPException(status_code=500, detail="Không tìm thấy trình duyệt Google Chrome được cài đặt trên hệ thống!")
        
    try:
        extension_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "extensions", "imagefx_automator"))
        
        cmd = [
            chrome_bin, 
            f"--user-data-dir={profile_path}", 
            f"--load-extension={extension_path}",
            url
        ]
        
        # Chạy subprocess độc lập
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.DETACHED_PROCESS
            
        subprocess.Popen(cmd, creationflags=creation_flags)
        return {"status": "success", "message": f"Đã mở Chrome (Profile: {payload.profile_folder})"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khởi chạy Chrome: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHỤC VỤ TRANG GIAO DIỆN TĨNH (STATIC FILES)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Phục vụ trang index.html ở root "/"
@app.get("/")
def get_index():
    static_index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content="<h1>Không tìm thấy thư mục static hoặc file index.html!</h1>", status_code=404)

# Gắn thư mục static phục vụ file CSS, JS
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Đóng tất cả các file log và tiến trình khi server tắt
@app.on_event("shutdown")
def shutdown_event():
    print("Cleaning up background processes...")
    for name, (proc, log_file) in list(active_processes.items()):
        try:
            proc.terminate()
            log_file.close()
            print(f"Terminated process for project '{name}'")
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    # Khởi chạy server local
    print("Starting Web Dashboard Server at http://127.0.0.1:8085 ...")
    uvicorn.run("dashboard:app", host="127.0.0.1", port=8085, reload=True)
