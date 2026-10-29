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
CORE_VERSION = "1.2.9"

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
    "custom_snippets",
    "tech_terms_normalization",
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
MN_PHONE_PREFIXES: Set[str] = {
    "99", "95", "94", "91", "90", "96", "97", "98", "93",
    "88", "89", "85", "86", "80", "83", "84",
    "70", "75", "77",
}


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

    snips = data.get("snippets")
    if isinstance(snips, dict):
        clean_snips = {}
        for k, v in snips.items():
            if isinstance(k, str) and isinstance(v, str):
                k_str = k.strip().lower()
                v_str = v.strip()
                if k_str and len(k_str) <= 64 and len(v_str) <= 1000:
                    clean_snips[k_str] = v_str
        clean["snippets"] = clean_snips

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


def snap_rect_to_screen_edges(
    x: int,
    y: int,
    w: int,
    h: int,
    work_area: Tuple[int, int, int, int],
    snap_distance: int = 24,
    margin: int = 16,
) -> Tuple[int, int]:
    """
    Snap window rectangle (x, y, w, h) cleanly to screen edges if within snap_distance.
    work_area: (left, top, right, bottom)
    """
    left, top, right, bottom = work_area
    snapped_x = x
    snapped_y = y

    # Left edge snap
    if abs(x - (left + margin)) <= snap_distance:
        snapped_x = left + margin
    # Right edge snap
    elif abs((x + w) - (right - margin)) <= snap_distance:
        snapped_x = right - w - margin

    # Top edge snap
    if abs(y - (top + margin)) <= snap_distance:
        snapped_y = top + margin
    # Bottom edge snap
    elif abs((y + h) - (bottom - margin)) <= snap_distance:
        snapped_y = bottom - h - margin

    return clamp_rect_to_screen(snapped_x, snapped_y, w, h, work_area)


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


def split_number_token_groups(tokens: list[str]) -> list[list[str]]:
    """
    Split a flat sequence of number tokens into distinct number phrases
    when hierarchy resets (e.g. tens after digit or tens, digit after digit).
    e.g. ['ерэн', 'ес', 'арван', 'нэг'] -> [['ерэн', 'ес'], ['арван', 'нэг']]
    """
    groups: list[list[str]] = []
    current_group: list[str] = []
    last_type: Optional[str] = None

    for t in tokens:
        if t in MN_DIGITS:
            cur_type = "digit"
        elif t in MN_TENS:
            cur_type = "ten"
        else:
            cur_type = "scale"

        if current_group:
            if cur_type == "ten" and last_type in ("digit", "ten"):
                groups.append(current_group)
                current_group = []
            elif cur_type == "digit" and last_type == "digit":
                groups.append(current_group)
                current_group = []

        current_group.append(t)
        last_type = cur_type

    if current_group:
        groups.append(current_group)
    return groups


