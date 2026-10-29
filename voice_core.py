"""
VOICE Desktop - Core Logic Module (Pure Python, Zero External C-Dependencies)
Contains validated business logic, setting sanitizers, geometry math, number normalizers,
and text formatting. Importable in headless CI environments (Windows, Linux, macOS).
"""
import os
import re
import time
from typing import Any, Optional, Tuple, Dict, Set

# Version
CORE_VERSION = "1.2.8"

# Setting choices allowed by the engine
SETTING_CHOICES: Dict[str, Set[str]] = {
    "hotkey": {
        "ctrl_alt",
        "f8",
        "ctrl_shift",
        "alt_shift",
        "ctrl_space",
        "f9",
        "f10",
        "f2",
        "f4",
    },
    "stt_engine": {"google", "whisper", "chimege"},
    "whisper_model": {"tiny", "base", "small", "medium", "large-v3"},
    "language": {"auto", "mn", "en", "ja"},
}

BOOLEAN_SETTINGS: Set[str] = {
    "restore_clipboard",
    "undo_button",
    "start_with_windows",
    "sound_cues",
    "auto_punctuation",
    "number_normalization",
    "voice_actions",
    "filler_word_cleaner",
    "noise_gate",
    "auto_insert_text",
}

VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

LANG_CYCLE = ["auto", "mn", "en", "ja"]
LANG_LABELS: Dict[str, str] = {
    "auto": "AUTO",
    "mn": "MN",
    "en": "EN",
    "ja": "JA",
}

HOTKEY_NAMES: Dict[str, str] = {
    "f8": "F8",
    "ctrl_alt": "Ctrl+Alt",
    "ctrl_shift": "Ctrl+Shift",
    "alt_shift": "Alt+Shift",
    "ctrl_space": "Ctrl+Space",
    "f9": "F9",
    "f10": "F10",
    "f2": "F2",
    "f4": "F4",
}

MN_DIGITS: Dict[str, int] = {
    "тэг": 0, "нэг": 1, "нэгэн": 1, "хоёр": 2, "гурав": 3, "гурван": 3,
    "дөрөв": 4, "дөрвөн": 4, "тав": 5, "таван": 5, "зургаа": 6, "зургаан": 6,
    "долоо": 7, "долоон": 7, "найм": 8, "найман": 8, "ес": 9, "есөн": 9,
}
MN_TENS: Dict[str, int] = {
    "арав": 10, "арван": 10, "хорь": 20, "хорин": 20, "гуч": 30, "гучин": 30,
    "дөч": 40, "дөчин": 40, "тавь": 50, "тавин": 50, "жар": 60, "жаран": 60,
    "дал": 70, "далан": 70, "ная": 80, "наян": 80, "ер": 90, "ерэн": 90,
}
MN_SCALES: Dict[str, int] = {
    "зуу": 100, "зуун": 100,
    "мянга": 1000, "мянган": 1000,
    "сая": 1000000,
    "тэрбум": 1000000000,
}
ALL_MN_NUM_WORDS: Set[str] = set(MN_DIGITS.keys()) | set(MN_TENS.keys()) | set(MN_SCALES.keys())


def sanitize_settings(data: Any) -> Dict[str, Any]:
    """
    Keep only known configuration keys with validated values.
    Discards unknown keys, prevents injection, and bounds string lengths.
    """
    clean: Dict[str, Any] = {}
    if not isinstance(data, dict):
        return clean

    for key, allowed in SETTING_CHOICES.items():
        val = data.get(key)
        if isinstance(val, str) and val.lower().strip() in allowed:
            clean[key] = val.lower().strip()

    for key in BOOLEAN_SETTINGS:
        val = data.get(key)
        if isinstance(val, bool):
            clean[key] = val
        elif isinstance(val, (int, str)):
            if str(val).lower() in ("true", "1", "yes"):
                clean[key] = True
            elif str(val).lower() in ("false", "0", "no"):
                clean[key] = False

    tok = data.get("chimege_token")
    if isinstance(tok, str) and len(tok) <= 512:
        clean["chimege_token"] = tok.strip()

    return clean


def is_safe_voice_id(voice_id: str) -> bool:
    """Return True if voice_id consists only of 1-64 alphanumeric, dash, or underscore characters."""
    if not isinstance(voice_id, str):
        return False
    return bool(VOICE_ID_RE.match(voice_id))


