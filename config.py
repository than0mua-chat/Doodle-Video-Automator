"""
=============================================================
  CONFIG.PY — Cấu hình trung tâm cho Pipeline Video Automation
=============================================================
Chỉnh sửa các giá trị bên dưới hoặc điều chỉnh qua Web Dashboard
"""

import os
import json

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TẢI CẤU HÌNH ĐỘNG TỪ SETTINGS.JSON
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
_user_settings = {}
if os.path.exists(_settings_path):
    try:
        with open(_settings_path, "r", encoding="utf-8") as _f:
            _user_settings = json.load(_f)
    except Exception:
        pass

def _get_setting(key, default_val):
    # Trả về giá trị từ settings.json -> Biến môi trường -> Giá trị mặc định
    return _user_settings.get(key, os.environ.get(key, default_val))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API KEYS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GEMINI_API_KEY = _get_setting("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
ELEVENLABS_API_KEY = _get_setting("ELEVENLABS_API_KEY", "")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LỰA CHỌN CÔNG CỤ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TTS Engine: "edge-tts" (miễn phí) hoặc "elevenlabs" (trả phí, chất lượng cao)
TTS_ENGINE = _get_setting("TTS_ENGINE", "edge-tts")

# Edge-TTS voice (xem danh sách: edge-tts --list-voices)
EDGE_TTS_VOICE = _get_setting("EDGE_TTS_VOICE", "en-US-AndrewNeural")

# ElevenLabs voice ID (lấy từ ElevenLabs dashboard)
ELEVENLABS_VOICE_ID = _get_setting("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
ELEVENLABS_MODEL_ID = _get_setting("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

# Image Generation: "api" (dùng Gemini Imagen API) hoặc "export" (xuất file prompt cho ImageFX)
IMAGE_MODE = _get_setting("IMAGE_MODE", "export")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GEMINI MODEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GEMINI_SCRIPT_MODEL = _get_setting("GEMINI_SCRIPT_MODEL", "gemini-2.5-flash")
GEMINI_PROMPT_MODEL = _get_setting("GEMINI_PROMPT_MODEL", "gemini-2.5-flash")
GEMINI_IMAGE_MODEL = _get_setting("GEMINI_IMAGE_MODEL", "imagen-4-ultra")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VIDEO SETTINGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIDEO_WIDTH = int(_get_setting("VIDEO_WIDTH", 1920))
VIDEO_HEIGHT = int(_get_setting("VIDEO_HEIGHT", 1080))
VIDEO_FPS = int(_get_setting("VIDEO_FPS", 24))
WOBBLE_INTENSITY = int(_get_setting("WOBBLE_INTENSITY", 3))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# THƯ MỤC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BASE_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

ACTIVE_PROFILE_ID = "ancient_history"
TOPIC_STRATEGIST_PERSONA = _get_setting("TOPIC_STRATEGIST_PERSONA", "You are a YouTube content strategist specializing in viral educational videos about ancient humans, human prehistory, evolution, anthropology, and survival.")
SCRIPTWRITER_PERSONA = _get_setting("SCRIPTWRITER_PERSONA", "You are an expert YouTube scriptwriter for a channel about ancient humans and prehistory.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MASTER PROMPT — DNA CỦA KÊNH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHANNEL_KNOWLEDGE_BASE = _get_setting("CHANNEL_KNOWLEDGE_BASE", """
### CONTENT & SCRIPT DNA
- **Niche:** Ancient humans, human prehistory, evolution, anthropology, and survival — how early humans actually lived, hunted, slept, raised children, and handled everyday life. Occasional crossovers into medieval life, weird history, and human psychology.
- **Format:** 7–12 minute educational explainer narrated in calm, intelligent 2nd-person ("you", "your ancestors", "your body", "your brain") — never "we" or "I".
- **Hook formula:** Open by dropping the viewer *inside* an ancestral or everyday sensory moment in 2nd person ("You wake up when your body is ready. No alarm, no schedule.") → immediately pivot with a reframe ("For 99% of human history, this wasn't a hypothetical." / "For roughly 300,000 years...") → contrast it against a striking modern statistic that reframes everything.
- **Script rhythm:** Short sentence. Short sentence. One longer sentence that builds depth. Short sentence. Question?
- **Narrative arc:** Hook → Reframe → Evidence stack (a named study → cross-cultural / skeletal / archaeological confirmation) → Reconstruct a concrete scene the viewer can picture ("So let's reconstruct a day...") → Counterintuitive twist (e.g., "agriculture was a trap") → Modern mirror → Closing line that echoes the very first line, completely reframed.
- **Evidence rule:** Weave at least 3 real named researchers, studies, or archaeological sites naturally into the narration (e.g., Richard Lee's 1963 study, James Suzman, Polly Wiessner, Chauvet Cave, Blombos Cave). Never invent names — only use real ones.
- **No jargon without plain-English explanation** — every scientific or anthropological term gets decoded immediately.
- **Always ends** by reflecting the ancient or scientific truth back onto something the viewer feels or does today.
""")

PROVEN_VIRAL_TOPIC_ANGLES = _get_setting("PROVEN_VIRAL_TOPIC_ANGLES", """
### PROVEN VIRAL TOPIC ANGLES
1. "What / How Did Ancient Humans ___?" — bridges a universal modern concern (jobs, privacy, sleep, raising children, hygiene) to prehistoric life.
2. "How Did Ancient Humans Survive ___?" — survival against a vivid threat (deadliest predators, deadly winters, the Ice Age, starvation).
3. "The CRAZIEST / WEIRDEST ___ Used by Ancient Humans" — a superlative, curiosity-gap reveal of strange real methods.
4. "What ___ Was Like in Ancient / Medieval Times" — an everyday or taboo bodily/social topic (the bathroom, periods, dating, hygiene, unwanted pregnancy) treated honestly.
5. "Why You Wouldn't Last a Day in ___" / "POV: Your Life as ___" — an immersive 2nd-person scenario that puts the viewer in the past.
6. "What If ___?" — a provocative existential or counterfactual question grounded in real data (e.g., "What If Neanderthals Had Not Gone Extinct?").
""")

VISUAL_STYLE_DNA = _get_setting("VISUAL_STYLE_DNA", """
### VISUAL STYLE DNA
- **Art style:** Hand-drawn 2D doodle cartoon animation — flat solid colors, bold black hand-drawn outlines, slightly wobbly/imperfect lines as if sketched fast with a marker. Childlike and simple. Minimal interior line detail allowed (wood grain, rock cracks) but always flat — ZERO gradients, ZERO drop shadows, ZERO photographic textures.
- **Main character ("you"):** A stick figure with a large round white head, simple black dot eyes, expressive thin eyebrows, a simple line mouth, and thin black stick limbs. The signature recurring character has spiky bright ORANGE hair. Hands are small black blobs/mittens.
- **Character variants:** Bald round white head (no hair) = neutral modern everyman; shaggy/messy brown hair = ancient/prehistoric human; gray hair in a bun + colored dress = elder/grandmother.
- **Animals & objects:** Chunky, simplified cartoon shapes — big, bold, flat single-color fills with thick black outlines.
- **Backgrounds (flat solid color zones — pick by emotional tone):**
  - White or cream = default / neutral / on-screen-text frames.
  - Light blue sky + tan/brown ground + green trees = outdoor daytime / nature / wilderness.
  - Orange sky + tan ground + grass tufts + lone acacia tree = ancient / prehistoric savanna (dawn, dusk, "deep past" tone).
  - Dark navy blue + yellow crescent moon + gray ground = calm night.
  - Deep indigo/purple + scattered star dots + brown ground = deep night / sleeping.
- **On-screen text:** Bold hand-lettered marker font, large, usually centered or upper-center. Default color RED.
- **Color palette (approximate hex):** Orange #F58220 · Sky blue #7FB5D5 · Grass green #4E9A45 · Sand/tan #D2B488 · Night navy #283A6E · Deep indigo #322B5E · Red text #E0302B · Yellow #F4C430 · White #FFFFFF
- **Aspect ratio:** Always 16:9.
""")

IMAGE_PROMPT_STYLE_ANCHOR = _get_setting("IMAGE_PROMPT_STYLE_ANCHOR", "Hand-drawn 2D doodle cartoon animation, flat solid colors, bold black hand-drawn outlines, slightly wobbly imperfect marker lines,")

IMAGE_PROMPT_STYLE_LOCK = _get_setting("IMAGE_PROMPT_STYLE_LOCK", "no gradients, no drop shadows, no photographic textures, no photorealism, no 3D render, no realistic faces, no anime, 16:9 widescreen, simple educational YouTube explainer doodle style.")
PROPOSED_IDEAS = _get_setting("PROPOSED_IDEAS", "### ĐỀ XUẤT 5 KỊCH BẢN & PHÂN TÍCH\n1. Ý tưởng 1...\n")

def load_channel_profile(profile_id: str):
    """
    Nạp cấu hình kênh từ profiles/<profile_id>.json và cập nhật các biến toàn cục của module config.
    """
    global CHANNEL_KNOWLEDGE_BASE, PROVEN_VIRAL_TOPIC_ANGLES, VISUAL_STYLE_DNA
    global IMAGE_PROMPT_STYLE_ANCHOR, IMAGE_PROMPT_STYLE_LOCK, PROPOSED_IDEAS
    global TTS_ENGINE, EDGE_TTS_VOICE, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL_ID
    global TOPIC_STRATEGIST_PERSONA, SCRIPTWRITER_PERSONA
    global ACTIVE_PROFILE_ID
    
    if not profile_id:
        return False
        
    profiles_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
    profile_path = os.path.join(profiles_dir, f"{profile_id}.json")
    
    if not os.path.exists(profile_path):
        print(f"⚠️  Không tìm thấy profile '{profile_id}', giữ nguyên cấu hình hiện tại.")
        return False
        
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
            
        ACTIVE_PROFILE_ID = profile_id
            
        # Ghi đè các thuộc tính cấu hình trong bộ nhớ runtime
        if "CHANNEL_KNOWLEDGE_BASE" in profile_data:
            CHANNEL_KNOWLEDGE_BASE = profile_data["CHANNEL_KNOWLEDGE_BASE"]
        if "PROVEN_VIRAL_TOPIC_ANGLES" in profile_data:
            PROVEN_VIRAL_TOPIC_ANGLES = profile_data["PROVEN_VIRAL_TOPIC_ANGLES"]
        if "VISUAL_STYLE_DNA" in profile_data:
            VISUAL_STYLE_DNA = profile_data["VISUAL_STYLE_DNA"]
        if "IMAGE_PROMPT_STYLE_ANCHOR" in profile_data:
            IMAGE_PROMPT_STYLE_ANCHOR = profile_data["IMAGE_PROMPT_STYLE_ANCHOR"]
        if "IMAGE_PROMPT_STYLE_LOCK" in profile_data:
            IMAGE_PROMPT_STYLE_LOCK = profile_data["IMAGE_PROMPT_STYLE_LOCK"]
        if "PROPOSED_IDEAS" in profile_data:
            PROPOSED_IDEAS = profile_data["PROPOSED_IDEAS"]
        if "TTS_ENGINE" in profile_data:
            TTS_ENGINE = profile_data["TTS_ENGINE"]
        if "EDGE_TTS_VOICE" in profile_data:
            EDGE_TTS_VOICE = profile_data["EDGE_TTS_VOICE"]
        if "ELEVENLABS_VOICE_ID" in profile_data:
            ELEVENLABS_VOICE_ID = profile_data["ELEVENLABS_VOICE_ID"]
        if "ELEVENLABS_MODEL_ID" in profile_data:
            ELEVENLABS_MODEL_ID = profile_data["ELEVENLABS_MODEL_ID"]
        if "TOPIC_STRATEGIST_PERSONA" in profile_data:
            TOPIC_STRATEGIST_PERSONA = profile_data["TOPIC_STRATEGIST_PERSONA"]
        if "SCRIPTWRITER_PERSONA" in profile_data:
            SCRIPTWRITER_PERSONA = profile_data["SCRIPTWRITER_PERSONA"]
            
        print(f"✨ Đã nạp thành công cấu hình kênh: {profile_data.get('profile_name', profile_id)}")
        return True
    except Exception as e:
        print(f"❌ Lỗi khi nạp cấu hình kênh '{profile_id}': {e}")
        return False