def format_mongolian_currency_and_contacts(text: str) -> str:
    """
    Format spoken/written currency amounts, phone numbers, and quantities:
    - 500000 төгрөг -> 500,000₮
    - 1500000 төгрөгийн -> 1,500,000₮-ийн
    - 50000 төгрөгөөр -> 50,000₮-өөр
    - 1000000 төгрөгтэй -> 1,000,000₮-тэй
    - 35000 ам доллар -> $35,000
    - 99 11 22 33 or 99112233 -> 9911-2233
    - +976 99112233 -> +976 9911-2233
    - 150000 хүн -> 150,000 хүн
    """
    if not text or not isinstance(text, str):
        return ""

    # Convert multipliers like '500 мянга/мянган', '10 сая', '2.5 сая'
    text = re.sub(
        r"\b(\d+\.\d+)\s*(сая|тэрбум)\b",
        lambda m: str(int(float(m.group(1)) * (1000000 if m.group(2) == "сая" else 1000000000))),
        text,
    )
    text = re.sub(
        r"\b(\d+)\s*(мянга|мянган)\b",
        lambda m: str(int(m.group(1)) * 1000),
        text,
    )
    text = re.sub(
        r"\b(\d+)\s*(сая|тэрбум)\b",
        lambda m: str(int(m.group(1)) * (1000000 if m.group(2) == "сая" else 1000000000)),
        text,
    )

    # 1. Spoken pairs of mobile phone numbers: '99 11 22 33' -> '9911-2233'
    def repl_phone_pairs(m: re.Match) -> str:
        prefix = m.group(1)
        if prefix in MN_PHONE_PREFIXES:
            return f"{prefix}{m.group(2)}-{m.group(3)}{m.group(4)}"
        return m.group(0)

    text = re.sub(r"\b([789][0-9])\s+([0-9]{2})\s+([0-9]{2})\s+([0-9]{2})\b", repl_phone_pairs, text)

    # 2. International prefix + mobile phone: '+976 99112233' -> '+976 9911-2233'
    text = re.sub(r"(\+?976\s*)([789][0-9])([0-9]{2})([0-9]{4})\b", r"+976 \2\3-\4", text)

    # 3. 8-digit mobile phone: '99112233' -> '9911-2233'
    def repl_phone_solid(m: re.Match) -> str:
        prefix = m.group(1)
        if prefix in MN_PHONE_PREFIXES:
            return f"{prefix}{m.group(2)}-{m.group(3)}"
        return m.group(0)

    text = re.sub(r"\b([789][0-9])([0-9]{2})([0-9]{4})\b", repl_phone_solid, text)

    # 4. MNT Currency: 500000 төгрөг -> 500,000₮
    def repl_mnt(m: re.Match) -> str:
        val = int(m.group(1))
        suffix = m.group(2)
        formatted = f"{val:,}₮"
        if suffix in ("төгрөгний", "төгрөгийн"):
            return f"{formatted}-ийн"
        elif suffix == "төгрөгөөр":
            return f"{formatted}-өөр"
        elif suffix == "төгрөгтэй":
            return f"{formatted}-тэй"
        return formatted

    text = re.sub(r"\b(\d+)\s*(төгрөгний|төгрөгийн|төгрөгөөр|төгрөгтэй|төгрөг|төг)\b", repl_mnt, text)

    # 5. USD Currency: 100 доллар -> $100
    text = re.sub(
        r"\b(\d+)\s*(ам\s*долларын|ам\s*доллар|долларын|доллар)\b",
        lambda m: f"${int(m.group(1)):,}",
        text,
    )

    # 6. Counter words / quantities: 150000 хүн -> 150,000 хүн
    counters = r"(хүн|хэрэглэгч|ширхэг|тонн|тн|метр|км|кг|хувьцаа|төрөл|данс|бараа)"
    text = re.sub(rf"\b(\d{{4,12}})\s+{counters}\b", lambda m: f"{int(m.group(1)):,} {m.group(2)}", text)

    # 7. Standalone 5+ digit numbers (>= 10,000) not bordering hyphens, periods or pluses
    text = re.sub(r"(?<![-+\d,])(\d{5,12})(?![-+\d,])", lambda m: f"{int(m.group(1)):,}", text)

    return text


def normalize_mongolian_numbers(text: str) -> str:
    """
    Convert written Mongolian numbers into Arabic numerals and format currency & contacts.
    e.g. 'хоёр мянга хорин зургаа' -> '2026', 'ерэн таван хувь' -> '95%',
         'таван зуун мянган төгрөг' -> '500,000₮', 'ерэн ес арван нэг хорин хоёр гучин гурав' -> '9911-2233'
    """
    if not text or not isinstance(text, str):
        return ""

    # Pre-convert digit + Mongolian scales (e.g. '500 мянга', '10 сая', '2.5 сая')
    text = re.sub(
        r"\b(\d+\.\d+)\s*(сая|тэрбум)\b",
        lambda m: str(int(float(m.group(1)) * (1000000 if m.group(2) == "сая" else 1000000000))),
        text,
    )
    text = re.sub(
        r"\b(\d+)\s*(мянга|мянган)\b",
        lambda m: str(int(m.group(1)) * 1000),
        text,
    )
    text = re.sub(
        r"\b(\d+)\s*(сая|тэрбум)\b",
        lambda m: str(int(m.group(1)) * (1000000 if m.group(2) == "сая" else 1000000000)),
        text,
    )

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

            groups = split_number_token_groups(num_tokens)
            parsed_vals = []
            for g in groups:
                v = convert_mn_number_tokens(g)
                if v is not None:
                    parsed_vals.append(str(v))

            if parsed_vals:
                # Check if followed by "хувь"
                if j < n and re.sub(r"[^\w\s]", "", words[j].lower()) == "хувь":
                    parsed_vals[-1] = f"{parsed_vals[-1]}%"
                    j += 1
                result.extend(parsed_vals)
                i = j
                continue
        result.append(words[i])
        i += 1

    joined = " ".join(result)
    return format_mongolian_currency_and_contacts(joined)