def safe_clone_wav_path(base_clones_dir: str, voice_id: str) -> str:
    """
    Return absolute path for a clone WAV file, verifying it stays within base_clones_dir.
    Raises ValueError on path traversal attempts or invalid IDs.
    """
    if not is_safe_voice_id(voice_id):
        raise ValueError("Invalid voice id format")

    base = os.path.realpath(base_clones_dir)
    target = os.path.realpath(os.path.join(base, f"{voice_id}.wav"))

    if os.path.commonpath([base, target]) != base:
        raise ValueError("Path traversal detected")

    return target


def get_fallback_flowbar_pos_math(
    work_area: Tuple[int, int, int, int],
    bar_w: int = 360,
    bar_h: int = 52,
    margin_x: int = 24,
    margin_y: int = 24,
) -> Tuple[int, int]:
    """
    Compute default bottom-right screen coordinates for the FlowBar window.
    work_area: (left, top, right, bottom)
    """
    left, top, right, bottom = work_area
    fx = max(left + 20, right - bar_w - margin_x)
    fy = max(top + 20, bottom - bar_h - margin_y)
    return fx, fy


def clamp_rect_to_screen(
    x: int,
    y: int,
    w: int,
    h: int,
    work_area: Tuple[int, int, int, int],
) -> Tuple[int, int]:
    """
    Clamp window rectangle (x, y, w, h) so it stays fully inside the primary work area.
    work_area: (left, top, right, bottom)
    """
    left, top, right, bottom = work_area
    max_x = max(left, right - w)
    max_y = max(top, bottom - h)
    clamped_x = min(max(x, left), max_x)
    clamped_y = min(max(y, top), max_y)
    return clamped_x, clamped_y


def is_rect_in_bounds(
    x: int,
    y: int,
    w: int,
    h: int,
    bounds: Tuple[int, int, int, int],
    min_overlap_ratio: float = 0.5,
) -> bool:
    """
    Check if a window rectangle (x, y, w, h) substantially intersects screen bounds.
    """
    b_left, b_top, b_right, b_bottom = bounds
    inter_left = max(x, b_left)
    inter_top = max(y, b_top)
    inter_right = min(x + w, b_right)
    inter_bottom = min(y + h, b_bottom)

    if inter_right <= inter_left or inter_bottom <= inter_top:
        return False

    inter_area = (inter_right - inter_left) * (inter_bottom - inter_top)
    total_area = w * h
    return (inter_area / float(total_area)) >= min_overlap_ratio


def compute_flowbar_status(
    state: Dict[str, Any],
    now: Optional[float] = None,
    heartbeat_timeout: float = 5.0,
) -> Dict[str, Any]:
    """
    Compute structured, unambiguous FlowBar health metrics for the dashboard and API.
    """
    if now is None:
        now = time.time()

    ui_alive_flag = bool(state.get("ui_alive", False))
    heartbeat = float(state.get("ui_heartbeat", 0.0) or 0.0)
    staleness = max(0.0, now - heartbeat) if heartbeat > 0 else 999999.0
    is_responsive = ui_alive_flag and (staleness <= heartbeat_timeout)

    return {
        "ui_alive": is_responsive,
        "ui_heartbeat_age_sec": round(staleness, 2) if heartbeat > 0 else None,
        "ui_error": state.get("ui_error", ""),
        "ui_restarts": state.get("ui_restarts", 0),
        "visible": bool(state.get("visible", True)),
        "status": state.get("status", "idle"),
        "language": state.get("language", "auto"),
        "pos": state.get("pos", ""),
    }


def convert_mn_number_tokens(tokens: list[str]) -> Optional[int]:
    """Parse a list of Mongolian number tokens into an integer value."""
    if not tokens or not all(t in ALL_MN_NUM_WORDS for t in tokens):
        return None
    total = 0
    current = 0
    for w in tokens:
        if w in MN_DIGITS:
            current += MN_DIGITS[w]
        elif w in MN_TENS:
            current += MN_TENS[w]
        elif w in ("зуу", "зуун"):
            current = (current or 1) * 100
        elif w in ("мянга", "мянган"):
            total += (current or 1) * 1000
            current = 0
        elif w == "сая":
            total += (current or 1) * 1000000
            current = 0
        elif w == "тэрбум":
            total += (current or 1) * 1000000000
            current = 0
    return total + current


