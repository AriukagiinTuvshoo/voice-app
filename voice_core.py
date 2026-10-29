"""
VOICE Desktop - Core Logic Module (Pure Python, Zero External C-Dependencies)
Contains validated business logic, setting sanitizers, geometry math, and status helpers.
Importable in headless CI environments (Windows, Linux, macOS).
"""
import os
import re
import time
from typing import Any, Optional, Tuple, Dict, Set

# Version
CORE_VERSION = "1.2.6"

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

    # Ensure target path strictly starts with base directory path
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
    Check if a window rectangle (x, y, w, h) substantially intersects a screen bounds (left, top, right, bottom).
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
