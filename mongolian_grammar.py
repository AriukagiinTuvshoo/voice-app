"""
VOICE APP — Mongolian Smart Grammar, Morphology & Voice Commands Engine (Stage 3)
-------------------------------------------------------------------------------
Handles:
1. Morphology & Suffix Attachment (Залгавар үгсийн дүрэм):
   - Re-attaches mistakenly detached suffixes (e.g. 'Улаанбаатар т' -> 'Улаанбаатарт')
   - Vowel harmony compliance (Эгшиг зохицох ёс: эр/эм/саармаг эгшиг)
   - Preservation & separation of postpositions and particles:
     'дээр', 'дагуу', 'тухай', 'болон', 'юм уу', 'болно уу'
   - Prevents aggressive over-merging; preserves ambiguous stems.
2. Voice Commands & Punctuation (Дуут тушаал ба цэг тэмдэг):
   - 'Шинэ мөр' -> '\\n'
   - 'Шинэ догол' / 'шинэ догол мөр' -> '\\n\\n'
   - 'Цэг' -> '.' (with context-aware noun disambiguation)
   - 'Таслал' -> ','
   - 'Асуултын тэмдэг' -> '?'
   - 'Анхаарлын тэмдэг' -> '!'
   - 'Хаалт нээх' -> '('
   - 'Хаалт хаах' -> ')'
   - 'Сүүлийнхийг арилга' -> One-time Backspace / Undo action
3. Custom Vocabulary Prompt Builder (Хувийн толь бичиг):
   - Safely creates bounded prompt for Whisper --prompt / initial_prompt.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple, List, Set, Dict


# ---------------------------------------------------------------------------
# Vowel Harmony & Phonology Definitions
# ---------------------------------------------------------------------------
BACK_VOWELS: Set[str] = set("аоуяёю")
FRONT_VOWELS: Set[str] = set("эөүе")
NEUTRAL_VOWELS: Set[str] = set("ий")

# Standalone postpositions, conjunctions, and particles that MUST REMAIN SEPARATED
PROTECTED_STANDALONE_WORDS: Set[str] = {
    "дээр", "дээрх", "дээрээ", "дээрээс",
    "дагуу", "дагуух",
    "тухай", "тухайгаа", "тухайгаар",
    "болон",
    "юм уу", "болно уу",
    "юм", "уу", "үү", "биш", "мөн", "тул", "тулд",
    "хүртэл", "орчим", "шахам", "гээд", "гэж",
    "руу", "рүү", "луу", "лүү",
    "байна уу", "байсан уу",
}

# Single-letter and short suffixes that often get split in Whisper speech recognition
DETACHED_SUFFIXES: Set[str] = {
    # Dative-locative (өгөх орших)
    "т", "д", "ад", "эд", "од", "өд",
    # Accusative (заах)
    "г", "ыг", "ийг",
    # Genitive (харьяалах)
    "ын", "ийн", "ний", "ны",
    # Ablative (гарах)
    "аас", "ээс", "оос", "өөс",
    # Instrumental (үйлдэх)
    "аар", "ээр", "оор", "өөр",
    # Comitative (хамтрах)
    "тай", "тэй", "той",
    # Reflexive (хамаатуулах)
    "аа", "ээ", "оо", "өө", "даа", "дээ", "доо", "дөө", "таа", "тээ", "тоо", "төө",
    # Plural (олон тоо)
    "чууд", "чүүд", "нууд", "нүүд", "үүд", "ууд", "нарт",
}

# Vowel harmony mapping for suffixes
HARMONY_MAP_A_E: Dict[str, Tuple[str, str, str, str]] = {
    "аас": ("аас", "ээс", "оос", "өөс"),
    "ээс": ("аас", "ээс", "оос", "өөс"),
    "оос": ("аас", "ээс", "оос", "өөс"),
    "өөс": ("аас", "ээс", "оос", "өөс"),

    "аар": ("аар", "ээр", "оор", "өөр"),
    "ээр": ("аар", "ээр", "оор", "өөр"),
    "оор": ("аар", "ээр", "оор", "өөр"),
    "өөр": ("аар", "ээр", "оор", "өөр"),

    "аа": ("аа", "ээ", "оо", "өө"),
    "ээ": ("аа", "ээ", "оо", "өө"),
    "оо": ("аа", "ээ", "оо", "өө"),
    "өө": ("аа", "ээ", "оо", "өө"),

    "тай": ("тай", "тэй", "той", "тэй"),
    "тэй": ("тай", "тэй", "той", "тэй"),
    "той": ("тай", "тэй", "той", "тэй"),

    "даа": ("даа", "дээ", "доо", "дөө"),
    "дээ": ("даа", "дээ", "доо", "дөө"),
    "доо": ("даа", "дээ", "доо", "дөө"),
    "дөө": ("даа", "дээ", "доо", "дөө"),

    "чууд": ("чууд", "чүүд", "чууд", "чүүд"),
    "чүүд": ("чууд", "чүүд", "чууд", "чүүд"),
    "ууд": ("ууд", "үүд", "ууд", "үүд"),
    "үүд": ("ууд", "үүд", "ууд", "үүд"),
}


def get_vowel_harmony(stem: str) -> str:
    """
    Determine vowel harmony of a Mongolian stem:
    - 'masculine_a': contains 'а', 'у', 'я', 'ю'
    - 'masculine_o': contains 'о', 'ё' (and no back 'а')
    - 'feminine_e': contains 'э', 'ү', 'е'
    - 'feminine_o': contains 'ө'
    - 'neutral': only contains 'и', 'й' or consonants -> acts as feminine_e
    """
    if not stem or not isinstance(stem, str):
        return "feminine_e"

    stem_lower = stem.lower()
    vowels = [c for c in stem_lower if c in (BACK_VOWELS | FRONT_VOWELS | NEUTRAL_VOWELS)]
    if not vowels:
        return "feminine_e"

    has_a_u = any(v in "ауяю" for v in vowels)
    has_o = any(v in "оё" for v in vowels)
    has_e_u = any(v in "эүе" for v in vowels)
    has_oe = any(v == "ө" for v in vowels)

    if has_a_u:
        return "masculine_a"
    if has_o:
        return "masculine_o"
    if has_oe:
        return "feminine_o"
    if has_e_u:
        return "feminine_e"

    # Only neutral vowels (и, й)
    return "feminine_e"


def harmonize_suffix(stem: str, suffix: str) -> str:
    """
    Harmonize a suffix to match the stem's vowel harmony.
    If the suffix is invariant or harmony doesn't apply, return suffix as-is.
    """
    s_low = suffix.lower()
    if s_low in HARMONY_MAP_A_E:
        a_form, e_form, o_form, oe_form = HARMONY_MAP_A_E[s_low]
        harmony = get_vowel_harmony(stem)
        if harmony == "masculine_a":
            res = a_form
        elif harmony == "masculine_o":
            res = o_form
        elif harmony == "feminine_o":
            res = oe_form
        else:
            res = e_form
        # Match case
        return res if suffix.islower() else res.capitalize()

    # Genitive (ын / ийн)
    if s_low in ("ын", "ийн"):
        harmony = get_vowel_harmony(stem)
        if harmony in ("masculine_a", "masculine_o") and not stem.lower().endswith(("ь", "и")):
            return "ын" if suffix.islower() else "Ын"
        return "ийн" if suffix.islower() else "Ийн"

    # Accusative (ыг / ийг)
    if s_low in ("ыг", "ийг"):
        harmony = get_vowel_harmony(stem)
        if harmony in ("masculine_a", "masculine_o") and not stem.lower().endswith(("ь", "и")):
            return "ыг" if suffix.islower() else "Ыг"
        return "ийг" if suffix.islower() else "Ийг"

    return suffix


# ---------------------------------------------------------------------------
# Morphology & Suffix Attachment
# ---------------------------------------------------------------------------

def attach_separated_suffixes(text: str) -> str:
    """
    Re-attach suffixes that Whisper STT separated with a space.
    Examples:
      - 'Улаанбаатар т' -> 'Улаанбаатарт'
      - 'хүн д' -> 'хүнд'
      - 'гэр ээс' -> 'гэрээс'
      - 'ном ыг' -> 'номыг'
      - 'сургууль аас' -> 'сургуулиас'
    Guarantees that protected standalone words ('дээр', 'дагуу', 'тухай', 'болон', 'юм уу', 'болно уу')
    are NEVER merged!
    """
    if not text or not isinstance(text, str):
        return ""

    tokens = text.split(" ")
    if len(tokens) < 2:
        return text

    new_tokens: List[str] = [tokens[0]]

    for i in range(1, len(tokens)):
        token = tokens[i]
        token_clean = re.sub(r"[^\wа-яёөүА-ЯЁӨҮ]", "", token).lower()
        prev_token = new_tokens[-1]
        prev_clean = re.sub(r"[^\wа-яёөүА-ЯЁӨҮ]", "", prev_token)

        # Do not merge if previous token ends with punctuation (. ! ? etc.)
        prev_has_punct = bool(re.search(r"[.!?,;:…\n)]$", prev_token))

        # Check if the current token is a detached suffix candidate
        is_suffix_candidate = (
            token_clean in DETACHED_SUFFIXES
            and not prev_has_punct
            and len(prev_clean) >= 2
            and re.match(r"^[а-яёөүА-ЯЁӨҮa-zA-Z0-9]+$", prev_clean)
        )

        # Explicitly protect standalone words
        if token_clean in PROTECTED_STANDALONE_WORDS:
            is_suffix_candidate = False

        if is_suffix_candidate:
            # Preserve punctuation on the suffix itself (e.g. 'т.' -> 'т' + '.')
            punct_match = re.search(r"([.!?,;:…)]+)$", token)
            trailing_punct = punct_match.group(1) if punct_match else ""

            # Check if stem is Cyrillic
            is_cyrillic = bool(re.search(r"[а-яёөүА-ЯЁӨҮ]", prev_clean))

            if is_cyrillic:
                # Apply vowel harmony
                harm_suffix = harmonize_suffix(prev_clean, token_clean)
                new_tokens[-1] = prev_token + harm_suffix + trailing_punct
            else:
                # Latin acronym or number (e.g. 'iPhone 15 т' -> 'iPhone 15-т')
                new_tokens[-1] = prev_token + "-" + token_clean + trailing_punct
        else:
            new_tokens.append(token)

    return " ".join(new_tokens)


def normalize_postpositions(text: str) -> str:
    """
    Fixes accidentally merged postpositions and particles, ensuring correct separation:
    - 'ширээндээр' -> 'ширээн дээр'
    - 'хуулиндагуу' -> 'хуулин дагуу'
    - 'төслийнтухай' -> 'төслийн тухай'
    - 'бидболон' -> 'бид болон'
    - 'юмуу' -> 'юм уу'
    - 'болнуу' -> 'болно уу'
    """
    if not text or not isinstance(text, str):
        return ""

    s = text

    # Detach 'дээр' if mistakenly merged after consonant/vowel
    s = re.sub(r"(?i)\b([а-яёөүА-ЯЁӨҮ]{3,})дээр\b", r"\1 дээр", s)

    # Detach 'дагуу' if mistakenly merged
    s = re.sub(r"(?i)\b([а-яёөүА-ЯЁӨҮ]{3,})дагуу\b", r"\1 дагуу", s)

    # Detach 'тухай' if mistakenly merged
    s = re.sub(r"(?i)\b([а-яёөүА-ЯЁӨҮ]{3,})тухай\b", r"\1 тухай", s)

    # Detach 'болон' if mistakenly merged
    s = re.sub(r"(?i)\b([а-яёөүА-ЯЁӨҮ]{3,})болон\b", r"\1 болон", s)

    # Standardize 'юмуу' -> 'юм уу'
    s = re.sub(r"(?i)\bюмуу\b", "юм уу", s)

    # Standardize 'болнуу' -> 'болно уу'
    s = re.sub(r"(?i)\bболнуу\b", "болно уу", s)

    return s


def apply_mongolian_grammar(text: str) -> str:
    """
    Comprehensive Mongolian grammar pipeline:
    1. Postposition normalization (separate 'дээр', 'дагуу', 'тухай', 'болон', 'юм уу', 'болно уу')
    2. Suffix attachment with vowel harmony (e.g. 'Улаанбаатар т' -> 'Улаанбаатарт')
    """
    if not text or not isinstance(text, str):
        return ""

    s = normalize_postpositions(text)
    s = attach_separated_suffixes(s)
    return s


# ---------------------------------------------------------------------------
# Voice Commands & Actions
# ---------------------------------------------------------------------------

def _is_period_noun_context(before_text: str, after_text: str) -> bool:
    """
    Disambiguate spoken 'цэг' (voice command for period) from legitimate noun phrases:
    e.g. 'эхлэх цэг', 'цугларах цэг', 'хяналтын цэг', 'А цэг', 'цэг дээр', 'цэг рүү'
    """
    prev_match = re.search(r"(\w+)\s+$", before_text)
    if prev_match:
        prev_word = prev_match.group(1).lower()
        noun_context = {
            "эхлэх", "цугларах", "хяналтын", "эцсийн", "барианы", "тулгуур",
            "огтлолцлын", "уулзах", "хөдлөх", "очих", "байрлах", "тусах",
            "гол", "эгзэгтэй", "энэ", "тэр", "тухайн", "нэг", "хоёр", "гурван",
            "эхлэл", "төгсгөл", "суурь", "өгөгдлийн", "холболтын", "эргэлтийн",
            "зангилаа", "хүрэх", "хойд", "өмнөд", "зүүн", "баруун", "дээд", "доод",
        }
        if prev_word in noun_context or (len(prev_word) == 1 and prev_word.isalpha()):
            return True

    next_match = re.search(r"^\s+(\w+)", after_text)
    if next_match:
        next_word = next_match.group(1).lower()
        postposition_context = {
            "дээр", "дээрх", "дээрээ", "рүү", "руу", "рүүгээ", "руугаа",
            "хүртэл", "хооронд", "орчим", "нь", "биш", "дээрээс", "тухай",
        }
        if next_word in postposition_context:
            return True

    return False


def process_voice_commands(text: str) -> Tuple[str, Optional[str]]:
    """
    Recognize and execute Mongolian voice commands.
    Returns: (processed_text, action)
    Where action can be:
      - 'undo': triggered by 'сүүлийнхийг арилга' / 'буцаах'
      - None: normal formatted text

    Voice command mapping:
      - 'Шинэ мөр' -> '\\n'
      - 'Шинэ догол' / 'шинэ догол мөр' -> '\\n\\n'
      - 'Цэг' -> '.' (with disambiguation)
      - 'Таслал' -> ','
      - 'Асуултын тэмдэг' -> '?'
      - 'Анхаарлын тэмдэг' -> '!'
      - 'Хаалт нээх' -> '('
      - 'Хаалт хаах' -> ')'
      - 'Сүүлийнхийг арилга' -> One-time Backspace / Undo
    """
    if not text or not isinstance(text, str):
        return "", None

    s = text.strip()
    if not s:
        return "", None

    # Check for standalone 'сүүлийнхийг арилга' / 'буцаах' command
    undo_pattern = r"(?i)^(сүүлийнхийг арилга|сүүлчийнхийг арилга|сүүлийг арилга|сүүлийнхийг устга|буцаах|undo)[.!?]*$"
    if re.match(undo_pattern, s):
        return "", "undo"

    # Check for 'сүүлийнхийг арилга' at the end of utterance:
    # e.g. "өнөөдөр хуралтай сүүлийнхийг арилга" -> removes the preceding word "хуралтай"
    trailing_undo = re.search(
        r"(?i)\s+(сүүлийнхийг арилга|сүүлчийнхийг арилга|сүүлийг арилга|сүүлийнхийг устга)[.!?]*$",
        s
    )
    if trailing_undo:
        # Strip the command
        prefix = s[:trailing_undo.start()].strip()
        # Remove the last word before the command (one backspace/undo effect)
        words = prefix.split(" ")
        if len(words) > 1:
            s = " ".join(words[:-1])
        else:
            s = ""

    # Replace newlines / paragraphs
    s = re.sub(r"(?i)\b(шинэ догол мөр|шинэ догол|догол мөр)\b", "\n\n", s)
    s = re.sub(r"(?i)\b(шинэ мөр|шинэ мөрөөр)\b", "\n", s)

    # Brackets
    s = re.sub(r"(?i)\b(хаалт нээх|хаалт нээ)\b", "(", s)
    s = re.sub(r"(?i)\b(хаалт хаах|хаалт хаа)\b", ")", s)

    # Punctuation commands
    s = re.sub(r"(?i)\b(асуултын тэмдэг)\b", "?", s)
    s = re.sub(r"(?i)\b(анхаарлын тэмдэг)\b", "!", s)
    s = re.sub(r"(?i)\b(давхар цэг|тодорхойлох цэг)\b", ":", s)
    s = re.sub(r"(?i)\b(цэг таслал)\b", ";", s)
    s = re.sub(r"(?i)\b(таслал)\b", ",", s)

    # Disambiguate 'цэг'
    def replace_period(m: re.Match) -> str:
        start, end = m.span()
        before = s[:start]
        after = s[end:]
        if _is_period_noun_context(before, after):
            return m.group(0)
        return "."

    s = re.sub(r"(?i)\bцэг\b", replace_period, s)

    # Clean up spacing around punctuation
    s = re.sub(r"\s+([.,!?:;\)])", r"\1", s)
    s = re.sub(r"([.,!?:;])([^\s\d.,!?:;\"'\)\n])", r"\1 \2", s)
    s = re.sub(r"([\(\"])\s+", r"\1", s)
    s = re.sub(r"(\S)(\()", r"\1 \2", s)

    # Clean space before/after newlines
    s = re.sub(r"[ ]*\n[ ]*", "\n", s)

    if s.strip() == text.strip():
        return text, None

    return capitalize_sentences(s.strip()), None


def capitalize_sentences(text: str) -> str:
    """Capitalize first letter of each sentence and newline."""
    if not text or not isinstance(text, str):
        return ""
    s = re.sub(
        r"(^|[\r\n\t]+)([\s\"'“”«»\(\[\{]*)([a-zA-Zа-яёөүА-ЯЁӨҮ])",
        lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
        text,
    )
    s = re.sub(
        r"([.!?…]+[\"')”»\]\}]*\s+)([a-zA-Zа-яёөүА-ЯЁӨҮ])",
        lambda m: m.group(1) + m.group(2).upper(),
        s,
    )
    return s


# ---------------------------------------------------------------------------
# Custom Vocabulary / Whisper Prompt Builder
# ---------------------------------------------------------------------------

def build_whisper_initial_prompt(vocabulary: List[str], max_chars: int = 350) -> str:
    """
    Constructs a clean, deduplicated initial prompt from custom vocabulary for Whisper.
    Strictly stays within max_chars to avoid overflowing Whisper's prompt context limit.
    """
    if not vocabulary or not isinstance(vocabulary, list):
        return ""

    cleaned_words: List[str] = []
    seen: Set[str] = set()

    for item in vocabulary:
        if isinstance(item, str):
            w = item.strip()
            w_low = w.lower()
            if w and 2 <= len(w) <= 64 and w_low not in seen:
                seen.add(w_low)
                cleaned_words.append(w)

    prompt_parts: List[str] = []
    cur_len = 0

    for w in cleaned_words:
        needed = len(w) + (2 if prompt_parts else 0)
        if cur_len + needed > max_chars:
            break
        prompt_parts.append(w)
        cur_len += needed

    return ", ".join(prompt_parts)