def normalize_mongolian_numbers(text: str) -> str:
    """
    Convert written Mongolian numbers into Arabic numerals.
    e.g. 'хоёр мянга хорин зургаа' -> '2026', 'ерэн таван хувь' -> '95%'
    """
    if not text or not isinstance(text, str):
        return ""
    words = text.split()
    if not words:
        return text

    result = []
    i = 0
    n = len(words)

    while i < n:
        w_clean = re.sub(r"[^\w\s]", "", words[i].lower())
        if w_clean in ALL_MN_NUM_WORDS:
            # Accumulate span of number words
            j = i
            num_tokens = []
            while j < n:
                token_clean = re.sub(r"[^\w\s]", "", words[j].lower())
                if token_clean in ALL_MN_NUM_WORDS:
                    num_tokens.append(token_clean)
                    j += 1
                else:
                    break
            val = convert_mn_number_tokens(num_tokens)
            if val is not None:
                # Check if followed by "хувь"
                if j < n and re.sub(r"[^\w\s]", "", words[j].lower()) == "хувь":
                    result.append(f"{val}%")
                    j += 1
                else:
                    result.append(str(val))
                i = j
                continue
        result.append(words[i])
        i += 1

    return " ".join(result)


def format_speech_text(text: str, auto_punct: bool = True) -> str:
    """
    Clean, capitalize, and punctuate recognized speech text.
    """
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""

    # Capitalize first character
    s = s[0].upper() + s[1:]

    if not auto_punct:
        return s

    # Check if already has terminal punctuation
    if s[-1] not in (".", "?", "!", "…", ",", ":", ";"):
        s_lower = s.lower()
        question_suffixes = (
            " уу", " үү", " бэ", " вэ", " юу", " билүү", " бил үү",
            " юмуу", " юм уу", " байхгүй юу", " байна уу", " байсан уу",
        )
        question_prefixes = (
            "хэн ", "юу ", "хаана ", "хэзээ ", "яагаад ", "яаж ", "ямар ",
            "хэд ", "хэдээр ", "хэдэн ", "why ", "what ", "where ", "when ",
            "how ", "who ", "which ", "is ", "are ", "can ", "could ",
        )
        if s_lower.endswith(question_suffixes) or s_lower.startswith(question_prefixes):
            s += "?"
        else:
            s += "."

    return s


def enhance_ssml_cadence(text: str) -> str:
    """
    Inserts natural prosodic pause tags for SSML generation in VoiceStudio TTS.
    Comma pauses: 200ms, sentence end pauses: 450ms.
    """
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    # Add breath pause after commas
    s = re.sub(r"([,，、])\s*", r'\1 <break time="200ms"/> ', s)
    # Add cadence pause after periods, semicolons, colons
    s = re.sub(r"([.。:;])(\s+|$)", r'\1 <break time="450ms"/> ', s)
    # Add cadence pause after exclamation and question marks
    s = re.sub(r"([?？!！])(\s+|$)", r'\1 <break time="400ms"/> ', s)
    return re.sub(r"\s+", " ", s).strip()


def apply_voice_commands(text: str) -> str:
    """
    Converts spoken voice commands in Mongolian to punctuation, newlines, and symbols.
    e.g. 'сайн байна уу цэг шинэ мөр би өнөөдөр хичээлтэй таслал гэхдээ' ->
    'сайн байна уу.\nби өнөөдөр хичээлтэй, гэхдээ'
    """
    if not text or not isinstance(text, str):
        return ""
    s = text

    commands = [
        (r"(?i)\b(шинэ мөр|догол мөр|шинэ мөрөөр)\b", "\n"),
        (r"(?i)\b(давхар цэг|тодорхойлох цэг)\b", ":"),
        (r"(?i)\b(асуултын тэмдэг)\b", "?"),
        (r"(?i)\b(анхаарлын тэмдэг)\b", "!"),
        (r"(?i)\b(хашилт нээх|хашилт нээ)\b", '"'),
        (r"(?i)\b(хашилт хаах|хашилт хаа)\b", '"'),
        (r"(?i)\b(хаалт нээх|хаалт нээ)\b", "("),
        (r"(?i)\b(хаалт хаах|хаалт хаа)\b", ")"),
        (r"(?i)\b(цэг)\b", "."),
        (r"(?i)\b(таслал)\b", ","),
        (r"(?i)\b(зураас)\b", " - "),
    ]

    for pat, rep in commands:
        s = re.sub(pat, rep, s)

    # Clean up spaces before punctuation
    s = re.sub(r"\s+([.,!?:;\)])", r"\1", s)
    # Ensure space after punctuation if followed by a letter/digit
    s = re.sub(r"([.,!?:;])([^\s\d.,!?:;\"'\)])", r"\1 \2", s)
    # Clean space after opening bracket/quote
    s = re.sub(r"([\(\"])\s+", r"\1", s)
    # Clean space before opening bracket
    s = re.sub(r"(\S)(\()", r"\1 \2", s)
    # Clean up newline spaces
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n")]
    return "\n".join(lines).strip()