def capitalize_sentences(text: str) -> str:
    """
    Capitalize the first letter of each sentence in text.
    Handles:
    - Start of string (including leading whitespace, quotes, dashes)
    - After newlines (\n, \r\n)
    - After sentence-ending punctuation (. ! ? …) followed by whitespace
    Preserves existing whitespace, indentation, and punctuation.
    """
    if not text or not isinstance(text, str):
        return ""

    # Capitalize first letter of string (may be preceded by quotes or opening brackets)
    s = re.sub(
        r"(^|[\r\n\t]+)([\s\"'“”«»\(\[\{]*)([a-zA-Zа-яёөүА-ЯЁӨҮ])",
        lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
        text,
    )

    # Capitalize letter after terminal punctuation (. ! ? …) followed by whitespace
    s = re.sub(
        r"([.!?…]+[\"')”»\]\}]*\s+)([a-zA-Zа-яёөүА-ЯЁӨҮ])",
        lambda m: m.group(1) + m.group(2).upper(),
        s,
    )

    return s


def _replace_period_command(match: re.Match, full_text: str) -> str:
    """
    Disambiguate spoken 'цэг' (voice command for period) from legitimate noun phrases:
    e.g. 'эхлэх цэг', 'цугларах цэг', 'хяналтын цэг', 'А цэг', 'цэг дээр', 'цэг рүү'
    """
    start, end = match.span()
    before = full_text[:start]
    after = full_text[end:]

    # Check preceding word
    prev_match = re.search(r"(\w+)\s+$", before)
    if prev_match:
        prev_word = prev_match.group(1).lower()
        noun_context = {
            "эхлэх", "цугларах", "хяналтын", "эцсийн", "барианы", "тулгуур",
            "огтлолцлын", "уулзах", "хөдлөх", "очих", "байрлах", "тусах",
            "гол", "эгзэгтэй", "энэ", "тэр", "тухайн", "нэг", "хоёр", "гурван",
            "эхлэл", "төгсгөл", "суурь", "өгөгдлийн", "холболтын", "эргэлтийн",
            "зангилаа", "хүрэх",
        }
        if prev_word in noun_context or (len(prev_word) == 1 and prev_word.isalpha()):
            return match.group(0)

    # Check following word
    next_match = re.search(r"^\s+(\w+)", after)
    if next_match:
        next_word = next_match.group(1).lower()
        postposition_context = {
            "дээр", "дээрх", "дээрээ", "рүү", "руу", "рүүгээ", "руугаа",
            "хүртэл", "хооронд", "орчим", "нь", "биш", "дээрээс", "тухай",
        }
        if next_word in postposition_context:
            return match.group(0)

    return "."


