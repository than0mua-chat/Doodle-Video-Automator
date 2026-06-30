"""
=============================================================
  AUDIO_GENERATOR.PY — Text-to-Speech với trích xuất timestamp
=============================================================
Hỗ trợ 2 engine:
  1. Edge-TTS  (miễn phí, async)
  2. ElevenLabs (trả phí, chất lượng cao)

Cả hai đều trả về:
  - Đường dẫn file voice.mp3
  - Danh sách timing theo câu: [{"index", "text", "start", "end"}, ...]
"""

import sys
import os
import re
import json
import asyncio
import logging
from typing import Optional

# ── Thêm thư mục gốc project vào path để import config ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ── Logging ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TIỆN ÍCH CHUNG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _split_into_sentences(text: str) -> list[str]:
    """
    Tách văn bản thành danh sách câu dựa trên dấu câu (. ? !).
    Giữ lại dấu câu ở cuối mỗi câu.
    """
    # Tách theo dấu câu, giữ dấu phân cách
    raw_parts = re.split(r'(?<=[.?!])\s+', text.strip())
    sentences = [s.strip() for s in raw_parts if s.strip()]
    return sentences


def _normalize(text: str) -> str:
    """Chuẩn hóa text để so sánh: lowercase, bỏ dấu câu, gộp khoảng trắng."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _map_words_to_sentences(
    sentences: list[str],
    word_boundaries: list[dict],
) -> list[dict]:
    """
    Ghép danh sách word boundary vào từng câu.
    Trả về timing list: [{"index", "text", "start", "end"}, ...]
    
    Mỗi word boundary cần có keys: "text", "start" (seconds), "end" (seconds).
    """
    timing_list: list[dict] = []
    word_idx = 0
    total_words = len(word_boundaries)

    for sent_i, sentence in enumerate(sentences):
        # Tách từ trong câu gốc (chỉ giữ ký tự chữ/số)
        sent_words = _normalize(sentence).split()
        if not sent_words:
            continue

        # Tìm vị trí bắt đầu của câu trong word_boundaries
        start_word_idx = word_idx
        matched = 0

        while word_idx < total_words and matched < len(sent_words):
            wb_text = _normalize(word_boundaries[word_idx]["text"])
            # So sánh từ hiện tại
            if matched < len(sent_words) and wb_text == sent_words[matched]:
                matched += 1
            elif matched == 0:
                # Chưa match từ nào → thử từ tiếp theo trong boundaries
                start_word_idx = word_idx + 1
            word_idx += 1

        # Xác định start/end time
        if start_word_idx < total_words:
            start_time = word_boundaries[start_word_idx]["start"]
        else:
            # Fallback: dùng end time của câu trước
            start_time = timing_list[-1]["end"] if timing_list else 0.0

        end_word_idx = min(word_idx - 1, total_words - 1)
        if end_word_idx >= 0:
            end_time = word_boundaries[end_word_idx]["end"]
        else:
            end_time = start_time + 1.0  # Fallback

        timing_list.append({
            "index": sent_i,
            "text": sentence,
            "start": round(start_time, 3),
            "end": round(end_time, 3),
        })

    return timing_list


def _save_timing(timing_list: list[dict], project_dir: str) -> str:
    """Lưu timing list ra file JSON."""
    timing_path = os.path.join(project_dir, "timing.json")
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(timing_list, f, ensure_ascii=False, indent=2)
    logger.info(f"Đã lưu timing → {timing_path}")
    return timing_path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENGINE 1: EDGE-TTS (miễn phí, async)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def generate_audio_edge_tts(
    script_text: str,
    project_dir: str,
) -> tuple[str, list[dict]]:
    """
    Tạo audio bằng Edge-TTS (Microsoft) cho từng câu, đo thời lượng và ghép nối nhị phân.
    """
    try:
        import edge_tts
    except ImportError:
        raise ImportError("Cần cài đặt edge-tts: pip install edge-tts")

    # Tạo các thư mục cần thiết
    os.makedirs(project_dir, exist_ok=True)
    voice_dir = os.path.join(project_dir, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    
    audio_path = os.path.join(project_dir, "voice.mp3")
    voice = getattr(config, "EDGE_TTS_VOICE", "vi-VN-HoaiAnNeural")
    
    # 1. Tách kịch bản thành các câu
    sentences = _split_into_sentences(script_text)
    if not sentences:
        raise ValueError("Script trống, không thể tạo âm thanh.")
        
    logger.info(f"Edge-TTS: voice={voice}, text length={len(script_text)} chars, sentences={len(sentences)}")

    # 2. Sinh âm thanh song song cho từng câu với Semaphore để tránh quá tải/rate limit
    sem = asyncio.Semaphore(5) # Cho phép tối đa 5 yêu cầu đồng thời

    async def save_sentence(text: str, idx: int, out_path: str):
        async with sem:
            logger.info(f"Đang sinh câu #{idx}: '{text[:30]}...'")
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(out_path)

    tasks = []
    sentence_files = []
    for idx, sentence in enumerate(sentences):
        file_name = f"{idx}.mp3"
        file_path = os.path.join(voice_dir, file_name)
        sentence_files.append((sentence, idx, file_path))
        tasks.append(save_sentence(sentence, idx, file_path))

    await asyncio.gather(*tasks)

    # 3. Đo thời lượng và lập timing.json
    from moviepy import AudioFileClip
    
    timing_list = []
    current_time = 0.0
    
    for sentence, idx, file_path in sentence_files:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file âm thanh cho câu #{idx}: {file_path}")
            
        # Đo thời lượng thực tế của file âm thanh
        clip = AudioFileClip(file_path)
        duration = round(clip.duration, 3)
        clip.close()
        
        start_time = round(current_time, 3)
        end_time = round(current_time + duration, 3)
        
        timing_list.append({
            "index": idx,
            "text": sentence,
            "start": start_time,
            "end": end_time
        })
        
        current_time = end_time

    # 4. Nối nhị phân toàn bộ các file mp3 đơn lẻ thành voice.mp3 chính
    with open(audio_path, "wb") as outfile:
        for _, _, file_path in sentence_files:
            with open(file_path, "rb") as infile:
                outfile.write(infile.read())
                
    logger.info(f"Đã ghi voice.mp3 chính: {audio_path} ({os.path.getsize(audio_path):,} bytes)")

    # 5. Lưu timing.json
    _save_timing(timing_list, project_dir)

    logger.info(f"Edge-TTS hoàn tất: {len(sentences)} câu.")
    return audio_path, timing_list


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENGINE 2: ELEVENLABS (trả phí, chất lượng cao)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_audio_elevenlabs(
    script_text: str,
    project_dir: str,
) -> tuple[str, list[dict]]:
    """
    Tạo audio bằng ElevenLabs API cho từng câu, đo thời lượng và ghép nối.
    """
    try:
        from elevenlabs import ElevenLabs
    except ImportError:
        raise ImportError("Cần cài đặt elevenlabs: pip install elevenlabs")

    api_key = getattr(config, "ELEVENLABS_API_KEY", "")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY chưa được cấu hình trong config.py")

    # Tạo các thư mục cần thiết
    os.makedirs(project_dir, exist_ok=True)
    voice_dir = os.path.join(project_dir, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    
    audio_path = os.path.join(project_dir, "voice.mp3")
    voice_id = getattr(config, "ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    model_id = getattr(config, "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    # 1. Tách kịch bản thành các câu
    sentences = _split_into_sentences(script_text)
    if not sentences:
        raise ValueError("Script trống, không thể tạo âm thanh.")
        
    logger.info(f"ElevenLabs: voice_id={voice_id}, model_id={model_id}, sentences={len(sentences)}")

    client = ElevenLabs(api_key=api_key)
    sentence_files = []
    
    # 2. Sinh âm thanh tuần tự cho từng câu
    for idx, sentence in enumerate(sentences):
        file_name = f"{idx}.mp3"
        file_path = os.path.join(voice_dir, file_name)
        sentence_files.append((sentence, idx, file_path))
        
        logger.info(f"ElevenLabs: Đang sinh câu #{idx}: '{sentence[:30]}...'")
        
        # Gọi API ElevenLabs để sinh tiếng
        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            model_id=model_id,
            text=sentence
        )
        
        # Ghi âm thanh vào file
        with open(file_path, "wb") as f:
            for chunk in audio_generator:
                f.write(chunk)

    # 3. Đo thời lượng và lập timing.json
    from moviepy import AudioFileClip
    
    timing_list = []
    current_time = 0.0
    
    for sentence, idx, file_path in sentence_files:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file âm thanh cho câu #{idx}: {file_path}")
            
        clip = AudioFileClip(file_path)
        duration = round(clip.duration, 3)
        clip.close()
        
        start_time = round(current_time, 3)
        end_time = round(current_time + duration, 3)
        
        timing_list.append({
            "index": idx,
            "text": sentence,
            "start": start_time,
            "end": end_time
        })
        
        current_time = end_time

    # 4. Nối nhị phân toàn bộ các file mp3 đơn lẻ thành voice.mp3 chính
    with open(audio_path, "wb") as outfile:
        for _, _, file_path in sentence_files:
            with open(file_path, "rb") as infile:
                outfile.write(infile.read())
                
    logger.info(f"Đã ghi voice.mp3 chính: {audio_path} ({os.path.getsize(audio_path):,} bytes)")

    # 5. Lưu timing.json
    _save_timing(timing_list, project_dir)

    logger.info(f"ElevenLabs hoàn tất: {len(sentences)} câu.")
    return audio_path, timing_list


def _build_word_boundaries_from_chars(
    chars: list[str],
    starts: list[float],
    ends: list[float],
) -> list[dict]:
    """
    Ghép character-level timestamps thành word-level boundaries.
    
    ElevenLabs trả về timestamp cho từng ký tự. Ta gộp các ký tự
    liên tiếp (không phải khoảng trắng) thành từ.
    """
    word_boundaries: list[dict] = []
    current_word: list[str] = []
    word_start: Optional[float] = None
    word_end: float = 0.0

    for i, char in enumerate(chars):
        if char.strip() == "":
            # Khoảng trắng → kết thúc từ hiện tại
            if current_word:
                word_boundaries.append({
                    "text": "".join(current_word),
                    "start": word_start if word_start is not None else 0.0,
                    "end": word_end,
                })
                current_word = []
                word_start = None
        else:
            # Ký tự thực → thêm vào từ hiện tại
            if word_start is None:
                word_start = starts[i] if i < len(starts) else 0.0
            word_end = ends[i] if i < len(ends) else word_end
            current_word.append(char)

    # Từ cuối cùng (nếu text không kết thúc bằng khoảng trắng)
    if current_word:
        word_boundaries.append({
            "text": "".join(current_word),
            "start": word_start if word_start is not None else 0.0,
            "end": word_end,
        })

    return word_boundaries


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DISPATCHER — Chọn engine tự động theo config
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_audio(
    script_text: str,
    project_dir: str,
) -> tuple[str, list[dict]]:
    """
    Dispatcher: tạo audio và timing dựa trên config.TTS_ENGINE.
    
    Args:
        script_text: Nội dung script cần đọc.
        project_dir: Thư mục output của project.
    
    Returns:
        (audio_path, timing_list)
    """
    engine = getattr(config, "TTS_ENGINE", "edge-tts").lower().strip()
    logger.info(f"TTS Engine được chọn: {engine}")

    if engine == "edge-tts":
        return asyncio.run(generate_audio_edge_tts(script_text, project_dir))
    elif engine == "elevenlabs":
        return generate_audio_elevenlabs(script_text, project_dir)
    else:
        raise ValueError(
            f"TTS_ENGINE không hợp lệ: '{engine}'. "
            f"Chọn 'edge-tts' hoặc 'elevenlabs' trong config.py"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    sample_text = (
        "You wake up when your body is ready. No alarm, no schedule. "
        "For 99 percent of human history, this was completely normal. "
        "Your ancestors slept in two phases, not one. "
        "Modern science is only now rediscovering what ancient humans already knew."
    )

    test_project_dir = os.path.join(config.BASE_OUTPUT_DIR, "_audio_test")
    os.makedirs(test_project_dir, exist_ok=True)

    print("=" * 60)
    print("  AUDIO GENERATOR — Test Module")
    print(f"  Engine: {config.TTS_ENGINE}")
    print(f"  Output: {test_project_dir}")
    print("=" * 60)
    print(f"\nScript ({len(sample_text)} chars):\n{sample_text}\n")

    try:
        audio_path, timing = generate_audio(sample_text, test_project_dir)

        print(f"\n✅ Audio: {audio_path}")
        print(f"   Size:  {os.path.getsize(audio_path):,} bytes")
        print(f"\n📋 Timing ({len(timing)} câu):")
        for t in timing:
            print(f"   [{t['index']}] {t['start']:.2f}s → {t['end']:.2f}s | {t['text'][:60]}...")

        # Kiểm tra timing.json đã được tạo
        timing_path = os.path.join(test_project_dir, "timing.json")
        if os.path.exists(timing_path):
            print(f"\n✅ timing.json đã lưu: {timing_path}")
        else:
            print(f"\n❌ timing.json KHÔNG tìm thấy!")

    except Exception as e:
        logger.error(f"Lỗi khi tạo audio: {e}", exc_info=True)
        print(f"\n❌ Lỗi: {e}")