def strip_filler_words(text: str) -> str:
    """
    Remove Mongolian conversational filler words like 'нөгөө', 'аан', 'тиймээ', etc.
    """
    if not text or not isinstance(text, str):
        return ""

    filler_patterns = [
        r"(?i)\b(нөгөө нэг|юу л даа|ер нь бол|за тэгээд|тэгээд нөгөө)\b",
        r"(?i)\b(нөгөө|нөгөөх|аан|тиймээ|тийм ээ|ер нь)\b",
    ]
    s = text
    for pat in filler_patterns:
        s = re.sub(pat, "", s)

    # Clean punctuation immediately preceded by empty spaces
    s = re.sub(r"\s+([.,!?:;])", r"\1", s)
    # Collapse multiple spaces
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def calculate_pcm_rms(pcm_bytes: bytes) -> float:
    """Calculate RMS amplitude of 16-bit PCM mono audio without external libraries."""
    import struct, math
    if not pcm_bytes or len(pcm_bytes) < 2:
        return 0.0
    count = len(pcm_bytes) // 2
    shorts = struct.unpack(f"<{count}h", pcm_bytes[:count * 2])
    sum_sq = sum(s * s for s in shorts)
    return math.sqrt(sum_sq / count)


def trim_silence_pcm(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
    sample_width: int = 2,
    chunk_ms: int = 30,
    threshold_rms: float = 300.0,
    lead_in_ms: int = 120,
) -> bytes:
    """
    Trim leading and trailing silence below threshold_rms from 16-bit PCM audio.
    Preserves speech head and tail padding.
    """
    if not pcm_bytes or len(pcm_bytes) < 2:
        return pcm_bytes

    bytes_per_sample = sample_width
    chunk_bytes = int(sample_rate * (chunk_ms / 1000.0) * bytes_per_sample)
    if chunk_bytes <= 0:
        return pcm_bytes

    total_len = len(pcm_bytes)
    first_speech_byte = None
    last_speech_byte = None

    for offset in range(0, total_len, chunk_bytes):
        chunk = pcm_bytes[offset:offset + chunk_bytes]
        if len(chunk) < 4:
            break
        rms = calculate_pcm_rms(chunk)
        if rms >= threshold_rms:
            if first_speech_byte is None:
                first_speech_byte = offset
            last_speech_byte = offset + len(chunk)

    if first_speech_byte is None:
        return pcm_bytes

    lead_pad = int(sample_rate * (lead_in_ms / 1000.0) * bytes_per_sample)
    start_idx = max(0, first_speech_byte - lead_pad)
    end_idx = min(total_len, last_speech_byte + lead_pad)

    # Align to 2-byte boundary
    start_idx = (start_idx // 2) * 2
    end_idx = (end_idx // 2) * 2

    return pcm_bytes[start_idx:end_idx]


def format_srt_time(seconds: float) -> str:
    """Format seconds (float) as standard SubRip timestamp HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def generate_srt(segments: list) -> str:
    """
    Generate SubRip (.srt) subtitle content from a list of dicts.
    Each item: {'start': float, 'end': float, 'text': str}
    """
    if not segments:
        return ""
    lines = []
    for idx, seg in enumerate(segments, start=1):
        start_t = float(seg.get("start", 0.0))
        end_t = float(seg.get("end", start_t + 2.5))
        if end_t <= start_t:
            end_t = start_t + 1.0
        text = str(seg.get("text", "")).strip()
        lines.append(str(idx))
        lines.append(f"{format_srt_time(start_t)} --> {format_srt_time(end_t)}")
        lines.append(text)
        lines.append("")
    return "\r\n".join(lines).strip() + "\r\n"