def format_speech_text(text: str, auto_punct: bool = True) -> str:
    """
    Clean, capitalize, and punctuate recognized speech text.
    Correctly capitalizes across sentences (. ! ? …) and newlines.
    """
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""

    # Capitalize every sentence start and newline
    s = capitalize_sentences(s)

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
    'Сайн байна уу.\nБи өнөөдөр хичээлтэй, гэхдээ'
    """
    if not text or not isinstance(text, str):
        return ""
    s = text

    commands = [
        (r"(?i)\b(дараагийн нүд|дараагийн талбар|дараагийн хүснэгт|дараагийн нүдэнд)\b", "\t"),
        (r"(?i)\b(доод нүд|доод талбар|доод нүдэнд)\b", "\n"),
        (r"(?i)\b(таб товч|таб)\b", "\t"),
        (r"(?i)\b(шинэ мөр|догол мөр|шинэ мөрөөр)\b", "\n"),
        (r"(?i)\b(давхар цэг|тодорхойлох цэг)\b", ":"),
        (r"(?i)\b(цэг таслал)\b", ";"),
        (r"(?i)\b(асуултын тэмдэг)\b", "?"),
        (r"(?i)\b(анхаарлын тэмдэг)\b", "!"),
        (r"(?i)\b(хашилт нээх|хашилт нээ)\b", '"'),
        (r"(?i)\b(хашилт хаах|хашилт хаа)\b", '"'),
        (r"(?i)\b(хаалт нээх|хаалт нээ)\b", "("),
        (r"(?i)\b(хаалт хаах|хаалт хаа)\b", ")"),
        (r"(?i)\b(таслал)\b", ","),
        (r"(?i)\b(зураас)\b", " - "),
    ]

    for pat, rep in commands:
        s = re.sub(pat, rep, s)

    # Disambiguate 'цэг' (voice command for period vs legitimate noun phrases)
    s = re.sub(r"(?i)\bцэг\b", lambda m: _replace_period_command(m, s), s)

    # Clean up spaces before punctuation
    s = re.sub(r"\s+([.,!?:;\)])", r"\1", s)
    # Ensure space after punctuation if followed by a letter/digit
    s = re.sub(r"([.,!?:;])([^\s\d.,!?:;\"'\)])", r"\1 \2", s)
    # Clean space after opening bracket/quote
    s = re.sub(r"([\(\"])\s+", r"\1", s)
    # Clean space before opening bracket
    s = re.sub(r"(\S)(\()", r"\1 \2", s)
    # Clean up newline spaces
    s = re.sub(r"[ ]*\n[ ]*", "\n", s)
    formatted_lines = []
    for line in s.split("\n"):
        parts = [re.sub(r"[ ]+", " ", part).strip() for part in line.split("\t")]
        formatted_lines.append("\t".join(parts).strip())
    res = "\n".join(formatted_lines).strip()
    return capitalize_sentences(res)


def strip_filler_words(text: str) -> str:
    """
    Remove Mongolian conversational filler words like 'нөгөө', 'аан', 'юу л даа', etc.
    Protects affirmative responses like 'Тийм ээ, би зөвшөөрч байна', 'Тийм ээ', 'Тиймээ, тэгье'.
    """
    if not text or not isinstance(text, str):
        return ""

    s = text

    # Multi-word fillers
    composite_fillers = [
        r"(?i)\b(нөгөө нэг|юу л даа|ер нь бол|за тэгээд|тэгээд нөгөө)\b",
    ]
    for pat in composite_fillers:
        s = re.sub(pat, " ", s)

    # Single fillers (excluding тиймээ/тийм ээ which may be affirmative)
    single_fillers = [
        r"(?i)\b(нөгөө|нөгөөх|аан|ер нь)\b",
    ]
    for pat in single_fillers:
        s = re.sub(pat, " ", s)

    # For 'тийм ээ' / 'тиймээ':
    # Protect if affirmative: at the beginning of utterance/clause, standalone, or followed by comma
    def _tiimee_filter(match: re.Match) -> str:
        start = match.start()
        prefix = s[:start].strip()
        if not prefix or prefix[-1] in (".", "!", "?", ":", ";", "\n", ","):
            return match.group(0)
        suffix = s[match.end():].lstrip()
        if suffix.startswith((",", ".", "!", "?", ":", ";")):
            return match.group(0)
        return " "

    s = re.sub(r"(?i)\b(тийм ээ|тиймээ)\b", _tiimee_filter, s)

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


def format_lrc_time(seconds: float) -> str:
    """Format seconds (float) as standard synchronized lyrics timestamp [mm:ss.xx]"""
    if seconds < 0:
        seconds = 0.0
    total_centis = int(seconds * 100.0 + 0.5)
    mins = total_centis // 6000
    secs = (total_centis % 6000) // 100
    centis = total_centis % 100
    return f"[{mins:02d}:{secs:02d}.{centis:02d}]"


def generate_lrc(segments: list, title: str = "", artist: str = "") -> str:
    """
    Generate Synchronized Lyrics (.lrc) format from segment dicts.
    Each item: {'start': float, 'end': float, 'text': str}
    """
    if not segments:
        return ""
    lines = []
    if title:
        lines.append(f"[ti:{title.strip()}]")
    if artist:
        lines.append(f"[ar:{artist.strip()}]")
    lines.append("[by:VOICE AI]")
    lines.append("")

    for seg in segments:
        start_t = float(seg.get("start", 0.0))
        text = str(seg.get("text", "")).strip()
        if text:
            lines.append(f"{format_lrc_time(start_t)}{text}")

    return "\r\n".join(lines).strip() + "\r\n"


def format_vtt_time(seconds: float) -> str:
    """Format seconds (float) as standard WebVTT timestamp HH:MM:SS.mmm"""
    if seconds < 0:
        seconds = 0.0
    total_millis = int(seconds * 1000.0 + 0.5)
    hrs = total_millis // 3600000
    mins = (total_millis % 3600000) // 60000
    secs = (total_millis % 60000) // 1000
    millis = total_millis % 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def generate_vtt(segments: list) -> str:
    """
    Generate WebVTT (.vtt) subtitle content from a list of dicts.
    Each item: {'start': float, 'end': float, 'text': str}
    """
    if not segments:
        return "WEBVTT\r\n"
    lines = ["WEBVTT", ""]
    for idx, seg in enumerate(segments, start=1):
        start_t = float(seg.get("start", 0.0))
        end_t = float(seg.get("end", start_t + 2.5))
        if end_t <= start_t:
            end_t = start_t + 1.0
        text = str(seg.get("text", "")).strip()
        lines.append(str(idx))
        lines.append(f"{format_vtt_time(start_t)} --> {format_vtt_time(end_t)}")
        lines.append(text)
        lines.append("")
    return "\r\n".join(lines).strip() + "\r\n"


def apply_voice_snippets(text: str, snippets: Optional[Dict[str, str]]) -> str:
    """
    Replace custom user voice trigger phrases with their configured text expansions.
    e.g. 'миний имэйл' -> 'user@gmail.com', 'миний данс' -> 'Хаан банк: 5000xxxxxx'
    """
    if not text or not snippets or not isinstance(snippets, dict):
        return text or ""
    s = text
    sorted_triggers = sorted(snippets.keys(), key=len, reverse=True)
    for trigger in sorted_triggers:
        replacement = snippets[trigger]
        if not trigger or not isinstance(trigger, str) or not replacement or not isinstance(replacement, str):
            continue
        pattern = r"(?i)(?<![^\W_])" + re.escape(trigger.strip()) + r"(?![^\W_])"
        s = re.sub(pattern, replacement.strip(), s)
    return s


TECH_TERMS_MAP: Dict[str, str] = {
    "фэйсбүүк": "Facebook",
    "фейсбүүк": "Facebook",
    "фэйсбүк": "Facebook",
    "юүтүб": "YouTube",
    "юүтүби": "YouTube",
    "ютуб": "YouTube",
    "инстаграм": "Instagram",
    "телеграм": "Telegram",
    "гүгл": "Google",
    "гугл": "Google",
    "хром": "Chrome",
    "виндовс": "Windows",
    "виндоус": "Windows",
    "эксел": "Excel",
    "ворд": "Word",
    "пауэрпойнт": "PowerPoint",
    "зуум": "Zoom",
    "зум": "Zoom",
    "пидиэф": "PDF",
    "пдф": "PDF",
    "вайфай": "Wi-Fi",
    "вай фай": "Wi-Fi",
    "риэкт": "React",
    "пайтон": "Python",
    "гит": "Git",
    "гитхаб": "GitHub",
    "айфон": "iPhone",
    "андроид": "Android",
    "капкат": "CapCut",
    "премьер": "Premiere",
}


def normalize_tech_terms(text: str) -> str:
    """
    Converts phonetically spelled Mongolian tech terms into clean standard brand names.
    e.g. 'фэйсбүүк' -> 'Facebook', 'зуум' -> 'Zoom', 'пидиэф' -> 'PDF', 'гитхаб' -> 'GitHub'
    """
    if not text or not isinstance(text, str):
        return text or ""
    s = text
    for cyr, lat in sorted(TECH_TERMS_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = r"(?i)\b" + re.escape(cyr) + r"\b"
        s = re.sub(pattern, lat, s)
    return s

def extract_summary_and_actions(text: str) -> dict:
    """
    Analyzes conversation, dictation, or meeting transcript text to extract:
    - summary: Cohesive summary paragraph
    - key_points: Bullet points of major discussion topics
    - action_items: Actionable tasks/to-dos with concrete responsibilities
    - decisions: Key agreements, approvals, and decisions reached
    """
    if not text or not isinstance(text, str) or not text.strip():
        return {
            "summary": "",
            "key_points": [],
            "action_items": [],
            "decisions": [],
        }

    raw = text.strip()
    raw_sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?\n])\s+", raw)
        if s.strip()
    ]
    if not raw_sentences:
        raw_sentences = [raw]

    action_items = []
    decisions = []
    key_points = []

    action_patterns = [
        r"(?i)\b(хийх хэрэгтэй|хийх ёстой|хийх болно|бэлтгэх|шалгах|холбогдох|явуулах|өгөх|шийдвэрлэх|дуусгах|эхлүүлэх|төлөвлөх|илгээх|хүргэх|засах|нэмэх|хэрэгжүүлэх|батлах|гүйцэтгэх)\b",
        r"(?i)\b(явуулна|бэлтгэнэ|шалгана|холбогдоно|өгнө|илгээнэ|хүргэнэ|дуусгана|эхлүүлнэ|засна|нэмнэ|ажиллана|судална|танилцуулна|мэдэгдэнэ|хүлээнэ|гүйцэтгэнэ)\b",
        r"(?i)\b(need to|must|will do|action item|todo|follow up|schedule|assign|ensure|prepare|review|submit|complete|send|contact|check|implement)\b",
    ]

    decision_patterns = [
        r"(?i)\b(шийдвэрлэв|тохиролцов|шийдлээ|тохирлоо|зөвшөөрөв|зөвшөөрлөө|батлав|баталлаа|сонгов|сонголоо|тогтов|тогтлоо|шийдэв|шийдсэн)\b",
        r"(?i)\b(decided|agreed|resolved|approved|selected|concluded|confirmed)\b",
    ]

    for sentence in raw_sentences:
        clean_s = sentence.strip(" -*•\t\r\n")
        if not clean_s or len(clean_s) < 5:
            continue

        is_decision = any(re.search(pat, clean_s) for pat in decision_patterns)
        if is_decision and clean_s not in decisions:
            decisions.append(clean_s)

        is_action = any(re.search(pat, clean_s) for pat in action_patterns)
        if is_action and clean_s not in action_items:
            action_items.append(clean_s)

        is_greeting = bool(re.match(r"(?i)^(сайн байна уу|байна уу|баярлалаа|hello|hi)\b", clean_s))
        if len(clean_s) >= 15 and not is_greeting and clean_s not in key_points:
            key_points.append(clean_s)

    if len(raw_sentences) <= 2:
        summary = raw
    elif key_points:
        summary = " ".join(key_points[:3])
    else:
        summary = " ".join(raw_sentences[:3])

    return {
        "summary": summary,
        "key_points": key_points[:5],
        "action_items": action_items[:8],
        "decisions": decisions[:5],
    }

FORMAL_REPLACEMENTS = [
    (r"(?i)\bбид нар\b", "бид"),
    (r"(?i)\bэнэ ажил\b", "тухайн ажил"),
    (r"(?i)\bтийм учраас\b", "иймд"),
    (r"(?i)\bтэгээд бас\b", "үүнээс гадна"),
    (r"(?i)\bтэгээд\b", "улмаар"),
    (r"(?i)\bхийгээд өгөөрэй\b", "гүйцэтгэнэ үү"),
    (r"(?i)\bхийж өгөөрэй\b", "гүйцэтгэнэ үү"),
    (r"(?i)\bявуулаарай\b", "ирүүлнэ үү"),
    (r"(?i)\bявуулна гэж бодож байна\b", "илгээхээр төлөвлөж байна"),
    (r"(?i)\bгэж бодож байна\b", "хэмээн үзэж байна"),
    (r"(?i)\bуулзах хэрэгтэй\b", "уулзалт зохион байгуулах шаардлагатай"),
    (r"(?i)\bярилцаж тохиролцсон\b", "хэлэлцэн тохиролцов"),
    (r"(?i)\bсайн ажиллалаа\b", "үр дүнтэй ажиллалаа"),
    (r"(?i)\bбайна даа\b", "байна"),
    (r"(?i)\bбайгаа юм\b", "байгаа болно"),
    (r"(?i)\bбаярлалаа\b", "Талархал илэрхийлье"),
]


def rewrite_text_style(text: str, style: str = "formal") -> dict:
    """
    AI Smart Tone & Style Rewriter for Mongolian speech and transcripts.
    Styles:
    - formal: Official business, governmental, and executive phrasing
    - email: Structured email draft with Subject, Salutation, Body, Sign-off
    - social: Engaging social post with catchy header, bullet points, call to action
    - proofread: Error correction, punctuation cleaning, and deduplication
    """
    if not text or not isinstance(text, str) or not text.strip():
        return {
            "status": "ok",
            "style": style,
            "original": "",
            "rewritten": "",
            "changes_count": 0,
        }

    raw = text.strip()
    cleaned = strip_filler_words(raw)
    cleaned = normalize_tech_terms(cleaned)
    style = (style or "formal").lower().strip()
    changes_count = 0

    if style == "formal":
        s = cleaned
        for pat, rep in FORMAL_REPLACEMENTS:
            new_s, n = re.subn(pat, rep, s)
            if n > 0:
                s = new_s
                changes_count += n
        s = capitalize_sentences(s)
        if not s.endswith((".", "!", "?")):
            s += "."
        rewritten = s

    elif style == "email":
        s = cleaned
        for pat, rep in FORMAL_REPLACEMENTS:
            s = re.sub(pat, rep, s)
        s = capitalize_sentences(s)
        if not s.endswith((".", "!", "?")):
            s += "."

        # Extract subject from first sentence or key topic
        first_clause = re.split(r"[.!?\n]+", s)[0].strip()
        words = first_clause.split()
        subj = " ".join(words[:6]) + ("..." if len(words) > 6 else "")
        if not subj:
            subj = "Ажлын мэдээлэл"

        rewritten = (
            f"Гарчиг: {subj}\n\n"
            f"Сайн байна уу?\n\n"
            f"{s}\n\n"
            f"Хүндэтгэсэн,\n"
            f"[Таны нэр]"
        )
        changes_count = 1

    elif style == "social":
        s = cleaned
        sentences = [line.strip() for line in re.split(r"[.!?\n]+", s) if line.strip()]
        if not sentences:
            sentences = [s]

        headline = sentences[0]
        bullets = sentences[1:]

        lines = [f"✨ {headline}"]
        if bullets:
            lines.append("")
            for b in bullets:
                lines.append(f"📌 {b}")
        lines.append("")
        lines.append("💬 Та энэ талаар ямар бодолтой байна вэ? Доор саналаа хуваалцаарай!")
        rewritten = "\n".join(lines)
        changes_count = len(sentences)

    else:  # proofread
        # Deduplicate consecutive repeated words (e.g. 'би би' -> 'би')
        s, n = re.subn(r"\b(\w+)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)
        changes_count += n
        s = capitalize_sentences(s)
        if not s.endswith((".", "!", "?")):
            s += "."
        rewritten = s

    return {
        "status": "ok",
        "style": style,
        "original": raw,
        "rewritten": rewritten,
        "changes_count": changes_count,
    }

