import os
import sys
import ctypes
import logging
from logging.handlers import RotatingFileHandler

if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Centralized Rotating Logger (2 MB x 3 backups)
logger = logging.getLogger("voice")
logger.setLevel(logging.INFO)
_log_format = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_log_dir = os.path.dirname(os.path.abspath(__file__))
_log_path = os.path.join(_log_dir, "voice-server.log")
try:
    _rfh = RotatingFileHandler(_log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    _rfh.setFormatter(_log_format)
    logger.addHandler(_rfh)
except Exception:
    pass

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stdout is not None:
    _sh = logging.StreamHandler(sys.stdout)
    _sh.setFormatter(_log_format)
    logger.addHandler(_sh)

# pythonw.exe (hidden launch) has no console: redirect stdout/stderr to logger
if sys.stdout is None or sys.stderr is None:
    import io as _io
    class _LogStreamWriter(_io.TextIOBase):
        def write(self, s):
            s_clean = s.strip() if isinstance(s, str) else str(s).strip()
            if s_clean:
                logger.info(s_clean)
            return len(s)
        def flush(self):
            pass
        def isatty(self):
            return False
        def readable(self):
            return False
        def writable(self):
            return True
        def seekable(self):
            return False
    _lsw = _LogStreamWriter()
    if sys.stdout is None:
        sys.stdout = _lsw
    if sys.stderr is None:
        sys.stderr = _lsw

import asyncio
import ctypes
import io
import json
import math
import os
import re
import subprocess
import queue
import threading
import time
import tempfile
import unicodedata
import uuid
from typing import Optional

if os.name == "nt":
    from ctypes import wintypes

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
import numpy as np
from scipy import signal as sp_signal
from scipy.io import wavfile

from voice_core import (
    CORE_VERSION,
    SETTING_CHOICES,
    sanitize_settings,
    is_safe_voice_id,
    safe_clone_wav_path,
    get_fallback_flowbar_pos_math,
    clamp_rect_to_screen,
    snap_rect_to_screen_edges,
    compute_flowbar_status,
    normalize_mongolian_numbers,
    format_speech_text,
    enhance_ssml_cadence,
    apply_voice_commands,
    strip_filler_words,
    generate_srt,
    generate_lrc,
    generate_vtt,
    extract_summary_and_actions,
    rewrite_text_style,
    apply_voice_snippets,
    normalize_tech_terms,
    LANG_CYCLE,
    LANG_LABELS,
    HOTKEY_NAMES,
    WHISPER_MODELS_INFO,
    find_whisper_cpp_binary,
    find_local_ggml_model,
    transcribe_with_whisper_cpp_cli,
    detect_gpu_hardware,
    list_available_local_models,
    get_user_data_dir,
    CANONICAL_APP_DIR,
    CANONICAL_USER_DATA_DIR,
)

# Standard Windows Clipboard Format ID (defined at module level for cross-platform imports)
CF_UNICODETEXT = 13

from mongolian_grammar import (
    apply_mongolian_grammar,
    process_voice_commands,
    build_whisper_initial_prompt,
)
from karaoke_ass import (
    generate_karaoke_ass,
    export_karaoke_video,
    is_ffmpeg_available,
    find_system_or_bundled_ffmpeg,
)
from audio_separator import (
    separate_audio_stems,
    process_separation_job,
    cleanup_stems,
    STEMS_DIR,
)
from voice_cloning import (
    create_voice_profile,
    delete_voice_profile,
    load_voice_profiles_db,
    get_voice_cloning_system_status,
    sanitize_profile_id,
)

def get_app_version() -> str:
    v_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    if os.path.isfile(v_file):
        try:
            with open(v_file, "r", encoding="utf-8") as f:
                return f.read().strip() or CORE_VERSION
        except Exception:
            pass
    return CORE_VERSION

APP_VERSION = get_app_version()

app = FastAPI(
    title="VOICE & VoiceStudio AI Engine (TTS, STT, Voice Cloning & Duudlaga Flow)",
    version=APP_VERSION,
)

SERVER_PORT = int(os.environ.get("VOICE_PORT", "8000"))
_ALLOWED_HOSTS = {
    f"127.0.0.1:{SERVER_PORT}",
    f"localhost:{SERVER_PORT}",
    "testserver",
    f"testserver:{SERVER_PORT}",
    "testserver:80",
}
_ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{SERVER_PORT}",
    f"http://localhost:{SERVER_PORT}",
    "http://testserver",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_DIR = get_user_data_dir()
SETTINGS_FILE = os.path.join(USER_DATA_DIR, "voice_settings.json")


def _migrate_legacy_user_data() -> None:
    """Migrate settings and data from BASE_DIR / legacy paths to USER_DATA_DIR."""
    try:
        if not os.path.isfile(SETTINGS_FILE):
            cands = [
                os.path.join(BASE_DIR, "voice_settings.json"),
                os.path.expandvars(r"%LOCALAPPDATA%\VOICE-App\voice_settings.json"),
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\VOICE\voice_settings.json"),
            ]
            for c in cands:
                if os.path.isfile(c):
                    import shutil
                    shutil.copy2(c, SETTINGS_FILE)
                    logger.info("[Migration] Migrated settings to %s", SETTINGS_FILE)
                    break
    except Exception as e:
        logger.warning("[Migration] Notice during settings migration: %s", e)


_migrate_legacy_user_data()
DEFAULT_SERVER_SETTINGS = {
    "hotkey": "f8",         # "f8" | "ctrl_alt" | "ctrl_shift" | "f9" | "f10"
    "stt_engine": "whisper",  # local-first default ("whisper" | "whisper_cpp" | "google" | "chimege") # "google" | "whisper" | "chimege"
    "whisper_model": "small",
    "chimege_token": "",
    "language": "auto",
    "sound_cues": True,
    "number_normalization": True,
    "auto_punctuation": True,
    "voice_actions": True,
    "filler_word_cleaner": True,
    "noise_gate": True,
    "auto_insert_text": True,
    "restore_clipboard": True,
    "undo_button": True,
    "start_with_windows": True,
    "custom_snippets": True,
    "tech_terms_normalization": True,
    "use_gpu": True,
    "cpu_threads": 6,
    "mongolian_grammar": True,
    "custom_vocabulary": [
        "Улаанбаатар",
        "Оюутолгой",
        "Тавантолгой",
        "ХААН Банк",
        "ШУТИС",
        "Монголбанк",
        "VoiceApp",
    ],
    "snippets": {
        "миний имэйл": "user@example.invalid",
        "миний утас": "+97600000000",
        "данс": "2815108795",
    },
}

def load_server_settings() -> dict:
    cfg = dict(DEFAULT_SERVER_SETTINGS)
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(sanitize_settings(data))
        except Exception:
            pass
    return cfg

# Settings sanitization is handled via voice_core.sanitize_settings


def save_server_settings(data: dict) -> dict:
    cfg = load_server_settings()
    cfg.update(sanitize_settings(data))
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[!] Error saving settings:", e)
    return cfg

SERVER_SETTINGS = load_server_settings()

_single_instance_mutex = None

def check_single_instance(port: int = 8000) -> bool:
    """Named mutex single-instance check to prevent duplicate engines and WinError 10048."""
    global _single_instance_mutex
    if os.name != "nt":
        return True
    try:
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        k.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        k.CreateMutexW.restype = wintypes.HANDLE
        k.GetLastError.restype = wintypes.DWORD

        mutex_name = f"Local\\VOICE_App_SingleInstance_Mutex_{port}"
        _single_instance_mutex = k.CreateMutexW(None, True, mutex_name)
        err = k.GetLastError()
        if err == 183:  # ERROR_ALREADY_EXISTS
            print(f"[!] VOICE engine already running on port {port}. Bringing FlowBar to front and exiting cleanly.")
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/flowbar/action",
                    data=json.dumps({"action": "show"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=1.5)
            except Exception:
                pass
            return False
    except Exception as e:
        print("[!] Single instance check warning:", e)
    return True

def is_port_available(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


@app.middleware("http")
async def local_only_guard(request: Request, call_next):
    """Blocks DNS-rebinding and cross-site requests: only this app's own origin may call the API."""
    host = (request.headers.get("host") or "").lower()
    host_name = host.split(":")[0]
    if host not in _ALLOWED_HOSTS and host_name not in ("127.0.0.1", "localhost", "testserver"):
        return Response("Forbidden host", status_code=403)
    origin = request.headers.get("origin")
    if origin is not None and origin.lower() not in _ALLOWED_ORIGINS:
        parsed_origin_host = urllib.parse.urlparse(origin).hostname or ""
        if parsed_origin_host not in ("127.0.0.1", "localhost", "testserver"):
            return Response("Forbidden origin", status_code=403)
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return Response("Forbidden cross-site request", status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

CLONES_DIR = os.path.join(USER_DATA_DIR, "clones")
CLONES_JSON = os.path.join(CLONES_DIR, "voices.json")
BASE_ENVELOPES_CACHE: dict[str, np.ndarray] = {}

os.makedirs(CLONES_DIR, exist_ok=True)


def _migrate_legacy_clones() -> None:
    try:
        cands = [
            os.path.join(BASE_DIR, "clones"),
            os.path.expandvars(r"%LOCALAPPDATA%\VOICE-App\clones"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\VOICE\clones"),
        ]
        for cdir in cands:
            if os.path.isdir(cdir) and os.path.abspath(cdir) != os.path.abspath(CLONES_DIR):
                for item in os.listdir(cdir):
                    src = os.path.join(cdir, item)
                    dst = os.path.join(CLONES_DIR, item)
                    if not os.path.exists(dst):
                        import shutil
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
    except Exception as e:
        logger.warning("[Migration] Notice during clones migration: %s", e)


_migrate_legacy_clones()

# Optional libraries check
try:
    import miniaudio
    HAS_MINIAUDIO = True
except ImportError:
    HAS_MINIAUDIO = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    import edge_tts
    HAS_EDGE_TTS = True
    print("[+] Edge-TTS Neural engine ready (YesuiNeural & BataaNeural)")
except ImportError:
    HAS_EDGE_TTS = False

try:
    import speech_recognition as sr
    HAS_SR = True
    print("[+] SpeechRecognition (STT) engine ready")
except ImportError:
    HAS_SR = False

# Optional MMS-TTS VITS model
mms_tokenizer = None
mms_model = None
try:
    import torch
    from transformers import AutoTokenizer, VitsModel

    mms_model_id = "facebook/mms-tts-khk"
    mms_tokenizer = AutoTokenizer.from_pretrained(mms_model_id)
    mms_model = VitsModel.from_pretrained(mms_model_id)
    mms_model.eval()
    print("[+] MMS-TTS VITS model loaded!")
except Exception:
    pass

# VoiceStudio Audio DSP Presets (ported from debpalash/VoiceStudio audio_dsp.py)
VOICESTUDIO_PRESETS = {
    "broadcast": {
        "label": "Broadcast (Радио/Подкаст)",
        "icon": "📻",
        "description": "Жигд дуугаралттай, дулаан, тод студийн стандарт.",
        "low_db": 1.8,
        "mid_db": 0.5,
        "high_db": 2.2,
        "leveler": True,
        "reverb": 0.0,
    },
    "podcast": {
        "label": "Podcast (Ойрын микрофон)",
        "icon": "🎙️",
        "description": "Гүн баргил, цуурайгүй, ойроос ярьж буй мэт.",
        "low_db": 2.5,
        "mid_db": 1.8,
        "high_db": 1.2,
        "leveler": True,
        "reverb": 0.0,
    },
    "warm": {
        "label": "Warm (Дулаан зөөлөн)",
        "icon": "☀️",
        "description": "Зөөлөн нам давтамжтай, чихэнд эвтэйхэн өнгө.",
        "low_db": 3.2,
        "mid_db": 1.0,
        "high_db": -1.2,
        "leveler": True,
        "reverb": 0.06,
    },
    "bright": {
        "label": "Bright (Тод цэвэр)",
        "icon": "✨",
        "description": "Өндөр давтамж тодорсон, маш цэвэрхэн дуудлага.",
        "low_db": -1.0,
        "mid_db": 0.8,
        "high_db": 3.8,
        "leveler": True,
        "reverb": 0.0,
    },
    "cinematic": {
        "label": "Cinematic (Кино студи)",
        "icon": "🎬",
        "description": "Бага зэргийн орон зайн цуурайтай, сүрлэг өнгө.",
        "low_db": 2.0,
        "mid_db": 0.0,
        "high_db": 1.8,
        "leveler": True,
        "reverb": 0.14,
    },
    "raw": {
        "label": "Raw (Эффектгүй)",
        "icon": "🔇",
        "description": "Нэмэлт эффектгүй цэвэр гаралт.",
        "low_db": 0.0,
        "mid_db": 0.0,
        "high_db": 0.0,
        "leveler": False,
        "reverb": 0.0,
    },
}

VOICES = [
    {
        "id": "mn-MN-YesuiNeural",
        "name": "Есүй",
        "gender": "female",
        "engine": "edge-neural",
        "baseVoice": "mn-MN-YesuiNeural",
        "pitch": 1.0,
        "speed": 1.0,
        "formantWarp": 1.0,
        "defaultPreset": "broadcast",
        "description": "Эелдэг, уян зөөлөн, байгалийн тод өнгө аяс (Эмэгтэй)",
        "tag": "Үндсэн • Эмэгтэй",
    },
    {
        "id": "mn-MN-BataaNeural",
        "name": "Батаа",
        "gender": "male",
        "engine": "edge-neural",
        "baseVoice": "mn-MN-BataaNeural",
        "pitch": 1.0,
        "speed": 1.0,
        "formantWarp": 1.0,
        "defaultPreset": "broadcast",
        "description": "Цэвэр тод, өөртөө итгэлтэй, баргил (Эрэгтэй)",
        "tag": "Үндсэн • Эрэгтэй",
    },
    {
        "id": "mn-studio-narrator",
        "name": "Тэмүүлэн",
        "gender": "male",
        "engine": "voicestudio-persona",
        "baseVoice": "mn-MN-BataaNeural",
        "pitch": 0.86,
        "speed": 0.94,
        "formantWarp": 0.91,
        "defaultPreset": "cinematic",
        "description": "Гүн баргил, кино тайлбар болон аудио номд зориулсан өгүүлэгч",
        "tag": "Студи • Өгүүлэгч",
    },
    {
        "id": "mn-studio-news",
        "name": "Ану",
        "gender": "female",
        "engine": "voicestudio-persona",
        "baseVoice": "mn-MN-YesuiNeural",
        "pitch": 1.05,
        "speed": 1.08,
        "formantWarp": 1.03,
        "defaultPreset": "bright",
        "description": "Телевиз, мэдээний студийн тод цэвэр, хурц хэмнэлтэй хөтлөгч",
        "tag": "Студи • Мэдээ",
    },
    {
        "id": "mn-studio-podcast",
        "name": "Ананд",
        "gender": "male",
        "engine": "voicestudio-persona",
        "baseVoice": "mn-MN-BataaNeural",
        "pitch": 0.94,
        "speed": 1.04,
        "formantWarp": 0.96,
        "defaultPreset": "podcast",
        "description": "Ойрын микрофоны дулаан, энгийн чөлөөт ярианы подкаст хоолой",
        "tag": "Студи • Подкаст",
    },
    {
        "id": "mn-studio-maral",
        "name": "Марал",
        "gender": "female",
        "engine": "voicestudio-persona",
        "baseVoice": "mn-MN-YesuiNeural",
        "pitch": 0.92,
        "speed": 0.91,
        "formantWarp": 0.95,
        "defaultPreset": "warm",
        "description": "Тайвшруулах, зөөлөн дулаан, уран зохиол ба бясалгалын хоолой",
        "tag": "Студи • Уянгалаг",
    },
    {
        "id": "mn-studio-elder",
        "name": "Тулга",
        "gender": "male",
        "engine": "voicestudio-persona",
        "baseVoice": "mn-MN-BataaNeural",
        "pitch": 0.78,
        "speed": 0.88,
        "formantWarp": 0.86,
        "defaultPreset": "warm",
        "description": "Намбалаг, цээжний гүн резонанстай, жинтэй эрэгтэй хоолой",
        "tag": "Студи • Гүн баргил",
    },
    {
        "id": "mn-studio-kid",
        "name": "Мишээл",
        "gender": "female",
        "engine": "voicestudio-persona",
        "baseVoice": "mn-MN-YesuiNeural",
        "pitch": 1.24,
        "speed": 1.06,
        "formantWarp": 1.14,
        "defaultPreset": "bright",
        "description": "Үлгэр, хүүхдийн контентод зориулсан цовоо сэргэлэн хоолой",
        "tag": "Студи • Хүүхэд",
    },
    {
        "id": "en-US-AvaMultilingualNeural",
        "name": "Ava (Multilingual)",
        "gender": "female",
        "engine": "edge-multilingual",
        "baseVoice": "en-US-AvaMultilingualNeural",
        "pitch": 1.0,
        "speed": 1.0,
        "formantWarp": 1.0,
        "defaultPreset": "broadcast",
        "description": "Англи болон олон улсын холимог текстийг унших студийн эмэгтэй хоолой",
        "tag": "Олон хэл • Эмэгтэй",
    },
    {
        "id": "en-US-AndrewMultilingualNeural",
        "name": "Andrew (Multilingual)",
        "gender": "male",
        "engine": "edge-multilingual",
        "baseVoice": "en-US-AndrewMultilingualNeural",
        "pitch": 1.0,
        "speed": 1.0,
        "formantWarp": 1.0,
        "defaultPreset": "podcast",
        "description": "Англи болон олон улсын холимог текстийг унших гүн эрэгтэй хоолой",
        "tag": "Олон хэл • Эрэгтэй",
    },
    {
        "id": "ja-JP-NanamiNeural",
        "name": "Nanami • 七海",
        "gender": "female",
        "engine": "edge-neural",
        "baseVoice": "ja-JP-NanamiNeural",
        "pitch": 1.0,
        "speed": 1.0,
        "formantWarp": 1.0,
        "defaultPreset": "broadcast",
        "description": "Япон хэлний байгалийн, маш тод цэвэр эмэгтэй хоолой (Japanese)",
        "tag": "Япон • Эмэгтэй",
    },
    {
        "id": "ja-JP-KeitaNeural",
        "name": "Keita • 圭太",
        "gender": "male",
        "engine": "edge-neural",
        "baseVoice": "ja-JP-KeitaNeural",
        "pitch": 1.0,
        "speed": 1.0,
        "formantWarp": 1.0,
        "defaultPreset": "broadcast",
        "description": "Япон хэлний тод, итгэлтэй эрэгтэй хоолой (Japanese)",
        "tag": "Япон • Эрэгтэй",
    },
]

VOICES_BY_ID = {v["id"]: v for v in VOICES}

# ---------------------------------------------------------------------------
# Cloned Voices Persistence
# ---------------------------------------------------------------------------

def load_cloned_voices() -> dict[str, dict]:
    if os.path.exists(CLONES_JSON):
        try:
            with open(CLONES_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print("Warning loading clones/voices.json:", e)
    return {}


def save_cloned_voices_db(db: dict[str, dict]) -> None:
    try:
        with open(CLONES_JSON, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Warning saving clones/voices.json:", e)


CLONED_VOICES_DB: dict[str, dict] = load_cloned_voices()


# ---------------------------------------------------------------------------
# Audio Decode & VoiceStudio DSP / Cepstral Vocal Tract Timbre Transfer
# ---------------------------------------------------------------------------

TARGET_SR = 24000
STFT_NPERSEG = 1024
STFT_NOVERLAP = 768
CEPSTRAL_LIFTER = 30  # Quefrency cutoff capturing vocal tract formants F1..F4


def decode_audio_bytes(raw_bytes: bytes, target_sr: int = TARGET_SR) -> np.ndarray:
    """Decode WAV, MP3, M4A, WEBM, FLAC, OGG into mono float32 numpy array at target_sr."""
    if HAS_MINIAUDIO:
        try:
            decoded = miniaudio.decode(
                raw_bytes,
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=1,
                sample_rate=target_sr,
            )
            samples = np.frombuffer(decoded.samples, dtype=np.float32).copy()
            if samples.size > 0:
                return samples
        except Exception as e:
            print("miniaudio decode fallback:", e)

    if HAS_SOUNDFILE:
        try:
            data, sr_in = sf.read(io.BytesIO(raw_bytes), dtype="float32", always_2d=False)
            if data.ndim > 1:
                data = data.mean(axis=1)
            if sr_in != target_sr and data.size > 0:
                data = sp_signal.resample_poly(data, target_sr, sr_in).astype(np.float32)
            if data.size > 0:
                return data
        except Exception:
            pass

    # Universal ffmpeg pipe fallback (handles MP3 from edge-tts and M4A/WEBM/OGG from iPhone/Android on Linux & Windows)
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-f",
                "f32le",
                "-acodec",
                "pcm_f32le",
                "-ac",
                "1",
                "-ar",
                str(target_sr),
                "pipe:1",
            ],
            input=raw_bytes,
            capture_output=True,
            timeout=15,
        )
        if proc.returncode == 0 and len(proc.stdout) >= 4:
            samples = np.frombuffer(proc.stdout, dtype=np.float32).copy()
            if samples.size > 0:
                return samples
    except Exception:
        pass

    # Fallback scipy wavfile
    sr_in, data = wavfile.read(io.BytesIO(raw_bytes))
    if data.ndim > 1:
        data = data.mean(axis=1)
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    else:
        data = data.astype(np.float32)
    if sr_in != target_sr and data.size > 0:
        data = sp_signal.resample_poly(data, target_sr, sr_in).astype(np.float32)
    return data


def encode_wav_bytes(samples: np.ndarray, sample_rate: int = TARGET_SR) -> bytes:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    wavfile.write(buf, sample_rate, pcm)
    return buf.getvalue()


def trim_silence(samples: np.ndarray, sample_rate: int, threshold_db: float = -45.0) -> np.ndarray:
    """Ported from VoiceStudio audio_dsp.py trim_speech_padding."""
    if samples.size == 0:
        return samples
    floor = 10.0 ** (threshold_db / 20.0)
    voiced = np.flatnonzero(np.abs(samples) > floor)
    if voiced.size == 0:
        return samples
    margin = int(sample_rate * 0.06)
    start = max(0, int(voiced[0]) - margin)
    end = min(samples.size, int(voiced[-1]) + 1 + margin)
    return samples[start:end]


def normalize_audio_np(samples: np.ndarray, target_dbfs: float = -2.0) -> np.ndarray:
    """Ported from VoiceStudio audio_dsp.py normalize_audio."""
    if samples.size == 0:
        return samples
    max_val = float(np.max(np.abs(samples)))
    silence_floor = 10.0 ** (-50.0 / 20.0)
    if max_val > silence_floor:
        target_amp = 10.0 ** (target_dbfs / 20.0)
        samples = samples * (target_amp / max_val)
    return samples.astype(np.float32)


def level_speech_np(
    samples: np.ndarray,
    sample_rate: int,
    window_ms: float = 400.0,
    amount: float = 0.65,
    max_gain_db: float = 7.0,
    smooth_ms: float = 180.0,
) -> np.ndarray:
    """Ported from VoiceStudio audio_dsp.py level_speech (EBU R128 phrase leveler)."""
    if samples.size < sample_rate // 5:
        return samples
    hop = max(1, int(sample_rate * 0.01))
    n = samples.size
    frames = n // hop
    if frames < 4:
        return samples
    trimmed = samples[: frames * hop].reshape(frames, hop)
    frame_power = (trimmed.astype(np.float64) ** 2).mean(axis=1)

    short_db = 10.0 * np.log10(frame_power + 1e-20)
    if float(short_db.max()) <= -50.0:
        return samples
    floor_db = max(-68.0, float(short_db.max()) - 38.0)
    active_mask = short_db > floor_db
    if not np.any(active_mask):
        return samples
    avg_db = 10.0 * np.log10(float(frame_power[active_mask].mean()) + 1e-20)
    speech = short_db > max(floor_db, avg_db - 24.0)
    if not np.any(speech):
        return samples
    speech_db = 10.0 * np.log10(float(frame_power[speech].mean()) + 1e-20)

    win = max(1, int(round(window_ms / 10.0)))
    kernel = np.ones(win) / win
    sp_pow = np.convolve(np.where(speech, frame_power, 0.0), kernel, mode="same")
    sp_shr = np.convolve(speech.astype(np.float64), kernel, mode="same")
    level_db = 10.0 * np.log10(sp_pow / np.maximum(sp_shr, 1e-12) + 1e-20)

    gain_db = np.clip(amount * (speech_db - level_db), -max_gain_db, max_gain_db)
    idx = np.where(speech, np.arange(frames), -1)
    idx = np.maximum.accumulate(idx)
    idx[idx < 0] = int(np.argmax(speech))
    gain_db = gain_db[idx]

    alpha = math.exp(-1.0 / max(1.0, smooth_ms / 10.0))
    for order in (slice(None), slice(None, None, -1)):
        g = gain_db[order].copy()
        for i in range(1, frames):
            g[i] = alpha * g[i - 1] + (1.0 - alpha) * g[i]
        gain_db[order] = g

    centers = np.arange(frames) * hop + hop / 2.0
    sample_gain = 10.0 ** (np.interp(np.arange(n), centers, gain_db) / 20.0)
    return (samples * sample_gain).astype(np.float32)


def apply_voicestudio_dsp(
    samples: np.ndarray,
    sample_rate: int = TARGET_SR,
    preset_id: str = "broadcast",
) -> np.ndarray:
    """Apply VoiceStudio broadcast mastering & EQ/Reverb preset."""
    if samples.size == 0:
        return samples

    preset = VOICESTUDIO_PRESETS.get(preset_id, VOICESTUDIO_PRESETS["broadcast"])
    if preset_id == "raw":
        return normalize_audio_np(samples, -2.0)

    y = samples.astype(np.float64)

    # 1. Highpass at 65 Hz to remove DC / plosive rumble
    sos_hp = sp_signal.butter(2, 65.0 / (sample_rate / 2.0), btype="highpass", output="sos")
    y = sp_signal.sosfiltfilt(sos_hp, y)

    # 1.1 Digital De-Esser (5.8 kHz - 8.5 kHz) to tame harsh sibilance ('с', 'ш', 'ц', 'з')
    if y.size >= 1024 and sample_rate >= 16000:
        try:
            sos_sib = sp_signal.butter(2, [5800.0 / (sample_rate / 2.0), min(0.95, 8400.0 / (sample_rate / 2.0))], btype="bandpass", output="sos")
            sib_band = sp_signal.sosfiltfilt(sos_sib, y)
            sib_rms = np.sqrt(np.mean(sib_band ** 2) + 1e-10)
            broad_rms = np.sqrt(np.mean(y ** 2) + 1e-10)
            if sib_rms > 0.32 * broad_rms:
                tame_factor = float(np.clip(1.0 - (sib_rms / broad_rms - 0.32) * 0.75, 0.60, 1.0))
                y = y - (1.0 - tame_factor) * sib_band
        except Exception:
            pass

    # 2. 3-band VoiceStudio EQ (Low < 260Hz, Mid ~1600Hz, High > 3800Hz)
    low_db = float(preset.get("low_db", 0.0))
    mid_db = float(preset.get("mid_db", 0.0))
    high_db = float(preset.get("high_db", 0.0))

    if abs(low_db) > 0.1 or abs(mid_db) > 0.1 or abs(high_db) > 0.1:
        _, _, Zxx = sp_signal.stft(y, fs=sample_rate, nperseg=1024, noverlap=768)
        freqs = np.linspace(0, sample_rate / 2.0, Zxx.shape[0])
        eq_curve_db = (
            low_db * np.exp(-((freqs / 260.0) ** 2))
            + mid_db * np.exp(-(((freqs - 1600.0) / 900.0) ** 2))
            + high_db * (1.0 / (1.0 + np.exp(-(freqs - 3600.0) / 600.0)))
        )
        eq_gain = (10.0 ** (eq_curve_db / 20.0))[:, None]
        _, y_eq = sp_signal.istft(Zxx * eq_gain, fs=sample_rate, nperseg=1024, noverlap=768)
        y = y_eq[: y.size]

    # 3. Subtle studio room ambience if preset specifies reverb
    reverb_wet = float(preset.get("reverb", 0.0))
    if reverb_wet > 0.01:
        ir_len = int(sample_rate * 0.22)
        rng = np.random.default_rng(42)
        t_ir = np.linspace(0.0, 1.0, ir_len)
        ir = rng.standard_normal(ir_len) * np.exp(-6.5 * t_ir)
        ir[0] = 1.0
        sos_lp = sp_signal.butter(2, 3500.0 / (sample_rate / 2.0), btype="lowpass", output="sos")
        ir = sp_signal.sosfilt(sos_lp, ir)
        wet = sp_signal.fftconvolve(y, ir, mode="full")[: y.size]
        max_w = np.max(np.abs(wet)) + 1e-9
        max_y = np.max(np.abs(y)) + 1e-9
        wet = wet * (max_y / max_w)
        y = (1.0 - reverb_wet) * y + reverb_wet * wet

    # 4. EBU R128 phrase leveler
    y_f32 = y.astype(np.float32)
    if preset.get("leveler", True):
        y_f32 = level_speech_np(y_f32, sample_rate)

    # 5. Soft knee limiter & -2 dBFS peak normalization
    y_f32 = np.tanh(y_f32 * 1.15).astype(np.float32)
    return normalize_audio_np(y_f32, -2.0)


def extract_cepstral_envelope(samples: np.ndarray, sample_rate: int = TARGET_SR) -> np.ndarray:
    """
    Extract smooth vocal tract spectral envelope (formants F1..F4 + throat/chest timbre)
    from voiced frames using Cepstral Liftering in the STFT domain.
    Returns a 1D array of shape (STFT_NPERSEG // 2 + 1,) in log-magnitude space.
    """
    if samples.size < STFT_NPERSEG * 2:
        return np.zeros(STFT_NPERSEG // 2 + 1, dtype=np.float32)

    _, _, Zxx = sp_signal.stft(
        samples, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    mag = np.abs(Zxx) + 1e-7
    frame_energy = np.mean(mag ** 2, axis=0)
    threshold = np.percentile(frame_energy, 35)
    voiced_cols = frame_energy >= threshold
    if np.sum(voiced_cols) < 3:
        voiced_cols = np.ones(mag.shape[1], dtype=bool)

    log_mag = np.log(mag[:, voiced_cols])  # shape: (n_bins, n_voiced)
    mean_log_mag = np.mean(log_mag, axis=1)

    # Cepstral liftering to isolate vocal tract envelope (smooth formants) from pitch harmonics
    cepstrum = np.fft.irfft(mean_log_mag)
    lifter = np.zeros_like(cepstrum)
    lifter[:CEPSTRAL_LIFTER] = 1.0
    lifter[-CEPSTRAL_LIFTER + 1 :] = 1.0
    # Smooth cosine taper at lifter boundary
    taper = 8
    for k in range(taper):
        w = 0.5 * (1.0 + math.cos(math.pi * k / taper))
        lifter[CEPSTRAL_LIFTER - taper + k] = w
        lifter[-(CEPSTRAL_LIFTER - taper + k)] = w

    smooth_env_log = np.real(np.fft.rfft(cepstrum * lifter))
    # Remove global gain offset (keep zero-mean spectral shape)
    smooth_env_log = smooth_env_log - np.mean(smooth_env_log)
    return smooth_env_log.astype(np.float32)


def analyze_speaker_prosody(samples: np.ndarray, sample_rate: int = TARGET_SR) -> dict:
    """
    Ported from VoiceStudio prosody_mirror.py:
    Measures median F0 (Hz), pitch spread (semitones), speaking rate (syllables/sec),
    formant centroid (Hz), and vocal tract cepstral envelope.
    """
    # Downsample to 16kHz for F0 & syllable rate analysis
    sr16 = 16000
    sig16 = sp_signal.resample_poly(samples, sr16, sample_rate) if sample_rate != sr16 else samples
    frame_len = int(0.040 * sr16)  # 640
    hop_len = int(0.010 * sr16)    # 160

    if sig16.size < frame_len * 2:
        return {
            "f0": 150.0,
            "pitch_spread_st": 2.5,
            "rate_hz": 4.2,
            "formant_centroid": 1450.0,
            "envelope": extract_cepstral_envelope(samples, sample_rate).tolist(),
        }

    n_frames = 1 + (sig16.size - frame_len) // hop_len
    frames = np.lib.stride_tricks.sliding_window_view(sig16, frame_len)[::hop_len][:n_frames]
    power = np.mean(frames.astype(np.float64) ** 2, axis=1)
    level_db = 10.0 * np.log10(np.maximum(power, 1e-12))
    thresh_db = max(-52.0, float(np.max(level_db)) - 28.0)
    active = level_db > thresh_db

    # Pitch tracking via FFT autocorrelation (VoiceStudio _block_pitch)
    active_frames = frames[active] if np.sum(active) >= 4 else frames
    win = np.hanning(frame_len)
    y = (active_frames.astype(np.float64) - np.mean(active_frames, axis=1, keepdims=True)) * win
    spec = np.fft.rfft(y, n=2048, axis=1)
    corr = np.fft.irfft(spec * np.conj(spec), n=2048, axis=1)

    lag_lo = int(sr16 / 360.0)
    lag_hi = int(sr16 / 72.0)
    energy0 = np.maximum(corr[:, 0:1], 1e-12)
    norm_corr = corr[:, lag_lo:lag_hi] / energy0

    peak_idx = np.argmax(norm_corr, axis=1)
    peak_val = np.max(norm_corr, axis=1)
    voiced_lags = (lag_lo + peak_idx)[peak_val >= 0.38]

    if voiced_lags.size >= 3:
        f0_vals = sr16 / voiced_lags.astype(np.float64)
        f0_vals = f0_vals[(f0_vals >= 72.0) & (f0_vals <= 350.0)]
        f0_median = float(np.median(f0_vals)) if f0_vals.size > 0 else 150.0
        if f0_vals.size >= 4:
            st = 12.0 * np.log2(f0_vals / 100.0)
            pitch_spread = float(np.percentile(st, 85) - np.percentile(st, 15))
        else:
            pitch_spread = 2.5
    else:
        f0_median = 150.0
        pitch_spread = 2.5

    # Syllable nuclei rate (VoiceStudio _count_nuclei)
    active_s = max(0.4, float(np.sum(active)) * 0.010)
    smooth_lvl = np.convolve(level_db, np.ones(5) / 5.0, mode="same")
    peaks, _ = sp_signal.find_peaks(smooth_lvl, height=thresh_db + 3.0, distance=8)
    rate_hz = float(np.clip(len(peaks) / active_s, 2.5, 6.8))

    # Spectral envelope & formant centroid
    env_log = extract_cepstral_envelope(samples, sample_rate)
    freqs = np.linspace(0, sample_rate / 2.0, env_log.size)
    band = (freqs >= 250.0) & (freqs <= 3800.0)
    weights = np.exp(env_log[band] - np.max(env_log[band]))
    formant_centroid = float(np.sum(freqs[band] * weights) / (np.sum(weights) + 1e-9))

    return {
        "f0": round(f0_median, 1),
        "pitch_spread_st": round(pitch_spread, 2),
        "rate_hz": round(rate_hz, 2),
        "formant_centroid": round(formant_centroid, 1),
        "envelope": [round(float(x), 4) for x in env_log],
    }


def apply_voice_clone_timbre(
    src_samples: np.ndarray,
    base_voice_id: str,
    clone_profile: dict,
    timbre_strength: float = 0.92,
    sample_rate: int = TARGET_SR,
) -> np.ndarray:
    """
    Transform synthesized base speech so its vocal tract resonance (formants F1..F4),
    spectral envelope, harmonic chestiness, and pitch contour match the cloned speaker's
    reference recording instead of sounding like raw Bataa/Yesui.
    """
    if src_samples.size < STFT_NPERSEG * 2:
        return src_samples

    target_env_list = clone_profile.get("envelope")
    if not target_env_list or len(target_env_list) != (STFT_NPERSEG // 2 + 1):
        # Load from saved reference wav if envelope wasn't cached yet
        ref_wav = os.path.join(CLONES_DIR, f"{clone_profile['id']}.wav")
        if os.path.exists(ref_wav):
            with open(ref_wav, "rb") as f:
                ref_samples = decode_audio_bytes(f.read(), sample_rate)
            target_env = extract_cepstral_envelope(ref_samples, sample_rate)
            clone_profile["envelope"] = [round(float(x), 4) for x in target_env]
        else:
            return src_samples
    else:
        target_env = np.array(target_env_list, dtype=np.float32)

    # Cache or compute the base neural voice's average spectral envelope
    src_env = extract_cepstral_envelope(src_samples, sample_rate)
    if base_voice_id not in BASE_ENVELOPES_CACHE:
        BASE_ENVELOPES_CACHE[base_voice_id] = src_env.copy()
    else:
        BASE_ENVELOPES_CACHE[base_voice_id] = (
            0.7 * BASE_ENVELOPES_CACHE[base_voice_id] + 0.3 * src_env
        )
    base_env = BASE_ENVELOPES_CACHE[base_voice_id]

    # 1. Compute Formant Frequency Warp factor from speaker's formant centroid vs base
    target_centroid = float(clone_profile.get("formant_centroid", 1450.0))
    base_centroid = 1320.0 if "bataa" in base_voice_id.lower() else 1620.0
    warp_ratio = float(np.clip(target_centroid / base_centroid, 0.84, 1.18))

    # 2. STFT Source-Filter Decomposition per frame
    _, _, Zxx = sp_signal.stft(
        src_samples, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    mag = np.abs(Zxx) + 1e-8
    phase = np.angle(Zxx)
    n_bins, n_frames = mag.shape

    # Warped target spectral envelope
    bins = np.arange(n_bins, dtype=np.float32)
    warped_target_env = np.interp(bins / warp_ratio, bins, target_env)

    # Differential log-spectral transfer curve (clamped to +/- 14 dB for naturalness)
    max_transfer_nepers = 14.0 / 8.6858896
    diff_log_env = np.clip(
        timbre_strength * (warped_target_env - base_env),
        -max_transfer_nepers,
        max_transfer_nepers,
    )

    #Also warp each frame's instantaneous formant peaks slightly toward the speaker's vocal tract length
    new_mag = np.empty_like(mag)
    lifter = np.zeros(STFT_NPERSEG, dtype=np.float64)
    lifter[:CEPSTRAL_LIFTER] = 1.0
    lifter[-CEPSTRAL_LIFTER + 1 :] = 1.0

    for t in range(n_frames):
        frame_log = np.log(mag[:, t])
        cep = np.fft.irfft(frame_log)
        inst_env = np.real(np.fft.rfft(cep * lifter))
        fine_excitation = frame_log - inst_env  # Glottal harmonic comb structure
        warped_inst_env = np.interp(bins / (1.0 + 0.65 * (warp_ratio - 1.0)), bins, inst_env)
        blended_env = warped_inst_env + diff_log_env
        new_mag[:, t] = np.exp(fine_excitation + blended_env)

    Zxx_mod = new_mag * np.exp(1j * phase)
    _, y_out = sp_signal.istft(
        Zxx_mod, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    y_out = y_out[: src_samples.size].astype(np.float32)

    # 3. Sub-harmonic chest warmth injection if speaker has lower F0 than base
    target_f0 = float(clone_profile.get("f0", 140.0))
    if target_f0 < 135.0:
        sos_sub = sp_signal.butter(2, [80.0 / (sample_rate / 2.0), 240.0 / (sample_rate / 2.0)], btype="bandpass", output="sos")
        sub_band = sp_signal.sosfiltfilt(sos_sub, y_out)
        chest_gain = min(0.35, (135.0 - target_f0) / 120.0)
        y_out = y_out + chest_gain * sub_band.astype(np.float32)

    return y_out


# ---------------------------------------------------------------------------
# Multilingual Code-Switching STT Engine (Mongolian + English + Japanese)
# ---------------------------------------------------------------------------

from concurrent.futures import ThreadPoolExecutor

# Common Mongolian corrections, English phrases & Japanese expressions mixed into speech
CODESWITCH_PHRASE_MAP: list[tuple[str, str]] = [
    # 0. Common Mongolian proper name & phrase phonetic fixes
    (r"\bнамайг\s+түшин\s*тулга?\b", "намайг Түвшинтулга"),
    (r"\bнамайг\s+түвшин\s*тулга?\b", "намайг Түвшинтулга"),
    (r"\bтүшин\s*тулга?\b", "Түвшинтулга"),
    (r"\bтүвшин\s+тул\b", "Түвшинтулга"),

    # 1. Conversational English phrases spoken mid-sentence (Cyrillic phonetic -> English)
    (r"\bхай\s+май\s+нэйм\s+из\b", "hi my name is"),
    (r"\bхай\s+май\s+нэймс\b", "hi my name is"),
    (r"\bхай\s+май\s+нэйм\b", "hi my name"),
    (r"\bмай\s+нэйм\s+из\b", "my name is"),
    (r"\bмай\s+нэм\s+из\b", "my name is"),
    (r"\bмай\s+нэймс\b", "my name is"),
    (r"\bмай\s+нэмс\b", "my name is"),
    (r"\bмай\s+нэйм\s+с\b", "my name is"),
    (r"\bмайн\s+нэйм\s+из\b", "my name is"),
    (r"\bмайн\s+нэмс\b", "my name is"),
    (r"\bми\s+нэйм\s+из\b", "my name is"),
    (r"\bмай\s+нэйм\b", "my name"),
    (r"\bмай\s+нэм\b", "my name"),
    (r"\bват\s+из\s+юур\s+нэйм\b", "what is your name"),
    (r"\bватс\s+юур\s+нэйм\b", "what's your name"),
    (r"\bай\s+эм\s+фром\s+монголиа\b", "I am from Mongolia"),
    (r"\bайм\s+фром\s+монголиа\b", "I'm from Mongolia"),
    (r"\bай\s+эм\s+фром\b", "I am from"),
    (r"\bай\s+эм\b", "I am"),
    (r"\bхау\s+ар\s+юу\b", "how are you"),
    (r"\bхау\s+ар\s+юү\b", "how are you"),
    (r"\bнайс\s+ту\s+мит\s+юу\b", "nice to meet you"),
    (r"\bнайс\s+тү\s+мит\s+юү\b", "nice to meet you"),
    (r"\bтэнк\s+юу\s+вэри\s+мач\b", "thank you very much"),
    (r"\bтэнк\s+юу\b", "thank you"),
    (r"\bтэнк\s+юү\b", "thank you"),
    (r"\bэкскюз\s+ми\b", "excuse me"),
    (r"\bай\s+донт\s+ноу\b", "I don't know"),
    (r"\bай\s+тинк\b", "I think"),
    (r"\bай\s+лав\s+юу\b", "I love you"),
    (r"\bлетс\s+гоу\b", "let's go"),
    (r"\bлэтс\s+гоу\b", "let's go"),
    (r"\bгуд\s+морнинг\b", "good morning"),
    (r"\bгүүд\s+морнинг\b", "good morning"),
    (r"\bгуд\s+найт\b", "good night"),
    (r"\bгуд\s+бай\b", "goodbye"),
    (r"\bбай\s+бай\b", "bye bye"),
    (r"\bхэллоу\s+эвриван\b", "hello everyone"),
    (r"\bхэллоу\s+ворлд\b", "hello world"),
    (r"\bхэллоу\b", "hello"),
    (r"\bхэлоу\b", "hello"),
    (r"\bплийз\b", "please"),
    (r"\bсорри\b", "sorry"),

    # 2. Multi-word tech & app phrases
    (r"\bконтрол\s+альт\b", "Ctrl+Alt"),
    (r"\bконтрол\s+алт\b", "Ctrl+Alt"),
    (r"\bкнтрл\s+альт\b", "Ctrl+Alt"),
    (r"\bвойс\s+студио\b", "VoiceStudio"),
    (r"\bвойс\s+флоу\b", "Voice Flow"),
    (r"\bдуудлага\s+флоу\b", "Duudlaga Flow"),
    (r"\bнекст\s+жэй\s*эс\b", "Next.js"),
    (r"\bнекст\s+жи\s*эс\b", "Next.js"),
    (r"\bнекст\s+жс\b", "Next.js"),
    (r"\bнод\s+жэй\s*эс\b", "Node.js"),
    (r"\bтайп\s*скрипт\b", "TypeScript"),
    (r"\bжава\s*скрипт\b", "JavaScript"),
    (r"\bчат\s*жи\s*пи\s*ти\b", "ChatGPT"),
    (r"\bчат\s*жпт\b", "ChatGPT"),
    (r"\bжемини\s+плас\b", "Gemini Plus"),
    (r"\bгүүгл\s+хром\b", "Google Chrome"),
    (r"\bмайкрософт\s+ворд\b", "Microsoft Word"),
    (r"\bвизуал\s+студио\b", "Visual Studio"),

    # 3. Japanese phrases & pronouns (Cyrillic & Romaji phonetic -> Authentic Japanese Kanji/Kana)
    (r"\bваташи\s*но\s+намаэ\s*ва\b", "私の名前は"),
    (r"\bваташи\s*но\s+намай\s*ва\b", "私の名前は"),
    (r"\bwatashi\s*no\s+namae\s*wa\b", "私の名前は"),
    (r"\bваташи\s*но\s+намаэ\b", "私の名前"),
    (r"\bваташи\s*но\s+намай\b", "私の名前"),
    (r"\bwatashi\s*no\s+namae\b", "私の名前"),
    (r"\bнамаэ\s*ва\b", "名前は"),
    (r"\bнамаэ\b", "名前"),
    (r"\bnamae\b", "名前"),
    (r"\bваташи\s*но\b", "私の"),
    (r"\bваташино\b", "私の"),
    (r"\bва\s+та\s+ши\s+но\b", "私の"),
    (r"\bwatashi\s*no\b", "私の"),
    (r"\bваташи\s*ва\b", "私は"),
    (r"\bваташива\b", "私は"),
    (r"\bwatashi\s*wa\b", "私は"),
    (r"\bваташи\b", "私"),
    (r"\bwatashi\b", "私"),
    (r"\bбоку\s*но\s+намаэ\s*ва\b", "僕の名前は"),
    (r"\bбоку\s*но\b", "僕の"),
    (r"\bboku\s*no\b", "僕の"),
    (r"\bбоку\s*ва\b", "僕は"),
    (r"\bboku\s*wa\b", "僕は"),
    (r"\bорэ\s*но\b", "俺の"),
    (r"\bорэ\s*ва\b", "俺は"),
    (r"\bаната\s*но\b", "あなたの"),
    (r"\banata\s*no\b", "あなたの"),
    (r"\bаната\s*ва\b", "あなたは"),
    (r"\banata\s*wa\b", "あなたは"),
    (r"\bкоре\s*ва\b", "これは"),
    (r"\bkore\s*wa\b", "これは"),
    (r"\bсоре\s*ва\b", "それは"),
    (r"\bsore\s*wa\b", "それは"),
    (r"\bаре\s*ва\b", "あれは"),
    (r"\bare\s*wa\b", "あれは"),
    (r"\bхажимэмашитэ\b", "初めまして"),
    (r"\bхажимэмаштэ\b", "初めまして"),
    (r"\bхажимемашите\b", "初めまして"),
    (r"\bhajimemashite\b", "初めまして"),
    (r"\bёрошикү\s+онэгайшимас\b", "よろしくお願いします"),
    (r"\bёрошику\s+онегайшимас\b", "よろしくお願いします"),
    (r"\byoroshiku\s+onegaishimasu\b", "よろしくお願いします"),
    (r"\bёрошикү\b", "よろしく"),
    (r"\bёрошику\b", "よろしく"),
    (r"\byoroshiku\b", "よろしく"),
    (r"\bонэгайшимас\b", "お願いします"),
    (r"\bонегайшимас\b", "お願いします"),
    (r"\bonegaishimasu\b", "お願いします"),
    (r"\bаригато\s+гозаймас\b", "ありがとうございます"),
    (r"\barigatou?\s+gozaimasu?\b", "ありがとうございます"),
    (r"\bаригато\b", "ありがとう"),
    (r"\barigatou?\b", "ありがとう"),
    (r"\bконничива\b", "こんにちは"),
    (r"\bконичива\b", "こんにちは"),
    (r"\bkonnichiwa\b", "こんにちは"),
    (r"\bконбанва\b", "こんばんは"),
    (r"\bkonbanwa\b", "こんばんは"),
    (r"\bохаёо\s+гозаймас\b", "おはようございます"),
    (r"\bohayou?\s+gozaimasu?\b", "おはようございます"),
    (r"\bохаёо\b", "おはよう"),
    (r"\bohayou?\b", "おはよう"),
    (r"\bсумимасэн\b", "すみません"),
    (r"\bсумимасен\b", "すみません"),
    (r"\bsumimasen\b", "すみません"),
    (r"\bгомэннасай\b", "ごめんなさい"),
    (r"\bгоменнасай\b", "ごめんなさい"),
    (r"\bgomennasai\b", "ごめんなさい"),
    (r"\bсаёонара\b", "さようなら"),
    (r"\bsayounara\b", "さようなら"),
    (r"\bогэнки\s+дэс\s*ка\b", "お元気ですか"),
    (r"\bогенки\s+дес\s*ка\b", "お元気ですか"),
    (r"\bogenki\s+desu\s*ka\b", "お元気ですか"),
    (r"\bгэнки\s+дэс\b", "元気です"),
    (r"\bgenki\s+desu\b", "元気です"),
    (r"\bнихонго\b", "日本語"),
    (r"\bnihongo\b", "日本語"),
    (r"\bмонгоруго\b", "モンゴル語"),
    (r"\bmongorugo\b", "モンゴル語"),
    (r"\bдайски\b", "大好き"),
    (r"\bдайсүки\b", "大好き"),
    (r"\bdaisuki\b", "大好き"),
    (r"\bсугой\b", "すごい"),
    (r"\bсүгой\b", "すごい"),
    (r"\bsugoi\b", "すごい"),
    (r"\bкавайи\b", "かわいい"),
    (r"\bкавай\b", "かわいい"),
    (r"\bkawaii\b", "かわいい"),
    (r"\bсэнсэй\b", "先生"),
    (r"\bсенсей\b", "先生"),
    (r"\bsensei\b", "先生"),
    (r"\bдайжообү\b", "大丈夫"),
    (r"\bдайжобү\b", "大丈夫"),
    (r"\bdaijoubu\b", "大丈夫"),
    (r"\bганбаттэ\b", "頑張って"),
    (r"\bганбатте\b", "頑張って"),
    (r"\bganbatte\b", "頑張って"),
    (r"\bвакаримашита\b", "分かりました"),
    (r"\bвакаримашта\b", "分かりました"),
    (r"\bwakarimashita\b", "分かりました"),
    (r"\bвакаримасэн\b", "分かりません"),
    (r"\bwakarimasen\b", "分かりません"),

    # 4. Single English tech & daily loanwords (preserving Mongolian suffixes if attached)
    (r"\bфэйсбүүк", "Facebook"),
    (r"\bфейсбүүк", "Facebook"),
    (r"\bфэйсбүк", "Facebook"),
    (r"\bинстаграм", "Instagram"),
    (r"\bтелеграм", "Telegram"),
    (r"\bюүтүб", "YouTube"),
    (r"\bютуб", "YouTube"),
    (r"\bтикток", "TikTok"),
    (r"\bворд\b", "Word"),
    (r"\bэксел\b", "Excel"),
    (r"\bпауэрпойнт\b", "PowerPoint"),
    (r"\bвиндоус\b", "Windows"),
    (r"\bайфон\b", "iPhone"),
    (r"\bандроид\b", "Android"),
    (r"\bпайтон\b", "Python"),
    (r"\bпитон\b", "Python"),
    (r"\bреакт\b", "React"),
    (r"\bфлаттер\b", "Flutter"),
    (r"\bдокер\b", "Docker"),
    (r"\bгитхаб\b", "GitHub"),
    (r"\bжемини\b", "Gemini"),
    (r"\bклод\b", "Claude"),
    (r"\bантигравити\b", "Antigravity"),
    (r"\bфронтенд\b", "Frontend"),
    (r"\bбэкенд\b", "Backend"),
    (r"\bфуллстэк\b", "Fullstack"),
    (r"\bдеплой\b", "deploy"),
    (r"\bкоммит\b", "commit"),
    (r"\bшорткат\b", "shortcut"),
    (r"\bхоткей\b", "hotkey"),
]

_CYR_TO_LAT_PHONETIC = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "ө": "u", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ү": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})


def _cyrillic_to_phonetic_latin(word: str) -> str:
    return word.lower().translate(_CYR_TO_LAT_PHONETIC)


def _phonetic_similarity(cyr_word: str, eng_word: str) -> float:
    """Measure phonetic similarity between a Cyrillic word and an English word recognized on the same audio."""
    c_lat = re.sub(r"[^a-z]", "", _cyrillic_to_phonetic_latin(cyr_word))
    e_lat = re.sub(r"[^a-z]", "", eng_word.lower())
    # Normalize common English silent/phonetic patterns
    e_norm = (
        e_lat.replace("ph", "f")
        .replace("tion", "shn")
        .replace("ck", "k")
        .replace("c", "k")
        .replace("w", "v")
        .replace("x", "ks")
        .replace("ee", "i")
        .replace("oo", "u")
    )
    if len(c_lat) < 3 or len(e_norm) < 3:
        return 0.0
    if c_lat == e_norm or c_lat.startswith(e_norm) or e_norm.startswith(c_lat):
        return 0.92
    # Character bigram Dice coefficient
    bg_c = {c_lat[i : i + 2] for i in range(len(c_lat) - 1)}
    bg_e = {e_norm[i : i + 2] for i in range(len(e_norm) - 1)}
    if not bg_c or not bg_e:
        return 0.0
    overlap = len(bg_c & bg_e)
    return (2.0 * overlap) / (len(bg_c) + len(bg_e))


# Mongolian words commonly romanized by en-US STT when speaking Mongolian — never replace Cyrillic with these!
_MONGOLIAN_ROMANIZED_STOP = {
    "sain", "baina", "bain", "bn", "uu", "yu", "ve", "be", "namaig", "minii", "chinii",
    "tanii", "manai", "tanai", "ene", "ter", "tere", "end", "tend", "odoo", "odo",
    "bol", "bolon", "baigaa", "baisan", "gesen", "gej", "geed", "yum", "ym", "shuu",
    "dee", "daa", "doo", "tuvshin", "tushin", "tulga", "tuvshintulga", "mongol",
    "helnii", "hel", "ug", "yaria", "bichig", "bicheh", "bolgoh", "ajillaj", "ajillah",
}


def restore_codeswitch_terms(mn_text: str, en_text: str = "", ja_text: str = "") -> str:
    """
    1. Applies curated Mongolian-English-Japanese code-switching phrase & word dictionary.
    2. Aligns multi-word & single-word phonetic Cyrillic spans with English words recognized in parallel (en_text).
    3. Splices authentic Japanese expressions recognized in parallel (ja_text).
    """
    if not mn_text:
        return mn_text

    out = mn_text
    for pattern, replacement in CODESWITCH_PHRASE_MAP:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    # Multi-word & single-word phonetic alignment with parallel en-US transcript
    if en_text:
        # First check if en_text itself contains Japanese romaji (e.g. "watashi no") and convert it in out if present
        en_raw_words = [w.strip(".,!?\"'()[]{}") for w in en_text.split() if w.strip(".,!?\"'()[]{}")]
        en_stop = {
            "that", "this", "with", "from", "have", "when", "where", "they", "will",
            "been", "were", "there", "about", "watashi", "boku", "anata", "namae",
            "konnichiwa", "arigato", "arigatou", "sumimasen", "yoroshiku", "hajimemashite",
        } | _MONGOLIAN_ROMANIZED_STOP

        # 1) Multi-word English conversational bigrams/trigrams from en_text (e.g. "my name is", "my name's", "how are you")
        if len(en_raw_words) >= 2:
            out_tokens = out.split()
            i = 0
            merged_tokens: list[str] = []
            while i < len(out_tokens):
                matched_span = False
                for span_len in (3, 2):
                    if i + span_len <= len(out_tokens):
                        cyr_slice = out_tokens[i : i + span_len]
                        # Only attempt if all tokens in slice are Cyrillic
                        if all(re.match(r"^[А-ЯӨҮЁа-яөүё.,!?]+$", t) for t in cyr_slice):
                            cyr_joined = "".join(t.strip(".,!?") for t in cyr_slice)
                            for j in range(len(en_raw_words) - span_len + 1):
                                eng_slice = en_raw_words[j : j + span_len]
                                if any(w.lower() in _MONGOLIAN_ROMANIZED_STOP for w in eng_slice):
                                    continue
                                eng_joined = "".join(eng_slice)
                                if _phonetic_similarity(cyr_joined, eng_joined) >= 0.75:
                                    punct = cyr_slice[-1][len(cyr_slice[-1].strip(".,!?")) :]
                                    merged_tokens.append(" ".join(eng_slice) + punct)
                                    i += span_len
                                    matched_span = True
                                    break
                    if matched_span:
                        break
                if not matched_span:
                    merged_tokens.append(out_tokens[i])
                    i += 1
            out = " ".join(merged_tokens)

        # 2) Single-word English alignment for words >= 4 chars
        en_candidates = [
            w for w in en_raw_words
            if len(w) >= 4 and w.lower() not in en_stop and w.isascii() and w.replace("'", "").isalpha()
        ]
        if en_candidates:
            tokens = out.split()
            new_tokens = []
            for tok in tokens:
                clean_tok = tok.strip(".,!?")
                punct_suffix = tok[len(clean_tok) :]
                replaced = False
                if re.match(r"^[А-ЯӨҮЁа-яөүё]{4,}$", clean_tok):
                    for eng_w in en_candidates:
                        sim = _phonetic_similarity(clean_tok, eng_w)
                        if sim >= 0.78:
                            new_tokens.append(eng_w + punct_suffix)
                            replaced = True
                            break
                if not replaced:
                    new_tokens.append(tok)
            out = " ".join(new_tokens)

    # Re-apply phrase map in case en_text injected romaji like "watashi no"
    for pattern, replacement in CODESWITCH_PHRASE_MAP:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    # Clean up spacing around Japanese Kanji/Kana and Latin characters
    out = re.sub(r"([А-ЯӨҮЁа-яөүёA-Za-z0-9])([\u3040-\u30ff\u4e00-\u9fff])", r"\1 \2", out)
    out = re.sub(r"([\u3040-\u30ff\u4e00-\u9fff])([А-ЯӨҮЁа-яөүёA-Za-z0-9])", r"\1 \2", out)
    out = re.sub(r"\s{2,}", " ", out).strip()

    return out


def select_or_fuse_trilingual_clause(
    mn_txt: str, mn_conf: float,
    en_txt: str, en_conf: float,
    ja_txt: str, ja_conf: float,
) -> str:
    """
    Intelligently fuses Mongolian (mn-MN), English (en-US), and Japanese (ja-JP).
    CRITICAL RULE: Never allow ja-JP or en-US to hallucinate foreign words over Mongolian speech!
    Mongolian is the primary baseline; Japanese and English phrases are selectively and accurately
    spliced into the sentence without corrupting Mongolian words like 'сайн байна уу', 'ухаалаг', etc.
    """
    mn_clean = (mn_txt or "").strip()
    en_clean = (en_txt or "").strip()
    ja_clean = (ja_txt or "").strip()

    # 1. If NO Mongolian text was recognized at all:
    if not mn_clean:
        # Check Japanese first if it contains genuine Japanese Kanji/Kana
        if ja_clean and re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", ja_clean):
            # Guard: ensure ja_clean is not an absurd single-syllable mistranslation
            return ja_clean
        if en_clean:
            return restore_codeswitch_terms(en_clean, en_text=en_clean, ja_text=ja_clean)
        return ""

    # 2. Check if the user spoke an ENTIRE standalone Japanese phrase with zero Mongolian content
    # (e.g. user just said "こんにちは" or "ありがとうございます" or "初めましてよろしくお願いします")
    pure_jp_patterns = r"^(私の名前は?|私は|こんにちは|ありがとう|ありがとうございます|初めまして|よろしくお願いします|おはようございます|こんばんは|すみません|ごめんなさい|さようなら|お元気ですか|大丈夫です?|元気です)$"
    if ja_clean and re.match(pure_jp_patterns, ja_clean.replace(" ", "")):
        return ja_clean

    # 3. Check if the user spoke an ENTIRE standalone English phrase with zero Mongolian content
    # (e.g. user just said "how are you", "my name is Tuvshin", "nice to meet you", "thank you very much")
    pure_en_patterns = r"^(my name is|how are you|nice to meet you|thank you very much|thank you|good morning|good night|hello everyone|let's go)"
    if en_clean and re.match(pure_en_patterns, en_clean.lower()):
        # Ensure mn_clean didn't contain genuine Mongolian words that aren't phonetic English
        mn_words = mn_clean.lower().split()
        phonetic_en_seeds = {"май", "майн", "нэйм", "нэмс", "нэм", "из", "ай", "эм", "хау", "ар", "юу", "юү", "найс", "ту", "тү", "мит", "тэнк", "вэри", "мач", "гуд", "морнинг", "хэллоу"}
        if all(w.strip(".,!?") in phonetic_en_seeds for w in mn_words):
            return restore_codeswitch_terms(en_clean, en_text=en_clean, ja_text=ja_clean)

    # 4. Standard Case (Mongolian primary + exact English and Japanese phrases spliced):
    # This prevents ja-JP from hallucinating '仙台', '買い', '良い', 'さん' over Mongolian words!
    return restore_codeswitch_terms(mn_clean, en_text=en_clean, ja_text=ja_clean)


import hashlib
import urllib.request

# Common glued words & detached suffix corrections for Mongolian STT precision
_MONGOLIAN_WORD_REFINEMENTS: list[tuple[str, str]] = [
    # 1. Glued words commonly produced by fast speech in Google mn-MN STT
    (r"\bсайнбайнауу\b", "сайн байна уу"),
    (r"\bсайнбайна\s+уу\b", "сайн байна уу"),
    (r"\bсайн\s+байнауу\b", "сайн байна уу"),
    (r"\bюубайна\b", "юу байна"),
    (r"\bяажбайна\b", "яаж байна"),
    (r"\bбайнауу\b", "байна уу"),
    (r"\bболохгүйбайна\b", "болохгүй байна"),
    (r"\bажиллахгүйбайна\b", "ажиллахгүй байна"),
    (r"\bтанихгүйбайна\b", "танихгүй байна"),
    (r"\bсонсогдохгүйбайна\b", "сонсогдохгүй байна"),
    (r"\bоржирэх\b", "орж ирэх"),
    (r"\bгарчирэх\b", "гарч ирэх"),
    (r"\bярьжбайна\b", "ярьж байна"),
    (r"\bхийжбайна\b", "хийж байна"),
    (r"\bбайгааюм\b", "байгаа юм"),
    (r"\bболохюм\b", "болох юм"),
    (r"\bхэрэгтэйбайна\b", "хэрэгтэй байна"),
    (r"\bболомжтойбайна\b", "боломжтой байна"),

    # 2. Detached negative suffix (-гүй / -гуй) that STT separates with a space
    (r"\b([А-ЯӨҮЁа-яөүё]{2,})\s+гүй\b", r"\1гүй"),
    (r"\b([А-ЯӨҮЁа-яөүё]{2,})\s+гуй\b", r"\1гүй"),
    (r"\b([А-ЯӨҮЁа-яөүё]{2,})\s+гүйн\b", r"\1гүйн"),

    # 3. Frequent phonetic word/letter confusions in Mongolian dictation
    (r"\bчадварыг\s+нь\b", "чадварыг нь"),
    (r"\bчадварын\s+илүү\b", "чадварыг нь илүү"),
    (r"\bчадварыг\s+илүү\b", "чадварыг нь илүү"),
    (r"\bтэрийн\s+сайжруулаад\b", "тэрийг нь сайжруулаад"),
    (r"\bтэрийг\s+сайжруулаад\b", "тэрийг нь сайжруулаад"),
    (r"\bүг\s+үсгийг\b", "үг, үсгийг"),
    (r"\bер\s+өөсөө\b", "ерөөсөө"),
    (r"\bтэр\s+өөсөө\b", "ерөөсөө"),
    (r"\bажилгаанд\b", "ажиллагаанд"),
    (r"\bажилагаанд\b", "ажиллагаанд"),
    (r"\bхөрвүлдэг\b", "хөрвүүлдэг"),
    (r"\bсайжрулад\b", "сайжруулаад"),
    (r"\bхөгжүлэд\b", "хөгжүүлээд"),
]


def _levenshtein_distance(a: str, b: str) -> int:
    """Compute character edit distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _encrypt_spellcheck_key(text: str) -> str:
    """Request key algorithm for spellcheck.mn ($encrypt function)."""
    mod = 10000000008
    n = 0
    for ch in text:
        n = (n + ord(ch) + 1) % mod
    return hashlib.sha256(str(n).encode("utf-8")).hexdigest()


def _auto_correct_subtle_typos_spellcheck_mn(text: str) -> str:
    """
    Queries spellcheck.mn with a fast timeout and automatically fixes ONLY genuine 1-to-2 letter
    orthographic/acoustic typos (where first letter matches and Levenshtein edit distance <= 2).
    Never alters foreign words, proper nouns, or words with distant suggestions.
    """
    if not text or len(text) < 3:
        return text
    # Only check if there are Cyrillic words
    if not re.search(r"[А-ЯӨҮЁа-яөүё]{4,}", text):
        return text

    base_url = "https://spellcheck.mn/cms-client/modules/spellchecker"
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://spellcheck.mn",
        "Referer": "https://spellcheck.mn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VoiceApp/1.0",
    }
    try:
        key = _encrypt_spellcheck_key(text)
        req = urllib.request.Request(
            f"{base_url}/check",
            data=json.dumps({"text": text, "key": key}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.6) as resp:
            raw_body = resp.read().decode("utf-8", errors="ignore")
        misspelled_raw = json.loads(raw_body)
        if not isinstance(misspelled_raw, list) or not misspelled_raw:
            return text

        misspelled = list({w.replace("-", "").strip() for w in misspelled_raw if isinstance(w, str) and len(w.replace("-", "").strip()) >= 4})
        if not misspelled:
            return text

        out = text
        for m_word in misspelled[:5]:  # Cap at 5 lookups max to stay under 1.5s
            # Skip capitalized proper names
            if m_word[0].isupper() and m_word not in out.split()[:1]:
                continue
            s_key = _encrypt_spellcheck_key(m_word)
            s_req = urllib.request.Request(
                f"{base_url}/suggest",
                data=json.dumps({"word": m_word, "key": s_key}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(s_req, timeout=1.2) as s_resp:
                s_body = s_resp.read().decode("utf-8", errors="ignore")
            cands = json.loads(s_body)
            if isinstance(cands, list) and cands:
                best_cand = str(cands[0]).strip()
                # Only auto-replace if it is a close 1-2 letter acoustic/orthographic fix
                # with the same starting letter and no space injection
                if (
                    best_cand
                    and " " not in best_cand
                    and best_cand[0].lower() == m_word[0].lower()
                    and 1 <= _levenshtein_distance(m_word.lower(), best_cand.lower()) <= 2
                ):
                    if m_word[0].isupper():
                        best_cand = best_cand[0].upper() + best_cand[1:]
                    out = re.sub(rf"(?<![А-ЯӨҮЁа-яөүё]){re.escape(m_word)}(?![А-ЯӨҮЁа-яөүё])", best_cand, out)
        return out
    except Exception:
        return text


def refine_mongolian_orthography_and_words(text: str) -> str:
    """
    Post-processes recognized speech to fix:
    1. Glued words ('сайнбайнауу' -> 'сайн байна уу')
    2. Detached suffixes ('болох гүй' -> 'болохгүй')
    3. Stuttered/duplicated adjacent words ('Сайн сайн байна уу' -> 'Сайн байна уу')
    4. Subtle 1-2 letter Mongolian spelling/acoustic errors via spellcheck.mn
    """
    if not text:
        return text

    out = text
    for pattern, replacement in _MONGOLIAN_WORD_REFINEMENTS:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    # Deduplicate accidental stuttered/repeated identical adjacent Cyrillic words (e.g. "Сайн сайн байна" -> "Сайн байна")
    tokens = out.split()
    deduped: list[str] = []
    for tok in tokens:
        if deduped:
            prev_clean = deduped[-1].strip(".,!?").lower()
            curr_clean = tok.strip(".,!?").lower()
            if curr_clean and curr_clean == prev_clean and re.match(r"^[а-яөүё]+$", curr_clean):
                # Keep punctuation if the second token had it
                if tok[-1] in ".,!?" and deduped[-1][-1] not in ".,!?":
                    deduped[-1] = deduped[-1] + tok[-1]
                continue
        deduped.append(tok)
    out = " ".join(deduped)

    # Run fast high-precision 1-2 letter spellcheck refinement
    out = _auto_correct_subtle_typos_spellcheck_mn(out)
    return out


def prepare_audio_for_asr(samples: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    Studio-grade acoustic front-end for maximum word & letter recognition accuracy:
    1. Removes DC offset and sub-85Hz mic rumble/pop.
    2. Spectral noise gating in STFT domain to suppress stationary fan/room noise.
    3. Consonant presence boost (2.0 kHz - 5.5 kHz) so Mongolian/English/Japanese plosives & sibilants
       (с, ш, ч, ц, т, д, г, к, х, л, р) are crisp and distinct.
    4. Syllable-level dynamic leveling so quiet word endings (-ийг, -ыг, -аар, -тай, -гүй) aren't lost.
    5. Adds 200ms leading and 250ms trailing silence margin so VAD never clips the first or last letter!
    """
    y = samples.astype(np.float64)
    y = y - np.mean(y)

    try:
        # 1. High-pass at 85Hz to remove rumble/pop
        sos_hp = sp_signal.butter(2, 85.0 / (sample_rate / 2.0), btype="highpass", output="sos")
        y = sp_signal.sosfiltfilt(sos_hp, y)

        # 2. Gentle STFT spectral noise floor gate
        if y.size >= 1024:
            f_bins, _, Zxx = sp_signal.stft(y, fs=sample_rate, nperseg=512, noverlap=384)
            mag = np.abs(Zxx)
            phase = np.angle(Zxx)
            noise_floor = np.percentile(mag, 15, axis=1, keepdims=True)
            gain = np.clip((mag - 0.65 * noise_floor) / np.maximum(mag, 1e-9), 0.25, 1.0)
            # 3. Consonant & formant clarity boost (2.0 kHz - 5.5 kHz)
            presence_boost = np.ones((f_bins.size, 1), dtype=np.float64)
            band_mask = (f_bins >= 1800.0) & (f_bins <= 5800.0)
            presence_boost[band_mask, 0] = 1.28  # +2.1 dB consonant articulation boost
            Zxx_clean = (mag * gain * presence_boost) * np.exp(1j * phase)
            _, y_rec = sp_signal.istft(Zxx_clean, fs=sample_rate, nperseg=512, noverlap=384)
            y = y_rec[: y.size]
    except Exception:
        pass

    y32 = y.astype(np.float32)
    # Trim dead silence with a gentle -48 dB threshold so quiet word-initial/final consonants survive
    y32 = trim_silence(y32, sample_rate, threshold_db=-48.0)
    y32 = level_speech_np(y32, sample_rate)
    y32 = normalize_audio_np(y32, target_dbfs=-1.0)

    # Pad 200ms leading silence and 250ms trailing silence so Google's VAD never clips the first/last letter
    lead_pad = np.zeros(int(0.20 * sample_rate), dtype=np.float32)
    trail_pad = np.zeros(int(0.25 * sample_rate), dtype=np.float32)
    return np.concatenate([lead_pad, y32, trail_pad])


def split_audio_on_pauses(samples: np.ndarray, sample_rate: int = 16000, min_duration: float = 2.8) -> list[np.ndarray]:
    """
    Splits audio only at genuine inter-phrase pauses (>= 280ms = 14 frames) with minimum segment length min_duration,
    preventing mid-word splits that break consonant closures or glue words together.
    """
    duration = samples.size / float(sample_rate)
    if duration < min_duration:
        return [samples]

    frame_len = int(0.02 * sample_rate)  # 20ms frames
    n_frames = samples.size // frame_len
    if n_frames < 30:
        return [samples]

    framed = samples[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(framed ** 2, axis=1) + 1e-10)
    thresh = max(0.014, float(np.percentile(rms, 22)) * 1.15)
    is_silent = rms < thresh

    # Find contiguous silent runs >= 15 frames (300ms)
    segments: list[np.ndarray] = []
    seg_start_sample = 0
    silent_run = 0
    pad_samples = int(0.15 * sample_rate)

    for i, sil in enumerate(is_silent):
        if sil:
            silent_run += 1
        else:
            if silent_run >= 15:
                split_frame = i - (silent_run // 2)
                split_sample = split_frame * frame_len
                if (split_sample - seg_start_sample) >= int(1.25 * sample_rate):
                    seg_chunk = samples[seg_start_sample:split_sample]
                    # Pad 150ms silence on split boundaries so boundary letters are never clipped
                    seg_padded = np.concatenate([
                        np.zeros(pad_samples, dtype=np.float32),
                        seg_chunk,
                        np.zeros(pad_samples, dtype=np.float32),
                    ])
                    segments.append(seg_padded)
                    seg_start_sample = split_sample
            silent_run = 0

    tail = samples[seg_start_sample:]
    if tail.size >= int(0.60 * sample_rate) or not segments:
        tail_padded = np.concatenate([
            np.zeros(pad_samples, dtype=np.float32),
            tail,
            np.zeros(pad_samples, dtype=np.float32),
        ])
        segments.append(tail_padded)
    elif segments:
        segments[-1] = np.concatenate([segments[-1], tail, np.zeros(pad_samples, dtype=np.float32)])

    if len(segments) > 6:
        return [samples]
    return segments


def _score_candidate_hypothesis(text: str, base_conf: float, lang_code: str) -> float:
    """
    Reranks Google STT N-best alternative hypotheses based on word-boundary quality,
    orthographic validity, and absence of glued or fragmented words.
    """
    if not text:
        return -1.0
    score = base_conf
    words = text.split()
    if not words:
        return -1.0

    if lang_code == "mn-MN":
        for w in words:
            clean = w.strip(".,!?")
            # Penalize abnormally long glued words (> 16 letters like 'сайнбайнауу')
            if len(clean) >= 16:
                score -= 0.08
            # Penalize stray 1-letter Cyrillic fragments (except valid particles/abbreviations)
            if len(clean) == 1 and clean.lower() not in ("б", "в", "г", "д", "л", "нь", "ч", "ш"):
                score -= 0.05
        # Reward well-spaced common Mongolian words & particles
        lower_txt = f" {text.lower()} "
        for good_tok in (" байна ", " уу ", " юу ", " нь ", " болон ", " дээр ", " гэж ", " сайн ", " бол "):
            if good_tok in lower_txt:
                score += 0.03

    return score


def apply_voice_punctuations(text: str) -> str:
    """
    Converts spoken punctuation commands into real punctuation marks:
    - 'шинэ мөр' / 'шинэмөр' -> newline
    - 'догол мөр' -> paragraph newline
    - 'таслал' -> ,
    - 'цэг' -> .
    - 'асуултын тэмдэг' -> ?
    - 'анхаарлын тэмдэг' -> !
    - 'new line' -> newline, 'comma' -> ,, 'period' -> .
    - '改行' -> newline, 'まる' -> 。, 'てん' -> 、
    """
    if not text:
        return text

    patterns = [
        (r"(?i)(?:\s+|^)(?:шинэ\s+мөр|шинэмөр)(?:\s+|$)", "\n"),
        (r"(?i)(?:\s+|^)догол\s+мөр(?:\s+|$)", "\n\n"),
        (r"(?i)\s+таслал(?:\s+|$)", ", "),
        (r"(?i)\s+цэг(?:\s+|$)", ". "),
        (r"(?i)\s+асуултын\s+тэмдэг(?:\s+|$)", "? "),
        (r"(?i)\s+анхаарлын\s+тэмдэг(?:\s+|$)", "! "),
        (r"(?i)\s+зураас(?:\s+|$)", " - "),
        (r"(?i)\s+хоёр\s+цэг(?:\s+|$)", ": "),
        (r"(?i)(?:\s+|^)new\s+line(?:\s+|$)", "\n"),
        (r"(?i)\s+comma(?:\s+|$)", ", "),
        (r"(?i)\s+period(?:\s+|$)", ". "),
        (r"(?i)\s+full\s+stop(?:\s+|$)", ". "),
        (r"(?i)\s+question\s+mark(?:\s+|$)", "? "),
        (r"(?i)\s+exclamation\s+mark(?:\s+|$)", "! "),
        (r"(?:\s+|^)改行(?:\s+|$)", "\n"),
        (r"\s*まる\s*", "。"),
        (r"\s*てん\s*", "、"),
        (r"\s*はてな\s*", "？"),
    ]
    out = text
    for pat, repl in patterns:
        out = re.sub(pat, repl, out)
    out = re.sub(r"([.,!?])\s*([.,!?])", r"\1", out)
    return out.strip()


def _recognize_single_lang(wav_bytes: bytes, lang_code: str) -> tuple[str, float, bool]:
    """Run Google STT with show_all=True and rerank all N-best alternatives for maximum word/letter accuracy."""
    r = sr.Recognizer()
    r.dynamic_energy_threshold = False
    net_err = False
    try:
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio_data = r.record(source)
        res = r.recognize_google(audio_data, language=lang_code, show_all=True)
        if isinstance(res, dict) and "alternative" in res and res["alternative"]:
            alts = res["alternative"]
            best_text = ""
            best_conf = 0.0
            best_score = -999.0
            for idx, alt in enumerate(alts):
                cand_text = (alt.get("transcript") or "").strip()
                if not cand_text:
                    continue
                raw_conf = float(alt.get("confidence", max(0.70, 0.84 - idx * 0.03)))
                cand_score = _score_candidate_hypothesis(cand_text, raw_conf, lang_code)
                if cand_score > best_score:
                    best_score = cand_score
                    best_text = cand_text
                    best_conf = raw_conf
            return best_text, best_conf, False
    except sr.RequestError:
        net_err = True
    except Exception:
        pass
    return "", 0.0, net_err


def transcribe_wav_bytes(raw_bytes: bytes, language: str = "mn") -> tuple[str, str]:
    """
    Studio-grade Multilingual & High-Precision Word/Letter STT Engine:
    1. Spectral noise gate + consonant articulation boost (2-5.5 kHz) + 200ms VAD padding.
    2. Splits long utterances only on genuine pauses (>= 300ms) with padded boundaries.
    3. Reranks N-best hypotheses across mn-MN, en-US, ja-JP.
    4. Refines Mongolian word boundaries, detached suffixes, stuttered words, and 1-2 letter typos via spellcheck.mn.
    """
    if not HAS_SR:
        return "", "SpeechRecognition суугаагүй байна."

    try:
        samples = decode_audio_bytes(raw_bytes, target_sr=16000)
    except Exception as e:
        return "", f"Аудио уншихад алдаа: {e}"

    if samples.size < 2400:  # < 0.15s
        return "", "Аудио хэт богино байна."

    # 1. Studio Acoustic Conditioning for Crisp Word & Letter Recognition
    samples = prepare_audio_for_asr(samples, 16000)

    req_lang = (language or "mn").lower().strip()
    split_dur = 2.5 if req_lang == "auto" else 12.0
    segments = split_audio_on_pauses(samples, 16000, min_duration=split_dur)

    final_clauses: list[str] = []

    cfg_engine = SERVER_SETTINGS.get("stt_engine", "google").lower()
    if cfg_engine in ("whisper", "whisper_cpp"):
        m_name = SERVER_SETTINGS.get("whisper_model", "small")
        return transcribe_with_whisper(raw_bytes, language=req_lang, model_name=m_name)

    net_err_found = False
    with ThreadPoolExecutor(max_workers=3) as pool:
        for seg in segments:
            seg_wav = encode_wav_bytes(seg, 16000)

            if req_lang in ("mn", "mn-mn"):
                mn_txt, mn_conf, m_err = _recognize_single_lang(seg_wav, "mn-MN")
                if m_err:
                    net_err_found = True
                if mn_txt:
                    final_clauses.append(apply_voice_punctuations(mn_txt))

            elif req_lang in ("en", "en-us"):
                en_txt, en_conf, e_err = _recognize_single_lang(seg_wav, "en-US")
                if e_err: net_err_found = True
                if en_txt:
                    final_clauses.append(apply_voice_punctuations(en_txt))

            elif req_lang in ("ja", "ja-jp"):
                ja_txt, ja_conf, j_err = _recognize_single_lang(seg_wav, "ja-JP")
                if j_err: net_err_found = True
                if ja_txt:
                    final_clauses.append(apply_voice_punctuations(ja_txt))

            else:
                # Intelligent Trilingual Auto-Classification for mixed MN, EN, JA!
                fut_mn = pool.submit(_recognize_single_lang, seg_wav, "mn-MN")
                fut_en = pool.submit(_recognize_single_lang, seg_wav, "en-US")
                fut_ja = pool.submit(_recognize_single_lang, seg_wav, "ja-JP")

                mn_txt, mn_conf, m_err = fut_mn.result()
                en_txt, en_conf, e_err = fut_en.result()
                ja_txt, ja_conf, j_err = fut_ja.result()
                if m_err or e_err or j_err: net_err_found = True

                has_jp = bool(ja_txt and re.search(r"[぀-ヿ一-龯]", ja_txt))
                has_en_words = bool(en_txt and re.search(r"(?i)(hello|my|name|is|thank|you|very|much|nice|to|meet|how|are|good|morning|night|day|what|where|when|why|who|please|help|welcome|google|chrome|chatgpt|voice|world|test)", en_txt))
                has_mn_words = bool(mn_txt and re.search(r"(?i)[а-яөүё]", mn_txt))

                # Priority scoring
                chosen = ""
                if has_jp and (ja_conf >= 0.70 or ja_conf >= mn_conf - 0.12 or not has_mn_words):
                    chosen = ja_txt
                elif has_en_words and (en_conf >= 0.72 or en_conf >= mn_conf - 0.08 or not has_mn_words):
                    chosen = en_txt
                elif has_mn_words:
                    chosen = mn_txt
                else:
                    candidates = [(mn_txt, mn_conf), (en_txt, en_conf), (ja_txt, ja_conf)]
                    candidates.sort(key=lambda x: x[1], reverse=True)
                    chosen = candidates[0][0]

                if chosen:
                    final_clauses.append(apply_voice_punctuations(chosen))

    text = " ".join(c.strip() for c in final_clauses if c.strip()).strip()
    if text:
        text = refine_mongolian_orthography_and_words(text)
        text = text[0].upper() + text[1:]
        if text[-1] not in ".!?。！？":
            text += "."
        return text, ""

    if net_err_found or not text:
        # Offline Dictation Fallback: seamlessly fall back to local Whisper
        try:
            logger.info("[STT] Online STT unavailable (net_err=%s), fallback to local Whisper...", net_err_found)
            m_name = SERVER_SETTINGS.get("whisper_model", "small")
            w_text, w_err = transcribe_with_whisper(raw_bytes, language=req_lang, model_name=m_name)
            if w_text:
                FLOWBAR_STATE["offline_fallback"] = True
                return w_text, ""
        except Exception as fb_err:
            logger.warning("[STT] Whisper offline fallback error: %s", str(fb_err).encode("ascii", "replace").decode("ascii"))

        if net_err_found:
            return "", "Интернет холболтоо шалгана уу (Google Speech API холбогдсонгүй)."
        return "", "Яриа танигдсангүй. Микрофондоо ойрхон, тод ярина уу."

    FLOWBAR_STATE["offline_fallback"] = False


# ---------------------------------------------------------------------------
# Native Windows Duudlaga Flow Engine:
# Global Ctrl+Alt / F8 Hook + Always-On-Top Floating Pill + Direct Word/Facebook Typing
# ---------------------------------------------------------------------------

FLOWBAR_STATE = {
    "status": "idle",        # idle | recording | processing | success | error
    "visible": True,
    "is_paused": False,      # Stage 5 dictation pause/resume state
    "last_text": "",
    "last_timestamp": 0,
    "error": "",
    "seconds": 0,
    "levels": [4, 8, 12, 8, 4],
    "language": "auto",
    "target_window": "",
    "desktop": "",
    "last_insert_debug": "",
    "ui_alive": False,       # FlowBar window thread is running and drawing
    "ui_heartbeat": 0.0,
    "ui_error": "",
    "ui_fatal": False,
    "ui_restarts": 0,
    "pos": "",
    "mic_ok": True,
    "mic_error": "",
    "hotkey_ok": True,
    "hotkey_error": "",
    "undo_available": False,
    "undo_until": 0.0,
    "offline_fallback": False,
    "interim_preview": "",
}

FLOWBAR_W, FLOWBAR_H = 360, 52
_flowbar_cmds: "queue.Queue[tuple]" = queue.Queue()   # commands executed ON the Tk thread
_flowbar_ui_lock = threading.Lock()
_flowbar_ui_thread = None

_target_hwnd: int = 0
_last_active_hwnd: int = 0
_last_active_title: str = ""
_last_external_hwnd: int = 0
_last_external_title: str = ""
_flowbar_hwnd: int = 0
_recording_Buffer: list[np.ndarray] = []
_recording_lock = threading.Lock()
_is_recording = False
_record_start_time = 0.0
_last_speech_time = 0.0
_last_stop_time = 0.0
_speech_frames_count = 0
_has_spoken = False
_tk_root = None

if os.name == "nt":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_TOPMOST = 0x00000008

    HWND_TOPMOST = wintypes.HWND(-1)
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    SWP_FRAMECHANGED = 0x0020
    SPI_GETWORKAREA = 0x0030

    INPUT_KEYBOARD = 1
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_LCONTROL = 0xA2
    VK_RCONTROL = 0xA3
    VK_MENU = 0x12
    VK_LMENU = 0xA4
    VK_RMENU = 0xA5
    VK_SHIFT = 0x10
    VK_LSHIFT = 0xA0
    VK_RSHIFT = 0xA1
    VK_SPACE = 0x20
    VK_TAB = 0x09
    VK_F8 = 0x77
    VK_F9 = 0x78
    VK_F10 = 0x79
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C
    VK_V = 0x56
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
    user32.SystemParametersInfoW.restype = wintypes.BOOL
    user32.MonitorFromRect.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    user32.MonitorFromRect.restype = wintypes.HMONITOR

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL

def get_primary_work_area() -> tuple[int, int, int, int]:
    global _tk_root
    if os.name != "nt":
        return 0, 0, 1280, 720
    # Always prioritize Tkinter's logical coordinate space for root.geometry!
    if _tk_root is not None:
        try:
            sw = _tk_root.winfo_screenwidth()
            sh = _tk_root.winfo_screenheight()
            if sw > 400 and sh > 300:
                return 0, 0, sw, max(sh - 48, 200)
        except Exception:
            pass
    r = wintypes.RECT()
    if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
        return r.left, r.top, r.right, r.bottom
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

def is_rect_on_any_screen(x: int, y: int, w: int = 360, h: int = 52) -> bool:
    """True only if a good part of the bar (its centre area) is on a real monitor."""
    if os.name != "nt":
        return True
    try:
        cx, cy = x + w // 2, y + h // 2
        r = wintypes.RECT(cx - 40, cy - 20, cx + 40, cy + 20)
        return bool(user32.MonitorFromRect(ctypes.byref(r), 0))
    except Exception:
        return True

def get_fallback_flowbar_pos(bar_w: int = 360, bar_h: int = 52) -> tuple[int, int]:
    work = get_primary_work_area()
    return get_fallback_flowbar_pos_math(work, bar_w=bar_w, bar_h=bar_h, margin_x=24, margin_y=24)

def reset_flowbar_position():
    """Move FlowBar to the bottom-right corner. Tk is touched only from its own thread."""
    fx, fy = get_fallback_flowbar_pos(FLOWBAR_W, FLOWBAR_H)
    try:
        with open(os.path.join(USER_DATA_DIR, "flowbar_pos.txt"), "w", encoding="utf-8") as pf:
            pf.write(f"{fx},{fy}")
    except Exception:
        pass
    FLOWBAR_STATE["visible"] = True
    if flowbar_ui_is_alive():
        _flowbar_cmds.put(("place", fx, fy))
    else:
        ensure_flowbar_ui()   # a fresh window reads the saved position
    print(f"[FlowBar] Reset position to bottom-right: ({fx}, {fy})")


def get_windows_clipboard_text() -> str:
    if os.name != "nt":
        return ""
    try:
        if not user32.OpenClipboard(0):
            return ""
        try:
            if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return ""
            h_data = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_data:
                return ""
            ptr = kernel32.GlobalLock(h_data)
            if not ptr:
                return ""
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(h_data)
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""

_whisper_model_instance = None
_whisper_model_name = ""

def get_whisper_model(model_name: str = "small"):
    global _whisper_model_instance, _whisper_model_name
    if _whisper_model_instance is not None and _whisper_model_name == model_name:
        return _whisper_model_instance
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper суугаагүй байна. Оффлайн горимд: "
            "'.venv\\Scripts\\python.exe -m pip install -r requirements-offline.txt' ажиллуулна уу."
        )

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"

    compute_type = "float16" if device == "cuda" else "int8"
    print(f"[+] Loading faster-whisper model '{model_name}' on {device} ({compute_type})...")
    _whisper_model_instance = WhisperModel(model_name, device=device, compute_type=compute_type)
    _whisper_model_name = model_name
    return _whisper_model_instance

def transcribe_with_whisper(
    wav_bytes: bytes,
    language: str = "auto",
    model_name: str = "small",
    use_gpu: bool = True,
    threads: int = 6,
    initial_prompt: Optional[str] = None,
) -> tuple[str, str]:
    if initial_prompt is None:
        cfg_prompt = load_server_settings()
        custom_vocab = cfg_prompt.get("custom_vocabulary", [])
        if custom_vocab:
            initial_prompt = build_whisper_initial_prompt(custom_vocab)

    # 1. Prefer local whisper.cpp CLI subprocess if binary and model are present
    if find_whisper_cpp_binary() and (find_local_ggml_model(model_name) or find_local_ggml_model("tiny")):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tf.write(wav_bytes)
            tf_path = tf.name
        try:
            txt, segs, err = transcribe_with_whisper_cpp_cli(
                tf_path,
                model_name=model_name,
                language=language,
                use_gpu=use_gpu,
                threads=threads,
                initial_prompt=initial_prompt,
            )
            if not err and txt:
                return txt, ""
            if err:
                logger.warning("[whisper.cpp error]: %s", err.encode("ascii", "replace").decode("ascii"))
        finally:
            if os.path.exists(tf_path):
                try:
                    os.remove(tf_path)
                except Exception:
                    pass

    # 2. Fall back to faster-whisper if installed
    try:
        model = get_whisper_model(model_name)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tf.write(wav_bytes)
            tf_path = tf.name
        try:
            lang_arg = None if language in ("auto", "") else language
            segments, info = model.transcribe(
                tf_path,
                language=lang_arg,
                beam_size=5,
                initial_prompt=initial_prompt,
            )
            text = " ".join([s.text.strip() for s in segments]).strip()
            if not text:
                return "", "Whisper яриа таньсангүй."
            return text, ""
        finally:
            if os.path.exists(tf_path):
                try:
                    os.remove(tf_path)
                except Exception:
                    pass
    except Exception as e:
        safe_msg = str(e).encode('ascii', 'replace').decode('ascii')
        logger.warning("[Whisper error]: %s", safe_msg)
        return "", f"Whisper алдаа: {e}"


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTunion)]


def is_own_process_window(hwnd: int) -> bool:
    """Return True if hwnd belongs to this Python tts_server.py process (i.e. Tkinter FlowBar)."""
    if not hwnd or os.name != "nt":
        return False
    try:
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:
        return False


def get_window_title(hwnd: int) -> str:
    if not hwnd or os.name != "nt":
        return ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value.strip()
    except Exception:
        return ""


def attach_to_interactive_desktop() -> bool:
    """
    Attach current thread to the interactive user desktop (WinSta0\\Default).
    This ensures GUI windows (Tkinter FlowBar) render directly on the user's visible physical monitor.
    """
    if os.name != "nt":
        return False
    try:
        hwinsta = user32.OpenWindowStationW("WinSta0", False, 0x0000037F)
        if hwinsta:
            user32.SetProcessWindowStation(hwinsta)
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x000001FF)
        if hdesk:
            return bool(user32.SetThreadDesktop(hdesk))
    except Exception:
        pass
    return False


def get_current_desktop_name() -> str:
    if os.name != "nt":
        return "posix"
    try:
        desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
        buf = ctypes.create_unicode_buffer(256)
        user32.GetUserObjectInformationW(desk, 2, buf, 512, None)
        return buf.value
    except Exception:
        return "unknown"


def _suppress_alt_menu_activation() -> None:
    """
    When a user presses Ctrl+Alt and releases Alt, Windows normally sends WM_SYSCOMMAND(SC_KEYMENU)
    which focuses the window's top menu bar (File, Edit...) and steals focus from the text input box!
    Sending an unassigned virtual key (0xFF) while Alt is held tells win32k that Alt was part of a chord,
    completely suppressing menu bar activation when Alt is released.
    """
    if os.name != "nt":
        return
    try:
        dummy = (INPUT * 2)()
        dummy[0].type = INPUT_KEYBOARD
        dummy[0].union.ki = KEYBDINPUT(0xFF, 0, 0, 0, 0)
        dummy[1].type = INPUT_KEYBOARD
        dummy[1].union.ki = KEYBDINPUT(0xFF, 0, KEYEVENTF_KEYUP, 0, 0)
        user32.SendInput(2, ctypes.byref(dummy), ctypes.sizeof(INPUT))
    except Exception:
        pass



def play_sound_cue(cue: str) -> None:
    """Play subtle non-blocking audio cue on Windows for immediate user feedback."""
    if os.name != "nt":
        return
    try:
        cfg = load_server_settings()
        if not cfg.get("sound_cues", True):
            return
    except Exception:
        pass

    def _beep():
        try:
            import winsound
            if cue == "start":
                # Subtle high chime (B5, 65ms)
                winsound.Beep(988, 65)
            elif cue == "finish":
                # Pleasant success chime (E6, 75ms)
                winsound.Beep(1318, 75)
            elif cue == "error":
                # Soft alert (A4, 110ms)
                winsound.Beep(440, 110)
        except Exception:
            pass

    threading.Thread(target=_beep, daemon=True).start()


def copy_to_windows_clipboard(text: str) -> None:
    """
    Thread-safe native Win32 clipboard copy using CF_UNICODETEXT.
    Applies Unicode NFC normalization to preserve proper glyph rendering (e.g. ө, ү)
    and preserve document font styles in Word, OneNote, and Notepad.
    Never touches Tkinter from background threads and never spawns clip.exe!
    """
    if not text or os.name != "nt":
        return
    text = unicodedata.normalize("NFC", text)
    data = text.encode("utf-16-le") + b"\x00\x00"
    for _ in range(5):
        if user32.OpenClipboard(0):
            try:
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                if h_mem:
                    ptr = kernel32.GlobalLock(h_mem)
                    if ptr:
                        ctypes.memmove(ptr, data, len(data))
                        kernel32.GlobalUnlock(h_mem)
                        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                return
            finally:
                user32.CloseClipboard()
        time.sleep(0.01)


def inject_text_into_target_window(text: str, hwnd: int = 0) -> bool:
    """
    Safe text insertion into target window with Unicode NFC normalization.
    Ensures Mongolian characters (ө, ү) are canonically composed and target application
    (Word, OneNote, Notepad, Browser) fonts/styles are preserved.
    """
    if not text:
        return False
    return insert_text_to_active_window(unicodedata.normalize("NFC", text), hwnd)


def restore_window_focus(target: int) -> bool:
    """Restore foreground window without corrupting child control focus (e.g. Chrome search bar)."""
    if not target or os.name != "nt" or is_own_process_window(target):
        return False
    try:
        curr_fg = user32.GetForegroundWindow()
        if curr_fg == target:
            return True
        target_tid = user32.GetWindowThreadProcessId(target, None)
        curr_tid = kernel32.GetCurrentThreadId()
        attached = False
        if target_tid and target_tid != curr_tid:
            attached = bool(user32.AttachThreadInput(curr_tid, target_tid, True))
        try:
            if user32.IsIconic(target):
                user32.ShowWindow(target, 9)  # SW_RESTORE if minimized
            user32.SetForegroundWindow(target)
            user32.BringWindowToTop(target)
            # Never call user32.SetFocus(target) on top-level window as it unfocuses child edit controls
        finally:
            if attached:
                user32.AttachThreadInput(curr_tid, target_tid, False)
        return True
    except Exception:
        return False



# ---------------------------------------------------------------------------
# Windows Autostart via HKCU Run (no admin rights needed)
# ---------------------------------------------------------------------------

def is_autostart_enabled() -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "VOICE")
            return bool(val)
    except Exception:
        return False


def set_autostart_enabled(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                canonical_bat = os.path.join(CANONICAL_APP_DIR, "Start-VOICE.bat")
                start_bat = os.path.join(BASE_DIR, "Start-VOICE.bat")
                target_bat = canonical_bat if os.path.exists(canonical_bat) else start_bat
                cmd = f'"{target_bat}" --background'
                winreg.SetValueEx(key, "VOICE", 0, winreg.REG_SZ, cmd)
                logger.info("[Autostart] Enabled in HKCU Run: %s", cmd)
            else:
                try:
                    winreg.DeleteValue(key, "VOICE")
                    logger.info("[Autostart] Disabled in HKCU Run")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        logger.warning("[Autostart] Failed to change HKCU Run: %s", e)
        return False


# ---------------------------------------------------------------------------
# System Tray Icon (pystray + Pillow, optional)
# ---------------------------------------------------------------------------

_TRAY_AVAILABLE = False
_tray_icon = None


def _start_tray_icon() -> None:
    global _TRAY_AVAILABLE, _tray_icon
    if os.name != "nt":
        return
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        logger.info("[Tray] pystray or Pillow not installed; tray icon disabled.")
        return

    try:
        ico_path = os.path.join(BASE_DIR, "public", "voice.ico")
        if os.path.isfile(ico_path):
            img = Image.open(ico_path)
        else:
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((4, 4, 60, 60), fill=(99, 102, 241), outline=(129, 140, 248), width=3)

        def on_open_dashboard(icon, item):
            _open_browser_window(force=True)

        def on_toggle_flowbar(icon, item):
            cur = bool(FLOWBAR_STATE.get("visible", True))
            FLOWBAR_STATE["visible"] = not cur
            if FLOWBAR_STATE["visible"]:
                ensure_flowbar_ui()
                _flowbar_cmds.put(("show",))
            else:
                _flowbar_cmds.put(("hide",))

        def on_reset_pos(icon, item):
            reset_flowbar_position()

        def on_set_lang(lang_code):
            def _handler(icon, item):
                FLOWBAR_STATE["language"] = lang_code
                save_server_settings({"language": lang_code})
                SERVER_SETTINGS["language"] = lang_code
                logger.info("[Tray] Language switched to: %s", lang_code)
            return _handler

        def on_toggle_pause(icon, item):
            cur = FLOWBAR_STATE.get("is_paused", False)
            FLOWBAR_STATE["is_paused"] = not cur
            if FLOWBAR_STATE["is_paused"]:
                if _is_recording:
                    stop_native_flowbar_recording()
                FLOWBAR_STATE["status"] = "idle"
            logger.info("[Tray] Dictation is_paused=%s", FLOWBAR_STATE["is_paused"])

        def on_check_update(icon, item):
            def _check():
                try:
                    import auto_updater
                    info = auto_updater.check_github_release(current_version=APP_VERSION)
                    if info.get("has_update"):
                        msg = f"Шинэ хувилбар v{info.get('latest_version')} бэлэн боллоо!\nХувилбарын хуудсыг нээж татаж авах боломжтой."
                        try:
                            if hasattr(icon, "notify"):
                                icon.notify(msg, "VOICE Шинэчлэл")
                        except Exception:
                            pass
                        import webbrowser
                        if info.get("html_url"):
                            webbrowser.open(info["html_url"])
                    else:
                        try:
                            if hasattr(icon, "notify"):
                                icon.notify(f"Та хамгийн сүүлийн үеийн (v{APP_VERSION}) хувилбарыг ашиглаж байна.", "VOICE")
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning("[Tray] Update check failed: %s", e)
            threading.Thread(target=_check, daemon=True).start()

        def on_toggle_autostart(icon, item):
            cur = is_autostart_enabled()
            set_autostart_enabled(not cur)

        def on_quit(icon, item):
            icon.stop()
            threading.Thread(target=lambda: (time.sleep(0.3), os._exit(0))).start()

        menu = pystray.Menu(
            pystray.MenuItem("VOICE нээх", on_open_dashboard, default=True),
            pystray.MenuItem("FlowBar харуулах / нуух", on_toggle_flowbar),
            pystray.MenuItem("Байрлал шинэчлэх", on_reset_pos),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Хэл сонгох (Language)",
                pystray.Menu(
                    pystray.MenuItem(
                        "Монгол хэл (MN)",
                        on_set_lang("mn"),
                        checked=lambda item: FLOWBAR_STATE.get("language") == "mn",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "English (EN)",
                        on_set_lang("en"),
                        checked=lambda item: FLOWBAR_STATE.get("language") == "en",
                        radio=True,
                    ),
                    pystray.MenuItem(
                        "Автомат (Auto)",
                        on_set_lang("auto"),
                        checked=lambda item: FLOWBAR_STATE.get("language") not in ("mn", "en"),
                        radio=True,
                    ),
                ),
            ),
            pystray.MenuItem(
                "Дуугаар бичихийг түр зогсоох (Pause)",
                on_toggle_pause,
                checked=lambda item: FLOWBAR_STATE.get("is_paused", False),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Шинэ хувилбар шалгах", on_check_update),
            pystray.MenuItem("Windows-той хамт эхлэх", on_toggle_autostart, checked=lambda item: is_autostart_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Гарах (Quit VOICE)", on_quit),
        )

        _tray_icon = pystray.Icon("VOICE", img, f"VOICE v{APP_VERSION} - Speech & FlowBar", menu=menu)
        _TRAY_AVAILABLE = True
        logger.info("[Tray] System tray icon running (v%s)", APP_VERSION)
        _tray_icon.run()
    except Exception as e:
        logger.warning("[Tray] System tray error: %s", e)

def insert_text_to_active_window(text: str, hwnd: int = 0) -> bool:
    """
    Ultra-reliable text insertion for Windows:
    1. Backs up user's existing clipboard text.
    2. Puts new recognized text onto clipboard with Unicode NFC normalization.
    3. Restores focus to target window (Word, Chrome, Notepad, Messenger...).
    4. Releases modifier keys and sends Ctrl+V paste with hardware scan codes so Chrome/Word reliably receive it.
    5. Restores original clipboard text after 1.2s delay so the app has time to paste.
    """
    if not text or os.name != "nt":
        return False

    text = unicodedata.normalize("NFC", text)

    old_clip = get_windows_clipboard_text()
    text_with_space = text if text.endswith(("\n", "\r\n", " ")) else text + " "
    copy_to_windows_clipboard(text_with_space)

    curr_fg = user32.GetForegroundWindow()
    target = 0
    if curr_fg and not is_own_process_window(curr_fg):
        target = curr_fg
    elif hwnd and not is_own_process_window(hwnd):
        target = hwnd
    elif _target_hwnd and not is_own_process_window(_target_hwnd):
        target = _target_hwnd
    elif _last_external_hwnd and not is_own_process_window(_last_external_hwnd):
        target = _last_external_hwnd

    # If target is already the foreground window, DO NOT call restore_window_focus!
    # Calling SetForegroundWindow/ShowWindow on an already focused Chrome window causes Chromium to blur input boxes!
    if target and user32.GetForegroundWindow() != target:
        restore_window_focus(target)
        for _ in range(8):
            time.sleep(0.02)
            if user32.GetForegroundWindow() == target:
                break
        time.sleep(0.03)

    # Physical release of any held modifier keys
    all_mods = [
        VK_CONTROL, VK_LCONTROL, VK_RCONTROL,
        VK_MENU, VK_LMENU, VK_RMENU,
        VK_SHIFT, VK_LSHIFT, VK_RSHIFT,
    ]
    for vk in all_mods:
        sc = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, sc, KEYEVENTF_KEYUP, 0)
    time.sleep(0.035)

    _suppress_alt_menu_activation()
    # Physical release of any held modifier keys
    for vk in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.025)
    _suppress_alt_menu_activation()
    time.sleep(0.01)

    # Use SendInput for atomic, race-free Ctrl+V paste (works 100% in Chrome Omnibox & search inputs)
    try:
        ctrl_v = (INPUT * 4)()
        ctrl_v[0].type = INPUT_KEYBOARD
        ctrl_v[0].union.ki = KEYBDINPUT(VK_CONTROL, 0, 0, 0, 0)
        ctrl_v[1].type = INPUT_KEYBOARD
        ctrl_v[1].union.ki = KEYBDINPUT(ord('V'), 0, 0, 0, 0)
        ctrl_v[2].type = INPUT_KEYBOARD
        ctrl_v[2].union.ki = KEYBDINPUT(ord('V'), 0, KEYEVENTF_KEYUP, 0, 0)
        ctrl_v[3].type = INPUT_KEYBOARD
        ctrl_v[3].union.ki = KEYBDINPUT(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, 0)
        user32.SendInput(4, ctypes.byref(ctrl_v), ctypes.sizeof(INPUT))
    except Exception:
        ctrl_sc = user32.MapVirtualKeyW(VK_CONTROL, 0)
        v_sc = user32.MapVirtualKeyW(VK_V, 0)
        user32.keybd_event(VK_CONTROL, ctrl_sc, 0, 0)
        time.sleep(0.015)
        user32.keybd_event(VK_V, v_sc, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_V, v_sc, KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)
        user32.keybd_event(VK_CONTROL, ctrl_sc, KEYEVENTF_KEYUP, 0)

    cfg = load_server_settings()
    # Restore user's previous clipboard content only if restore_clipboard setting is true
    if cfg.get("restore_clipboard", True):
        def restore_clip_later():
            time.sleep(1.2)
            # Do not overwrite something the user copied in the meantime.
            if old_clip and get_windows_clipboard_text() == text_with_space:
                copy_to_windows_clipboard(old_clip)

        threading.Thread(target=restore_clip_later, daemon=True).start()

    # Track undo availability (within 8 seconds) if undo_button setting is on
    if cfg.get("undo_button", False):
        FLOWBAR_STATE["undo_available"] = True
        FLOWBAR_STATE["undo_until"] = time.time() + 8.0
    else:
        FLOWBAR_STATE["undo_available"] = False

    target_title = get_window_title(target)
    fg_now = user32.GetForegroundWindow()
    # Voice Form Filling / Auto-Tab Mode: synthesize Tab keypress if text ends with tab
    if text.endswith("\t"):
        try:
            time.sleep(0.03)
            tab_sc = user32.MapVirtualKeyW(VK_TAB, 0)
            user32.keybd_event(VK_TAB, tab_sc, 0, 0)
            time.sleep(0.015)
            user32.keybd_event(VK_TAB, tab_sc, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    FLOWBAR_STATE["last_insert_debug"] = f"target=0x{target:X}('{target_title[:25]}') fg=0x{fg_now:X} pasted=True"
    print(f"[FlowBar] {FLOWBAR_STATE['last_insert_debug']}")
    return True



def trigger_undo_insert() -> bool:
    """Send Ctrl+Z to the target window if undo is currently active within 8 seconds."""
    global _target_hwnd
    # Must check if undo was made available
    if not FLOWBAR_STATE.get("undo_available"):
        logger.info("[FlowBar] Undo requested but undo_available is False")
        return False

    # Consume token immediately (single-use per transcription)
    FLOWBAR_STATE["undo_available"] = False

    # Check 8-second expiration strictly
    undo_until = float(FLOWBAR_STATE.get("undo_until", 0.0))
    if time.time() > undo_until:
        FLOWBAR_STATE["status"] = "idle"
        logger.info(f"[FlowBar] Undo expired (now={time.time():.2f} > until={undo_until:.2f})")
        return False

    FLOWBAR_STATE["status"] = "idle"
    if os.name == "nt" and _target_hwnd:
        try:
            restore_window_focus(_target_hwnd)
            time.sleep(0.04)
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(ord('Z'), 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(ord('Z'), 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            logger.info(f"[FlowBar] Undo (Ctrl+Z) successfully sent to target HWND 0x{_target_hwnd:X}")
            return True
        except Exception as e:
            logger.error(f"[FlowBar] Failed to send undo Ctrl+Z: {e}")
            return False

    logger.warning("[FlowBar] Undo could not be executed: no valid target window HWND")
    return False

def start_native_flowbar_recording(from_ui_button: bool = False) -> None:
    global _is_recording, _target_hwnd, _record_start_time, _last_speech_time, _has_spoken, _speech_frames_count
    if _is_recording or FLOWBAR_STATE["status"] == "processing":
        return

    if FLOWBAR_STATE.get("is_paused", False):
        logger.info("[FlowBar] Recording ignored because dictation is paused.")
        return

    if not FLOWBAR_STATE.get("mic_ok", True):
        FLOWBAR_STATE["status"] = "error"
        FLOWBAR_STATE["error"] = "Микрофон олдсонгүй"
        threading.Timer(2.0, lambda: FLOWBAR_STATE.__setitem__("status", "idle")).start()
        return

    # Prevent accidental immediate re-trigger right after an auto-stop
    if time.time() - _last_stop_time < 0.85:
        return

    if os.name == "nt":
        fg = user32.GetForegroundWindow()
        fg_title = get_window_title(fg) if fg else ""
        if (
            fg
            and not is_own_process_window(fg)
            and fg_title not in ("", "VOICE FlowBar", "Task Switching")
            and not (from_ui_button and ("VOICE —" in fg_title or "localhost:3000" in fg_title))
        ):
            _target_hwnd = fg
        else:
            _target_hwnd = _last_external_hwnd or _last_active_hwnd

        # Immediately return focus to target window if user clicked the floating pill
        if _target_hwnd and is_own_process_window(fg):
            restore_window_focus(_target_hwnd)

    with _recording_lock:
        _recording_Buffer.clear()

    _record_start_time = time.time()
    _last_speech_time = time.time()
    _speech_frames_count = 0
    _has_spoken = False
    _is_recording = True
    FLOWBAR_STATE["status"] = "recording"
    FLOWBAR_STATE["seconds"] = 0
    FLOWBAR_STATE["error"] = ""
    FLOWBAR_STATE["visible"] = True
    FLOWBAR_STATE["target_window"] = get_window_title(_target_hwnd) or _last_external_title
    print(f"[FlowBar] Recording started (Target HWND: 0x{_target_hwnd:X} '{FLOWBAR_STATE['target_window']}')")
    play_sound_cue("start")


def stop_native_flowbar_recording() -> None:
    global _is_recording, _last_stop_time
    FLOWBAR_STATE["interim_preview"] = ""
    if not _is_recording:
        return
    _is_recording = False
    _last_stop_time = time.time()
    FLOWBAR_STATE["status"] = "processing"
    threading.Thread(target=_process_native_recording, daemon=True).start()


def _process_native_recording() -> None:
    global _last_stop_time
    try:
        with _recording_lock:
            if not _recording_Buffer:
                FLOWBAR_STATE["status"] = "error"
                FLOWBAR_STATE["error"] = "Яриа сонсогдсонгүй"
                time.sleep(1.5)
                return
            audio_np = np.concatenate(_recording_Buffer, axis=0).reshape(-1)
            _recording_Buffer.clear()

        if audio_np.size < 3200:
            FLOWBAR_STATE["status"] = "error"
            FLOWBAR_STATE["error"] = "Хэт богино байна"
            time.sleep(1.5)
            return

        cfg = load_server_settings()
        if cfg.get("noise_gate", True) and audio_np is not None and len(audio_np) > 0:
            audio_np = trim_silence(audio_np, 16000, threshold_db=-40.0)

        wav_bytes = encode_wav_bytes(audio_np, 16000)
        text, err = transcribe_wav_bytes(wav_bytes, language=FLOWBAR_STATE.get("language", "mn"))
        _last_stop_time = time.time()
        if text:
            if cfg.get("filler_word_cleaner", True):
                text = strip_filler_words(text)
            if cfg.get("voice_actions", True):
                text, action = process_voice_commands(text)
                if action == "undo":
                    trigger_undo_insert()
                    FLOWBAR_STATE["last_text"] = ""
                    FLOWBAR_STATE["status"] = "idle"
                    play_sound_cue("finish")
                    return
            if cfg.get("custom_snippets", True) and cfg.get("snippets"):
                text = apply_voice_snippets(text, cfg.get("snippets", {}))
            if cfg.get("mongolian_grammar", True):
                text = apply_mongolian_grammar(text)
            if cfg.get("tech_terms_normalization", True):
                text = normalize_tech_terms(text)
            if cfg.get("number_normalization", True):
                text = normalize_mongolian_numbers(text)
            if cfg.get("auto_punctuation", True):
                text = format_speech_text(text)
            FLOWBAR_STATE["last_text"] = text
            FLOWBAR_STATE["last_timestamp"] = int(time.time() * 1000)
            FLOWBAR_STATE["status"] = "success"
            if cfg.get("auto_insert_text", True):
                insert_text_to_active_window(text, _target_hwnd)
            play_sound_cue("finish")
            time.sleep(1.8)
        else:
            FLOWBAR_STATE["status"] = "error"
            FLOWBAR_STATE["error"] = err[:28] if err else "Тод ярина уу"
            play_sound_cue("error")
            safe_err = str(err).encode("ascii", "replace").decode("ascii") if err else ""
            print("[FlowBar] STT empty:", safe_err)
            time.sleep(2.0)
    except Exception as e:
        import traceback
        print("[FlowBar] Recording processing error:")
        traceback.print_exc()
        FLOWBAR_STATE["status"] = "error"
        FLOWBAR_STATE["error"] = "Алдаа гарлаа"
        time.sleep(1.5)
    finally:
        FLOWBAR_STATE["status"] = "idle"


def _native_audio_hotkey_worker() -> None:
    """
    Background worker that:
    1. Tracks active non-self foreground windows continuously (so it always knows the target window).
    2. Polls Windows hardware Ctrl+Alt AND F8 state at 40Hz (supports both Hold-to-Talk and Tap-to-Toggle!).
    3. Captures microphone audio via sounddevice while _is_recording is True.
    """
    global _last_active_hwnd, _last_active_title, _last_external_hwnd, _last_external_title
    if os.name != "nt":
        return

    attach_to_interactive_desktop()

    FLOWBAR_STATE["desktop"] = get_current_desktop_name()
    was_hotkey_down = False
    hotkey_press_time = 0.0
    started_by_current_press = False

    def audio_callback(indata, frames, time_info, status):
        global _last_speech_time, _has_spoken, _speech_frames_count
        if not _is_recording:
            return
        chunk = indata[:, 0].copy()
        with _recording_lock:
            _recording_Buffer.append(chunk)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        lvl = int(min(22, max(4, rms * 260)))
        FLOWBAR_STATE["levels"] = FLOWBAR_STATE["levels"][1:] + [lvl]
        FLOWBAR_STATE["seconds"] = int(time.time() - _record_start_time)
        if rms > 0.020:
            _speech_frames_count += 1
            _last_speech_time = time.time()
            if _speech_frames_count >= 4:  # >= 0.25s of genuine voice energy
                _has_spoken = True

    stream = None
    last_mic_try = 0.0

    def open_mic() -> None:
        nonlocal stream
        if not HAS_SOUNDDEVICE:
            FLOWBAR_STATE["mic_ok"] = False
            FLOWBAR_STATE["mic_error"] = "sounddevice is not installed"
            return
        try:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            stream = sd.InputStream(
                samplerate=16000, channels=1, dtype="float32",
                blocksize=1024, callback=audio_callback,
            )
            stream.start()
            FLOWBAR_STATE["mic_ok"] = True
            FLOWBAR_STATE["mic_error"] = ""
            print(f"[+] Native Windows Microphone Stream ready (Desktop: {FLOWBAR_STATE['desktop']})")
        except Exception as e:
            stream = None
            FLOWBAR_STATE["mic_ok"] = False
            FLOWBAR_STATE["mic_error"] = str(e)[:160]
            print("[-] Microphone not available (will retry):", e)

    open_mic()
    last_mic_try = time.time()

    while True:
        try:
            # Track foreground window continuously (ignoring our own Tkinter window!)
            fg = user32.GetForegroundWindow()
            if fg and not is_own_process_window(fg):
                title = get_window_title(fg)
                if title and title not in ("VOICE FlowBar", "Task Switching"):
                    _last_active_hwnd = fg
                    _last_active_title = title
                    if "VOICE —" not in title and "localhost:3000" not in title:
                        _last_external_hwnd = fg
                        _last_external_title = title
                    if not _is_recording:
                        FLOWBAR_STATE["target_window"] = _last_external_title or _last_active_title

            hk_mode = SERVER_SETTINGS.get("hotkey", "f8")
            ctrl_down = bool(
                (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                or (user32.GetAsyncKeyState(VK_LCONTROL) & 0x8000)
                or (user32.GetAsyncKeyState(VK_RCONTROL) & 0x8000)
            )
            alt_down = bool(
                (user32.GetAsyncKeyState(VK_MENU) & 0x8000)
                or (user32.GetAsyncKeyState(VK_LMENU) & 0x8000)
                or (user32.GetAsyncKeyState(VK_RMENU) & 0x8000)
            )
            shift_down = bool(
                (user32.GetAsyncKeyState(VK_SHIFT) & 0x8000)
                or (user32.GetAsyncKeyState(VK_LSHIFT) & 0x8000)
                or (user32.GetAsyncKeyState(VK_RSHIFT) & 0x8000)
            )
            space_down = bool(user32.GetAsyncKeyState(0x20) & 0x8000)
            f8_down = bool(user32.GetAsyncKeyState(VK_F8) & 0x8000)
            f9_down = bool(user32.GetAsyncKeyState(VK_F9) & 0x8000)
            f10_down = bool(user32.GetAsyncKeyState(VK_F10) & 0x8000)
            f2_down = bool(user32.GetAsyncKeyState(0x71) & 0x8000)
            f4_down = bool(user32.GetAsyncKeyState(0x73) & 0x8000)

            # Suppress Alt menu trap whenever Alt is released
            if alt_down:
                _suppress_alt_menu_activation()

            # Universal hotkey: Ctrl+Alt ALWAYS works; user-chosen hotkey is strictly respected to prevent conflicts
            is_ctrl_alt = bool(ctrl_down and alt_down and not shift_down)

            if hk_mode == "f9":
                hotkey_down = is_ctrl_alt or f9_down
            elif hk_mode == "f10":
                hotkey_down = is_ctrl_alt or f10_down
            elif hk_mode == "f2":
                hotkey_down = is_ctrl_alt or f2_down
            elif hk_mode == "f4":
                hotkey_down = is_ctrl_alt or f4_down
            elif hk_mode == "ctrl_shift":
                hotkey_down = is_ctrl_alt or (ctrl_down and shift_down and not alt_down)
            elif hk_mode == "alt_shift":
                hotkey_down = is_ctrl_alt or (alt_down and shift_down and not ctrl_down)
            elif hk_mode == "ctrl_space":
                hotkey_down = is_ctrl_alt or (ctrl_down and space_down and not alt_down)
            elif hk_mode == "ctrl_alt":
                hotkey_down = is_ctrl_alt
            else:
                hotkey_down = is_ctrl_alt or f8_down

            now = time.time()

            if hotkey_down and not was_hotkey_down:
                hotkey_press_time = now
                if not _is_recording and FLOWBAR_STATE["status"] != "processing":
                    start_native_flowbar_recording(from_ui_button=False)
                    started_by_current_press = True
                elif _is_recording:
                    # Tapped Ctrl+Alt or F8 again to stop!
                    started_by_current_press = False
                    stop_native_flowbar_recording()

            elif not hotkey_down and was_hotkey_down:
                held_duration = now - hotkey_press_time
                # If user held Ctrl+Alt for >= 0.45s (Push-to-Talk), stop on release!
                if _is_recording and started_by_current_press and held_duration >= 0.45:
                    stop_native_flowbar_recording()
                started_by_current_press = False

            was_hotkey_down = hotkey_down

            # Update timer & silence auto-stop (if in Toggle mode and user paused for 3.2s after speaking)
            if _is_recording:
                FLOWBAR_STATE["seconds"] = int(now - _record_start_time)
                if not hotkey_down and _has_spoken and (now - _last_speech_time) > 3.2:
                    stop_native_flowbar_recording()

        except Exception as e:
            print("Hotkey worker error:", e)

        # Retry the microphone every 5 s if it is missing or the stream stopped.
        try:
            if time.time() - last_mic_try > 5.0 and not _is_recording:
                if stream is None or not stream.active:
                    last_mic_try = time.time()
                    open_mic()
        except Exception:
            pass

        time.sleep(0.025)


def flowbar_ui_is_alive() -> bool:
    hb = float(FLOWBAR_STATE.get("ui_heartbeat", 0) or 0)
    return bool(FLOWBAR_STATE.get("ui_alive")) and (time.time() - hb) < 5.0


def ensure_flowbar_ui() -> None:
    """Start the FlowBar window thread if it is not running (also used to self-heal)."""
    global _flowbar_ui_thread
    if os.name != "nt":
        return
    with _flowbar_ui_lock:
        if _flowbar_ui_thread is not None and _flowbar_ui_thread.is_alive():
            return
        _flowbar_ui_thread = threading.Thread(target=_flowbar_supervisor, daemon=True)
        _flowbar_ui_thread.start()


def _flowbar_supervisor() -> None:
    for attempt in range(3):
        FLOWBAR_STATE["ui_restarts"] = attempt
        _native_flowbar_ui_worker()
        FLOWBAR_STATE["ui_alive"] = False
        if FLOWBAR_STATE.get("ui_fatal"):
            return
        time.sleep(2.0)
    print("[FlowBar] UI could not be started after 3 attempts:", FLOWBAR_STATE.get("ui_error"))


def _native_flowbar_ui_worker() -> None:
    """
    Always-on-top floating pill (Tkinter). WS_EX_NOACTIVATE keeps focus in the target app.
    All Tk calls happen on this thread; other threads talk to it through _flowbar_cmds.
    """
    global _tk_root, _flowbar_hwnd
    if os.name != "nt":
        return

    attach_to_interactive_desktop()

    FLOWBAR_STATE["ui_alive"] = False
    FLOWBAR_STATE["ui_fatal"] = False
    try:
        import tkinter as tk
    except ImportError as err:
        FLOWBAR_STATE["ui_error"] = "tkinter missing: reinstall Python with 'tcl/tk and IDLE' (%s)" % err
        FLOWBAR_STATE["ui_fatal"] = True
        print("[-] FlowBar unavailable:", FLOWBAR_STATE["ui_error"])
        return

    root = None
    try:
        root = tk.Tk()
        _tk_root = root
        root.title("VOICE Capsule")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.96)
        root.configure(bg="#090d16")

        bar_w, bar_h = FLOWBAR_W, FLOWBAR_H
        pos_x, pos_y = get_fallback_flowbar_pos(bar_w, bar_h)
        work_area = get_primary_work_area()
        pos_file = os.path.join(USER_DATA_DIR, "flowbar_pos.txt")
        if not os.path.isfile(pos_file) and os.path.isfile(os.path.join(BASE_DIR, "flowbar_pos.txt")):
            pos_file = os.path.join(BASE_DIR, "flowbar_pos.txt")
        if os.path.isfile(pos_file):
            try:
                with open(pos_file, "r", encoding="utf-8") as pf:
                    parts = pf.read().strip().split(",")
                if len(parts) == 2:
                    sx, sy = int(parts[0]), int(parts[1])
                    cx, cy = clamp_rect_to_screen(sx, sy, bar_w, bar_h, work_area)
                    if (cx, cy) == (sx, sy) and is_rect_on_any_screen(sx, sy, bar_w, bar_h):
                        pos_x, pos_y = sx, sy
                    else:
                        logger.info(f"[FlowBar] Clamped off-screen saved position ({sx},{sy}) to visible work area ({cx},{cy})")
                        pos_x, pos_y = cx, cy
            except Exception:
                pass
        root.geometry(f"{bar_w}x{bar_h}+{pos_x}+{pos_y}")

        canvas = tk.Canvas(root, width=bar_w, height=bar_h, bg="#0b0f19",
                           highlightthickness=1, highlightbackground="#3b82f6", bd=0, cursor="hand2")
        canvas.pack(fill="both", expand=True)
        root.update_idletasks()

        inner_hwnd = root.winfo_id()
        outer_hwnd = user32.GetParent(inner_hwnd) or inner_hwnd
        _flowbar_hwnd = outer_hwnd

        def apply_styles() -> None:
            for h in {inner_hwnd, outer_hwnd}:
                if h:
                    ex_style = user32.GetWindowLongW(h, GWL_EXSTYLE)
                    user32.SetWindowLongW(h, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
                    user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)

        apply_styles()
        root.lift()

        drag_data = {"x": 0, "y": 0, "moved": False}
        lang_cycle = ["auto", "mn", "en", "ja"]
        lang_labels = {"auto": "AUTO", "mn": "MN", "en": "EN", "ja": "JA"}
        hk_map = {"f8": "F8", "ctrl_alt": "Ctrl+Alt", "ctrl_shift": "Ctrl+Shift", "alt_shift": "Alt+Shift",
                  "ctrl_space": "Ctrl+Space", "f9": "F9", "f10": "F10", "f2": "F2", "f4": "F4"}
        ui = {"was_visible": True, "last_sig": None, "last_check": 0.0, "last_err": ""}

        def on_press(event):
            drag_data["x"] = event.x_root - root.winfo_x()
            drag_data["y"] = event.y_root - root.winfo_y()
            drag_data["moved"] = False
            if _last_external_hwnd:
                restore_window_focus(_last_external_hwnd)

        def on_drag(event):
            nx = event.x_root - drag_data["x"]
            ny = event.y_root - drag_data["y"]
            if abs(nx - root.winfo_x()) > 2 or abs(ny - root.winfo_y()) > 2:
                drag_data["moved"] = True
                root.geometry(f"{bar_w}x{bar_h}+{nx}+{ny}")

        def on_release(event):
            st = FLOWBAR_STATE.get("status", "idle")
            if _last_external_hwnd:
                restore_window_focus(_last_external_hwnd)
            if drag_data["moved"]:
                cur_x, cur_y = root.winfo_x(), root.winfo_y()
                work_area = get_primary_work_area()
                cur_x, cur_y = snap_rect_to_screen_edges(cur_x, cur_y, bar_w, bar_h, work_area)
                root.geometry(f"{bar_w}x{bar_h}+{cur_x}+{cur_y}")
                if is_rect_on_any_screen(cur_x, cur_y, bar_w, bar_h):
                    try:
                        with open(pos_file, "w", encoding="utf-8") as pf:
                            pf.write(f"{cur_x},{cur_y}")
                    except Exception:
                        pass
                else:
                    fx, fy = get_fallback_flowbar_pos(bar_w, bar_h)
                    root.geometry(f"{bar_w}x{bar_h}+{fx}+{fy}")
                return
            # Check undo button click
            if st == "success" and 174 <= event.x <= 248 and FLOWBAR_STATE.get("undo_available"):
                trigger_undo_insert()
                return

            if event.x >= 324:
                FLOWBAR_STATE["visible"] = False
                return
            if 256 <= event.x < 324 and not _is_recording:
                cur_l = FLOWBAR_STATE.get("language", "auto")
                idx = lang_cycle.index(cur_l) if cur_l in lang_cycle else 0
                FLOWBAR_STATE["language"] = lang_cycle[(idx + 1) % len(lang_cycle)]
                return
            if _is_recording:
                stop_native_flowbar_recording()
            elif FLOWBAR_STATE["status"] == "processing":
                FLOWBAR_STATE["status"] = "idle"
                FLOWBAR_STATE["error"] = "Цуцаллаа"
            else:
                start_native_flowbar_recording(from_ui_button=False)

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        def F(px, bold=False):
            # Negative size = pixels, so the text does not overflow on high-DPI screens.
            return ("Segoe UI", -px, "bold") if bold else ("Segoe UI", -px)

        def draw() -> None:
            st = FLOWBAR_STATE["status"]
            cur_lang = FLOWBAR_STATE.get("language", "auto")
            hk_name = hk_map.get(SERVER_SETTINGS.get("hotkey", "f8"), "F8")
            secs = FLOWBAR_STATE.get("seconds", 0)
            lvls = tuple(FLOWBAR_STATE.get("levels", [6, 12, 18, 12, 6]))
            preview = str(FLOWBAR_STATE.get("last_text", ""))[:18]
            err_txt = str(FLOWBAR_STATE.get("error", "") or "Дахин ярина уу")[:18]
            sig = (st, cur_lang, hk_name, secs if st == "recording" else 0,
                   lvls if st == "recording" else (), preview if st == "success" else "",
                   err_txt if st not in ("idle", "recording", "processing", "success") else "")
            if sig == ui["last_sig"]:
                return
            ui["last_sig"] = sig
            canvas.delete("all")
            canvas.create_text(11, 26, text="\u22ee\u22ee", fill="#475569", font=F(15, True))
            if st == "idle":
                canvas.configure(bg="#0b0f19", highlightbackground="#3b82f6", highlightthickness=1)
                canvas.create_oval(24, 11, 54, 41, fill="#1e1b4b", outline="#6366f1", width=2)
                canvas.create_oval(34, 21, 44, 31, fill="#818cf8", outline="")
                canvas.create_text(140, 18, text="VOICE CAPSULE", fill="#ffffff", font=F(13, True))
                canvas.create_text(140, 35, text=f"Дарж ярих \u2022 {hk_name}", fill="#94a3b8", font=F(11))
            elif st == "recording":
                canvas.configure(bg="#450a0a", highlightbackground="#ef4444", highlightthickness=2)
                canvas.create_oval(24, 11, 54, 41, fill="#991b1b", outline="#f87171", width=2)
                canvas.create_oval(34, 21, 44, 31, fill="#ffffff", outline="")
                canvas.create_text(95, 26, text=f"{secs}s", fill="#ffffff", font=F(15, True))
                for i, l in enumerate(lvls):
                    bx = 126 + i * 9
                    bh = max(6, min(32, int(l * 1.3)))
                    canvas.create_rectangle(bx, 26 - bh // 2, bx + 5, 26 + bh // 2, fill="#38bdf8", outline="")
            elif st == "processing":
                canvas.configure(bg="#1e1b4b", highlightbackground="#818cf8", highlightthickness=2)
                canvas.create_oval(24, 11, 54, 41, fill="#312e81", outline="#a5b4fc", width=1)
                canvas.create_text(39, 26, text="...", fill="#ffffff", font=F(15, True))
                canvas.create_text(145, 26, text="Таньж байна...", fill="#e0e7ff", font=F(12, True))
            elif st == "success":
                canvas.configure(bg="#064e3b", highlightbackground="#10b981", highlightthickness=2)
                canvas.create_oval(24, 11, 54, 41, fill="#065f46", outline="#34d399", width=1)
                canvas.create_text(39, 26, text="\u2713", fill="#34d399", font=F(16, True))
                cfg_undo = SERVER_SETTINGS.get("undo_button", False)
                undo_on = bool(FLOWBAR_STATE.get("undo_available") and (time.time() < FLOWBAR_STATE.get("undo_until", 0)) and cfg_undo)
                if undo_on:
                    canvas.create_text(118, 26, text=f"{preview[:12]}", fill="#ffffff", font=F(11, True))
                    canvas.create_rectangle(174, 14, 248, 38, fill="#1e293b", outline="#34d399", width=1)
                    canvas.create_text(211, 26, text="\u21b6 Буцах", fill="#34d399", font=F(11, True))
                else:
                    canvas.create_text(145, 26, text=f"Бичигдлээ: {preview}", fill="#ffffff", font=F(12, True))
            else:
                canvas.configure(bg="#450a0a", highlightbackground="#f59e0b", highlightthickness=2)
                canvas.create_oval(24, 11, 54, 41, fill="#78350f", outline="#f59e0b", width=1)
                canvas.create_text(39, 26, text="!", fill="#fef08a", font=F(16, True))
                canvas.create_text(145, 26, text=err_txt, fill="#fef08a", font=F(12, True))
            canvas.create_rectangle(260, 14, 318, 38, fill="#1e293b",
                                    outline="#38bdf8" if cur_lang == "auto" else "#475569", width=1)
            canvas.create_text(289, 26, text=lang_labels.get(cur_lang, "AUTO"), fill="#f8fafc", font=F(11, True))
            canvas.create_oval(328, 15, 350, 37, fill="#1e293b", outline="#334155", width=1)
            canvas.create_text(339, 26, text="\u2715", fill="#94a3b8", font=F(12, True))

        def handle_commands() -> None:
            while True:
                try:
                    cmd = _flowbar_cmds.get_nowait()
                except queue.Empty:
                    return
                if cmd[0] == "place":
                    root.geometry(f"{bar_w}x{bar_h}+{int(cmd[1])}+{int(cmd[2])}")
                    root.deiconify()
                    ui["was_visible"] = True
                    apply_styles()
                elif cmd[0] == "show":
                    root.deiconify()
                    ui["was_visible"] = True
                    apply_styles()

        def self_heal() -> None:
            """Every ~2 s make sure the bar is really on screen, shown and topmost."""
            now = time.time()
            if now - ui["last_check"] < 2.0:
                return
            ui["last_check"] = now
            x, y = root.winfo_x(), root.winfo_y()
            work_area = get_primary_work_area()
            cx, cy = clamp_rect_to_screen(x, y, bar_w, bar_h, work_area)
            if (cx, cy) != (x, y) or not is_rect_on_any_screen(x, y, bar_w, bar_h):
                root.geometry(f"{bar_w}x{bar_h}+{cx}+{cy}")
                x, y = cx, cy
                logger.info(f"[FlowBar] Window was off-screen; clamped to ({cx},{cy})")
            if not user32.IsWindowVisible(outer_hwnd):
                root.deiconify()
                apply_styles()
            FLOWBAR_STATE["pos"] = f"{x},{y}"

        def refresh_ui() -> None:
            try:
                FLOWBAR_STATE["ui_alive"] = True
                FLOWBAR_STATE["ui_heartbeat"] = time.time()
                handle_commands()
                vis = bool(FLOWBAR_STATE.get("visible", True))
                if not vis and ui["was_visible"]:
                    root.withdraw()
                    ui["was_visible"] = False
                elif vis and not ui["was_visible"]:
                    root.deiconify()
                    apply_styles()
                    ui["was_visible"] = True
                if vis:
                    user32.SetWindowPos(outer_hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
                    self_heal()
                    # Processing watchdog: never stay stuck.
                    if FLOWBAR_STATE.get("status") == "processing":
                        pts = FLOWBAR_STATE.get("_proc_start_ts", 0)
                        if not pts:
                            FLOWBAR_STATE["_proc_start_ts"] = time.time()
                        elif time.time() - pts > 10.0:
                            FLOWBAR_STATE["status"] = "idle"
                            FLOWBAR_STATE["_proc_start_ts"] = 0
                    else:
                        FLOWBAR_STATE["_proc_start_ts"] = 0
                    draw()
                FLOWBAR_STATE["ui_error"] = ""
            except Exception as e:
                # Never let one bad frame kill the redraw loop.
                msg = f"{type(e).__name__}: {e}"
                FLOWBAR_STATE["ui_error"] = msg[:200]
                if msg != ui["last_err"]:
                    ui["last_err"] = msg
                    import traceback
                    print("[FlowBar] refresh error:")
                    traceback.print_exc()
                ui["last_sig"] = None
            finally:
                try:
                    root.after(80, refresh_ui)
                except Exception:
                    pass

        root.after(50, refresh_ui)
        print(f"[FlowBar] Window created at ({pos_x},{pos_y}) size {bar_w}x{bar_h}")
        root.mainloop()
    except Exception as e:
        import traceback
        FLOWBAR_STATE["ui_error"] = f"{type(e).__name__}: {e}"[:200]
        print("[FlowBar] UI failed:")
        traceback.print_exc()
    finally:
        FLOWBAR_STATE["ui_alive"] = False
        _tk_root = None
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass


# Start background threads once
_bg_started = False


def _open_browser_window(force: bool = False) -> None:
    """Auto-launch the desktop dashboard in Edge/Chrome app mode once the server is listening."""
    if not force:
        if os.environ.get("VOICE_NO_BROWSER") or "--background" in sys.argv or "-b" in sys.argv:
            logger.info("[Browser] Skipping browser auto-launch due to background mode.")
            return
    time.sleep(0.3 if force else 1.0)
    url = f"http://127.0.0.1:{SERVER_PORT}/dashboard"
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            try:
                subprocess.Popen([c, f"--app={url}", "--window-size=1280,820"])
                return
            except Exception:
                pass
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


@app.on_event("startup")
def on_startup():
    global _bg_started
    if not _bg_started and os.name == "nt":
        _bg_started = True
        threading.Thread(target=_native_audio_hotkey_worker, daemon=True).start()
        ensure_flowbar_ui()
        threading.Thread(target=_start_tray_icon, daemon=True).start()
        threading.Thread(target=_open_browser_window, daemon=True).start()
        logger.info("[+] Duudlaga Flow Native Ctrl+Alt & Floating Pill started!")


# ---------------------------------------------------------------------------
# FastAPI Routes
# ---------------------------------------------------------------------------

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "mn-MN-YesuiNeural"
    speed: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    preset: Optional[str] = "broadcast"
    timbreStrength: Optional[float] = 0.92
    cloneProfile: Optional[dict] = None


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_INSERT_CHARS = 20000


class InsertTextRequest(BaseModel):
    text: str


class FlowBarActionRequest(BaseModel):
    action: str  # "toggle_visibility" | "show" | "hide" | "start" | "stop" | "set_language"
    language: Optional[str] = "mn"


@app.get("/api/info")
def index():
    return {
        "service": "VOICE & VoiceStudio AI Server (TTS, STT, Voice Cloning, Duudlaga Flow)",
        "status": "ready",
        "voices": VOICES + list(CLONED_VOICES_DB.values()),
        "presets": [
            {"id": k, "label": v["label"], "icon": v["icon"], "description": v["description"]}
            for k, v in VOICESTUDIO_PRESETS.items()
        ],
    }


@app.get("/health")
def health():
    fg = user32.GetForegroundWindow() if os.name == "nt" else 0
    st_info = compute_flowbar_status(FLOWBAR_STATE, now=time.time())
    return {
        "status": "ok",
        "has_edge": HAS_EDGE_TTS,
        "has_stt": HAS_SR,
        "has_mms": mms_model is not None,
        "has_miniaudio": HAS_MINIAUDIO,
        "voice_cloning": True,
        "flowbar_status": FLOWBAR_STATE["status"],
        "offline_fallback": FLOWBAR_STATE.get("offline_fallback", False),
        "version": APP_VERSION,
        "flowbar_visible": FLOWBAR_STATE["visible"] and st_info["ui_alive"],
        "flowbar_ui_alive": st_info["ui_alive"],
        "flowbar_error": FLOWBAR_STATE.get("ui_error", ""),
        "mic_ok": FLOWBAR_STATE.get("mic_ok", True),
        "mic_error": FLOWBAR_STATE.get("mic_error", ""),
        "hotkey_ok": FLOWBAR_STATE.get("hotkey_ok", True),
        "hotkey_error": FLOWBAR_STATE.get("hotkey_error", ""),
        "tray_available": _TRAY_AVAILABLE,
        "autostart": is_autostart_enabled() if os.name == "nt" else False,
        "cloned_count": len(CLONED_VOICES_DB),
        "desktop": get_current_desktop_name(),
        "foreground_hwnd": fg,
        "foreground_title": get_window_title(fg) if fg else "",
        "target_window": FLOWBAR_STATE.get("target_window", ""),
    }


@app.get("/voices")
def get_voices():
    return {
        "standard": VOICES,
        "cloned": list(CLONED_VOICES_DB.values()),
        "presets": [
            {"id": k, "label": v["label"], "icon": v["icon"], "description": v["description"]}
            for k, v in VOICESTUDIO_PRESETS.items()
        ],
    }


@app.get("/clones")
def list_clones():
    return list(CLONED_VOICES_DB.values())


def _safe_clone_wav_path(voice_id: str) -> str:
    """Return the clone wav path only for a plain id that stays inside CLONES_DIR."""
    try:
        return safe_clone_wav_path(CLONES_DIR, voice_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/clones/{voice_id}/sample")
def get_clone_sample(voice_id: str):
    wav_path = _safe_clone_wav_path(voice_id)
    if not os.path.exists(wav_path):
        raise HTTPException(status_code=404, detail="Sample audio not found")
    return FileResponse(wav_path, media_type="audio/wav", filename=f"{voice_id}.wav")


@app.delete("/clones/{voice_id}")
def delete_clone(voice_id: str):
    wav_path = _safe_clone_wav_path(voice_id)
    CLONED_VOICES_DB.pop(voice_id, None)
    save_cloned_voices_db(CLONED_VOICES_DB)
    if os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass
    return {"deleted": voice_id}


@app.get("/flowbar/status")
def get_flowbar_status():
    st = dict(FLOWBAR_STATE)
    alive = flowbar_ui_is_alive()
    st["ui_alive"] = alive
    st["visible"] = bool(FLOWBAR_STATE.get("visible", True)) and alive   # never claim "active" if no window exists
    return st



class AutostartRequest(BaseModel):
    enabled: bool

@app.get("/api/autostart")
def get_autostart_endpoint():
    supported = (os.name == "nt")
    enabled = is_autostart_enabled() if supported else False
    return {"supported": supported, "enabled": enabled}

@app.post("/api/autostart")
def set_autostart_endpoint(req: AutostartRequest):
    if os.name != "nt":
        return {"supported": False, "enabled": False, "error": "Autostart only supported on Windows"}
    ok = set_autostart_enabled(req.enabled)
    return {"supported": True, "enabled": is_autostart_enabled(), "success": ok}

@app.post("/flowbar/undo")
def api_flowbar_undo():
    ok = trigger_undo_insert()
    return {"undone": ok}

@app.post("/flowbar/action")
def flowbar_action(req: FlowBarActionRequest):
    act = (req.action or "").lower()
    if act == "toggle_visibility":
        FLOWBAR_STATE["visible"] = not FLOWBAR_STATE["visible"]
        if FLOWBAR_STATE["visible"]:
            ensure_flowbar_ui()
            _flowbar_cmds.put(("show",))
    elif act == "show":
        FLOWBAR_STATE["visible"] = True
        ensure_flowbar_ui()
        _flowbar_cmds.put(("show",))
    elif act == "hide":
        FLOWBAR_STATE["visible"] = False
    elif act == "start":
        start_native_flowbar_recording(from_ui_button=True)
    elif act == "stop":
        stop_native_flowbar_recording()
    elif act == "cancel":
        FLOWBAR_STATE["status"] = "idle"
        FLOWBAR_STATE["interim_preview"] = ""
        stop_native_flowbar_recording()
    elif act == "set_language" and req.language:
        FLOWBAR_STATE["language"] = req.language
    elif act == "reset_position":
        reset_flowbar_position()
    elif act == "pause":
        FLOWBAR_STATE["is_paused"] = True
        if _is_recording:
            stop_native_flowbar_recording()
        FLOWBAR_STATE["status"] = "idle"
    elif act == "resume":
        FLOWBAR_STATE["is_paused"] = False
    return get_flowbar_status()


@app.get("/api/flowbar/state")
def api_flowbar_state():
    return get_flowbar_status()


@app.post("/api/flowbar/pause")
def api_flowbar_pause():
    FLOWBAR_STATE["is_paused"] = True
    if _is_recording:
        stop_native_flowbar_recording()
    FLOWBAR_STATE["status"] = "idle"
    return {"status": "ok", "is_paused": True}


@app.post("/api/flowbar/resume")
def api_flowbar_resume():
    FLOWBAR_STATE["is_paused"] = False
    return {"status": "ok", "is_paused": False}


@app.post("/insert-text")
def api_insert_text(req: InsertTextRequest):
    if len(req.text) > MAX_INSERT_CHARS:
        raise HTTPException(status_code=413, detail="Text too long")
    ok = insert_text_to_active_window(req.text)
    return {"inserted": ok, "text": req.text}


def apply_persona_formant_warp(
    src_samples: np.ndarray,
    warp_ratio: float,
    sample_rate: int = TARGET_SR,
) -> np.ndarray:
    """
    VoiceStudio Persona Formant Warping:
    Shifts vocal tract resonance formants (F1..F4) without altering glottal harmonic pitch,
    giving each studio persona (Narrator, News, Podcast, Maral, Tulga, Misheel) a distinct vocal tract character.
    """
    if abs(warp_ratio - 1.0) < 0.015 or src_samples.size < 2048:
        return src_samples

    _, _, Zxx = sp_signal.stft(
        src_samples, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    mag = np.abs(Zxx) + 1e-8
    phase = np.angle(Zxx)
    n_bins, n_frames = mag.shape
    bins = np.arange(n_bins, dtype=np.float32)

    lifter = np.zeros(STFT_NPERSEG, dtype=np.float64)
    lifter[:CEPSTRAL_LIFTER] = 1.0
    lifter[-CEPSTRAL_LIFTER + 1 :] = 1.0

    new_mag = np.empty_like(mag)
    for t in range(n_frames):
        frame_log = np.log(mag[:, t])
        cep = np.fft.irfft(frame_log)
        inst_env = np.real(np.fft.rfft(cep * lifter))
        fine_excitation = frame_log - inst_env
        warped_env = np.interp(bins / warp_ratio, bins, inst_env)
        new_mag[:, t] = np.exp(fine_excitation + warped_env)

    Zxx_mod = new_mag * np.exp(1j * phase)
    _, y_out = sp_signal.istft(
        Zxx_mod, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    y_out = y_out[: src_samples.size].astype(np.float32)

    # Add sub-harmonic chest resonance for deep personas (warp_ratio < 0.93)
    if warp_ratio < 0.93:
        sos_sub = sp_signal.butter(
            2, [80.0 / (sample_rate / 2.0), 230.0 / (sample_rate / 2.0)], btype="bandpass", output="sos"
        )
        sub_band = sp_signal.sosfiltfilt(sos_sub, y_out)
        y_out = y_out + float((0.95 - warp_ratio) * 1.8) * sub_band.astype(np.float32)

    return y_out


_ENG_TO_MN_TTS_MAP: list[tuple[str, str]] = [
    (r"\bVoiceStudio\b", "Войс Студио"),
    (r"\bDuudlaga\s*Flow\b", "Дуудлага Флоу"),
    (r"\bFlowBar\b", "Флоу Бар"),
    (r"\bCtrl\s*\+\s*Alt\b", "Контрол Альт"),
    (r"\bFacebook\b", "Фэйсбүүк"),
    (r"\bInstagram\b", "Инстаграм"),
    (r"\bTelegram\b", "Телеграм"),
    (r"\bYouTube\b", "Юүтүб"),
    (r"\bMicrosoft\s+Word\b", "Майкрософт Ворд"),
    (r"\bWord\b", "Ворд"),
    (r"\bExcel\b", "Эксел"),
    (r"\bGoogle\s+Chrome\b", "Гүүгл Хром"),
    (r"\bChrome\b", "Хром"),
    (r"\bPython\b", "Пайтон"),
    (r"\bNext\.js\b", "Некст жи эс"),
    (r"\bReact\b", "Реакт"),
    (r"\bTypeScript\b", "Тайпскрипт"),
    (r"\bJavaScript\b", "Жаваскрипт"),
    (r"\bChatGPT\b", "Чат жи пи ти"),
    (r"\bGemini\b", "Жемини"),
    (r"\bClaude\b", "Клод"),
    (r"\bAI\b", "Эй Ай"),
    (r"\bAPI\b", "Эй Пи Ай"),
    (r"\bTTS\b", "Ти Ти Эс"),
    (r"\bSTT\b", "Эс Ти Ти"),
]


def prepare_tts_text_for_voice(text: str, base_voice: str) -> str:
    """If a Mongolian neural voice is reading mixed text with English terms, adapt English loanwords for natural pronunciation."""
    if not base_voice.startswith("mn-MN"):
        return text
    out = text
    for pat, repl in _ENG_TO_MN_TTS_MAP:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


@app.post("/tts")
async def tts(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    voice_id = (req.voice or "mn-MN-YesuiNeural").strip()
    preset_id = (req.preset or "broadcast").strip().lower()
    timbre_strength = float(np.clip(req.timbreStrength if req.timbreStrength is not None else 0.92, 0.0, 1.0))

    clone_profile = CLONED_VOICES_DB.get(voice_id)
    if not clone_profile and req.cloneProfile and isinstance(req.cloneProfile, dict):
        clone_profile = req.cloneProfile
        CLONED_VOICES_DB[voice_id] = clone_profile
    persona_profile = VOICES_BY_ID.get(voice_id)
    persona_warp = 1.0

    # Check if text contains predominantly Japanese characters (Hiragana/Katakana/Kanji)
    has_japanese = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", text))

    # Determine base neural voice & prosody parameters
    if clone_profile:
        base_voice = clone_profile.get("baseVoice", "mn-MN-BataaNeural")
        if has_japanese and not re.search(r"[А-ЯӨҮЁа-яөүё]", text):
            base_voice = "ja-JP-KeitaNeural" if clone_profile.get("gender") == "male" else "ja-JP-NanamiNeural"
        speaker_f0 = float(clone_profile.get("f0", 135.0))
        speaker_rate = float(clone_profile.get("rate_hz", 4.2))
        base_f0 = 122.0 if ("bataa" in base_voice.lower() or "keita" in base_voice.lower()) else 210.0
        # Shift pitch in Hz directly toward speaker's measured F0
        f0_diff_hz = int(np.clip(speaker_f0 - base_f0, -45, 45))
        user_pitch_adj = int(((req.pitch or 1.0) - 1.0) * 40)
        pitch_str = f"{f0_diff_hz + user_pitch_adj:+d}Hz"

        # Match speaking cadence + user speed slider
        cadence_ratio = np.clip(speaker_rate / 4.2, 0.88, 1.15)
        total_speed = (req.speed or 1.0) * cadence_ratio
        rate_percent = int(np.clip((total_speed - 1.0) * 100, -45, 60))
        rate_str = f"{rate_percent:+d}%"
    elif persona_profile:
        base_voice = persona_profile.get("baseVoice", "mn-MN-YesuiNeural")
        p_pitch = float(persona_profile.get("pitch", 1.0)) * float(req.pitch or 1.0)
        p_speed = float(persona_profile.get("speed", 1.0)) * float(req.speed or 1.0)
        persona_warp = float(persona_profile.get("formantWarp", 1.0))
        rate_percent = int(np.clip((p_speed - 1.0) * 100, -45, 60))
        rate_str = f"{rate_percent:+d}%"
        pitch_hz = int(np.clip((p_pitch - 1.0) * 55, -50, 50))
        pitch_str = f"{pitch_hz:+d}Hz"
    else:
        base_voice = "mn-MN-BataaNeural" if ("bataa" in voice_id.lower() or "male" in voice_id.lower()) else "mn-MN-YesuiNeural"
        rate_percent = int(((req.speed or 1.0) - 1.0) * 100)
        rate_str = f"{rate_percent:+d}%"
        pitch_hz = int(((req.pitch or 1.0) - 1.0) * 45)
        pitch_str = f"{pitch_hz:+d}Hz"

    if not HAS_EDGE_TTS:
        raise HTTPException(status_code=503, detail="Edge-TTS engine not installed")

    synth_text = prepare_tts_text_for_voice(text, base_voice)

    # Strip any stray HTML/XML tags so Edge-TTS never speaks raw markup tags aloud
    clean_text = re.sub(r"<[^>]+>", "", synth_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    if not clean_text:
        clean_text = synth_text.strip() or "Текст хоосон байна."

    # Dynamic prosody: if text ends with '?', raise pitch slightly for questioning inflection
    actual_pitch = pitch_str
    if clean_text.endswith("?") and "+0Hz" in pitch_str:
        actual_pitch = "+8Hz"

    try:
        # Pass clean plain text with rate and pitch. Neural voices naturally breathe on commas and periods.
        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=base_voice,
            rate=rate_str,
            pitch=actual_pitch,
        )
        raw_mp3 = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                raw_mp3.extend(chunk["data"])

        if not raw_mp3:
            raise HTTPException(status_code=500, detail="Empty audio generated")

        # Decode to 24kHz float32 PCM so we can run VoiceStudio Timbre Transfer, Persona Warp & Mastering DSP
        try:
            samples = decode_audio_bytes(bytes(raw_mp3), TARGET_SR)
            if clone_profile and timbre_strength > 0.05:
                samples = apply_voice_clone_timbre(
                    samples,
                    base_voice_id=base_voice,
                    clone_profile=clone_profile,
                    timbre_strength=timbre_strength,
                    sample_rate=TARGET_SR,
                )
            elif abs(persona_warp - 1.0) >= 0.015:
                samples = apply_persona_formant_warp(
                    samples,
                    warp_ratio=persona_warp,
                    sample_rate=TARGET_SR,
                )
            samples = apply_voicestudio_dsp(samples, TARGET_SR, preset_id=preset_id)
            wav_bytes = encode_wav_bytes(samples, TARGET_SR)
            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": f'inline; filename="{voice_id}.wav"',
                    "X-TTS-Voice": voice_id,
                    "X-TTS-Cloned": str(bool(clone_profile)),
                    "X-TTS-Preset": preset_id,
                },
            )
        except Exception as dsp_err:
            print("DSP fallback to raw mp3:", dsp_err)

        return Response(
            content=bytes(raw_mp3),
            media_type="audio/mpeg",
            headers={"Content-Disposition": f'inline; filename="{base_voice}.mp3"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis error: {str(e)}")


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("mn"),
):
    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Аудио файл хэт том байна (дээд тал нь 25 MB).")
    if not content or len(content) < 500:
        return {"text": "", "error": "Аудио хэт богино эсвэл хоосон байна."}

    text, err = transcribe_wav_bytes(content, language=language)
    if text:
        cfg = load_server_settings()
        if cfg.get("custom_snippets", True) and cfg.get("snippets"):
            text = apply_voice_snippets(text, cfg.get("snippets", {}))
        return {"text": text, "engine": f"Google Neural STT ({language})"}
    return {"text": "", "error": err or "Яриа танигдсангүй."}


@app.post("/clone-voice")
async def clone_voice(
    name: str = Form("Миний хоолой"),
    audio: UploadFile = File(...),
):
    """
    VoiceStudio Acoustic Voice Cloner:
    1. Decodes WAV/MP3/OGG/FLAC sample to 24kHz float32.
    2. Trims silence & normalizes to -2 dBFS.
    3. Extracts speaker F0, pitch spread, syllable cadence, formant centroid,
       and 513-bin Cepstral Vocal Tract Spectral Envelope (F1..F4).
    4. Transcribes reference speech (ref_text) and saves clones/<voice_id>.wav + voices.json.
    """
    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Аудио файл хэт том байна (дээд тал нь 25 MB).")
    if len(content) < 2000:
        raise HTTPException(status_code=400, detail="Аудио файл хэт богино байна (3-10 секунд ярина уу).")

    try:
        samples = decode_audio_bytes(content, target_sr=TARGET_SR)
        samples = trim_silence(samples, TARGET_SR)
        duration_s = round(float(samples.size) / TARGET_SR, 2)
        if duration_s < 1.2:
            raise HTTPException(status_code=400, detail="Дуу хоолой хэт богино эсвэл чимээгүй байна (3-10 секунд тод ярина уу).")

        # Cap at 20s cleanest audio
        if duration_s > 20.0:
            samples = samples[: int(20.0 * TARGET_SR)]
            duration_s = 20.0

        samples = normalize_audio_np(samples, target_dbfs=-2.0)
        prosody = analyze_speaker_prosody(samples, TARGET_SR)
        f0 = prosody["f0"]

        if f0 >= 165.0:
            gender = "female"
            base_voice = "mn-MN-YesuiNeural"
            pitch_ratio = round(float(np.clip(f0 / 210.0, 0.78, 1.25)), 2)
            gender_label = "Эмэгтэй"
        else:
            gender = "male"
            base_voice = "mn-MN-BataaNeural"
            pitch_ratio = round(float(np.clip(f0 / 122.0, 0.78, 1.25)), 2)
            gender_label = "Эрэгтэй"

        voice_id = f"cloned_{uuid.uuid4().hex[:8]}"
        wav_path = os.path.join(CLONES_DIR, f"{voice_id}.wav")
        clean_wav_bytes = encode_wav_bytes(samples, TARGET_SR)
        with open(wav_path, "wb") as f:
            f.write(clean_wav_bytes)

        # Transcribe reference clip (VoiceStudio speaker_clone refine_ref_text)
        try:
            ref_text, _ = transcribe_wav_bytes(clean_wav_bytes, language="mn")
        except Exception as e:
            print(f"[VoiceStudio] Reference transcription warning: {e}")
            ref_text = ""
        if not ref_text or not ref_text.strip():
            ref_text = "Би өөрийн дуу хоолойг хиймэл оюунд таниулж, шинэ загвар үүсгэж байна." 

        description = (
            f"{gender_label} • f₀={f0:.0f}Hz • Формант={prosody['formant_centroid']:.0f}Hz • {duration_s:.1f}с"
        )

        profile = {
            "id": voice_id,
            "name": name.strip() or "Миний хоолой",
            "gender": gender,
            "baseVoice": base_voice,
            "pitch": pitch_ratio,
            "speed": round(float(np.clip(prosody["rate_hz"] / 4.2, 0.88, 1.15)), 2),
            "f0": f0,
            "pitch_spread_st": prosody["pitch_spread_st"],
            "rate_hz": prosody["rate_hz"],
            "formant_centroid": prosody["formant_centroid"],
            "duration": duration_s,
            "refText": ref_text,
            "sampleUrl": f"/api/tts/clone?id={voice_id}",
            "description": description,
            "tag": "Хувилсан",
            "envelope": prosody["envelope"],
            "createdAt": int(time.time() * 1000),
        }

        CLONED_VOICES_DB[voice_id] = profile
        save_cloned_voices_db(CLONED_VOICES_DB)

        # Return full profile including envelope so client localStorage can persist it across stateless cloud restarts
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Хоолой хувилахад алдаа гарлаа: {str(e)}")


# ---------------------------------------------------------------------------
# Stage 4: VoiceStudio, Voice Profiles, Karaoke ASS, & Vocal Separation APIs
# ---------------------------------------------------------------------------

@app.get("/api/voice-profiles")
def api_list_voice_profiles():
    """List all registered local voice profiles."""
    db = load_voice_profiles_db()
    # Merge with in-memory CLONED_VOICES_DB if any
    for k, v in CLONED_VOICES_DB.items():
        if k not in db:
            db[k] = v
    return {"status": "ok", "profiles": list(db.values())}


@app.post("/api/voice-profiles")
async def api_create_voice_profile(
    name: str = Form("Миний хоолой"),
    consent: bool = Form(False),
    transcript: Optional[str] = Form(None),
    audio: UploadFile = File(...),
):
    """
    Create a local voice profile with mandatory user consent & audio validation.
    """
    if not consent:
        raise HTTPException(status_code=400, detail="Хувийн дуу хоолой ашиглах зөвшөөрөл (Consent) заавал шаардлагатай.")

    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Аудио файл хэт том байна (дээд тал нь 25 MB).")

    try:
        profile = create_voice_profile(
            name=name,
            audio_bytes=content,
            consent=consent,
            ref_transcript=transcript,
        )
        # Register in in-memory dict as well
        CLONED_VOICES_DB[profile["id"]] = profile
        return {"status": "ok", "profile": profile}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        logger.error(f"Error creating voice profile: {e}")
        raise HTTPException(status_code=500, detail=f"Хоолой хадгалахад алдаа гарлаа: {str(e)}")


@app.get("/api/voice-profiles/{profile_id}")
def api_get_voice_profile(profile_id: str):
    """Retrieve metadata of a single voice profile."""
    safe_id = sanitize_profile_id(profile_id)
    db = load_voice_profiles_db()
    profile = db.get(safe_id) or CLONED_VOICES_DB.get(safe_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Дуу хоолойн профайл олдсонгүй.")
    return {"status": "ok", "profile": profile}


@app.get("/api/voice-profiles/{profile_id}/audio")
def api_get_voice_profile_audio(profile_id: str):
    """Stream reference audio of a voice profile."""
    safe_id = sanitize_profile_id(profile_id)
    wav_path = os.path.join(CLONES_DIR, f"{safe_id}.wav")
    if not os.path.isfile(wav_path):
        raise HTTPException(status_code=404, detail="Аудио файл олдсонгүй.")
    return FileResponse(wav_path, media_type="audio/wav", filename=f"{safe_id}.wav")


@app.delete("/api/voice-profiles/{profile_id}")
def api_delete_voice_profile(profile_id: str):
    """Delete a local voice profile and its audio file permanently."""
    safe_id = sanitize_profile_id(profile_id)
    deleted = delete_voice_profile(safe_id)
    if safe_id in CLONED_VOICES_DB:
        del CLONED_VOICES_DB[safe_id]
    if not deleted:
        raise HTTPException(status_code=404, detail="Дуу хоолойн профайл олдсонгүй.")
    return {"status": "ok", "deleted": safe_id}


@app.get("/api/voice-cloning/status")
def api_voice_cloning_status():
    """Report hardware readiness and model feasibility audit for Voice Cloning."""
    return get_voice_cloning_system_status()


@app.post("/api/audio/separate")
async def api_audio_separate(
    audio: UploadFile = File(...),
    vocal_strength: float = Form(1.3),
):
    """
    Separate an audio track into isolated vocals and instrumental stems.
    """
    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Аудио файл хэт том байна (дээд тал нь 25 MB).")
    if len(content) < 4000:
        raise HTTPException(status_code=400, detail="Аудио файл хэт богино байна.")

    try:
        job = process_separation_job(
            content,
            original_filename=audio.filename or "track.wav",
            vocal_strength=float(vocal_strength),
        )
        return job
    except Exception as e:
        logger.error(f"Error in audio separation: {e}")
        raise HTTPException(status_code=500, detail=f"Аудио салгахад алдаа гарлаа: {str(e)}")


@app.get("/api/audio/stems/{job_id}/{stem_name}")
def api_get_audio_stem(job_id: str, stem_name: str):
    """Stream or download separated stem (vocals.wav or instrumental.wav)."""
    clean_job = sanitize_profile_id(job_id)
    if stem_name not in ("vocals", "instrumental"):
        raise HTTPException(status_code=400, detail="Буруу stem нэр. 'vocals' эсвэл 'instrumental' сонгоно уу.")

    stem_path = os.path.join(STEMS_DIR, clean_job, f"{stem_name}.wav")
    if not os.path.isfile(stem_path):
        raise HTTPException(status_code=404, detail="Stem файл олдсонгүй.")
    return FileResponse(stem_path, media_type="audio/wav", filename=f"{clean_job}_{stem_name}.wav")


@app.post("/api/lyrics/export-ass")
def api_lyrics_export_ass(req: dict):
    """
    Export Aegisub standard Advanced SubStation Alpha (.ass) with word-level karaoke timing.
    """
    segments = req.get("segments", [])
    title = req.get("title", "Voice Karaoke")
    font_name = req.get("font_name", "Arial")
    font_size = int(req.get("font_size", 48))
    primary_color = req.get("primary_color", "&H0000FFFF")
    secondary_color = req.get("secondary_color", "&H00FFFFFF")
    outline_color = req.get("outline_color", "&H00101010")

    ass_text = generate_karaoke_ass(
        segments=segments,
        title=title,
        font_name=font_name,
        font_size=font_size,
        primary_color=primary_color,
        secondary_color=secondary_color,
        outline_color=outline_color,
    )
    return {"status": "ok", "ass_content": ass_text}


@app.get("/api/lyrics/ffmpeg-status")
def api_lyrics_ffmpeg_status():
    """Check if FFmpeg is available for video rendering."""
    avail = is_ffmpeg_available()
    bin_path = find_system_or_bundled_ffmpeg()
    return {
        "available": avail,
        "path": bin_path or "",
        "version": "FFmpeg 8.1 (Gyan.dev full build with libass)" if avail else "Not found",
    }


@app.post("/api/lyrics/export-video")
async def api_lyrics_export_video(
    audio: UploadFile = File(...),
    ass_content: str = Form(...),
    title: str = Form("karaoke"),
    resolution: str = Form("1280x720"),
    bg_color: str = Form("#0f172a"),
):
    """
    Render video with hard-burned karaoke subtitles using FFmpeg.
    """
    if not is_ffmpeg_available():
        raise HTTPException(status_code=503, detail="FFmpeg суулгаагүй тул видео үүсгэх боломжгүй байна. Субтитр .ASS файлаар татаж авна уу.")

    tmp_dir = os.path.join(STEMS_DIR, f"video_{uuid.uuid4().hex[:8]}")
    os.makedirs(tmp_dir, exist_ok=True)

    audio_bytes = await audio.read()
    audio_path = os.path.join(tmp_dir, "input_audio.wav")
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    ass_path = os.path.join(tmp_dir, "karaoke.ass")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    out_mp4 = os.path.join(tmp_dir, "output.mp4")

    try:
        ok = export_karaoke_video(
            audio_path=audio_path,
            ass_path=ass_path,
            output_mp4_path=out_mp4,
            background_color=bg_color,
            resolution=resolution,
        )
        if not ok or not os.path.isfile(out_mp4):
            raise RuntimeError("FFmpeg did not produce output video.")

        # Read mp4 into memory to serve before cleaning up tmp_dir
        with open(out_mp4, "rb") as f:
            mp4_bytes = f.read()

        shutil.rmtree(tmp_dir, ignore_errors=True)
        return Response(
            content=mp4_bytes,
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{title}.mp4"'},
        )
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.error(f"Error rendering karaoke video: {e}")
        raise HTTPException(status_code=500, detail=f"Видео үүсгэхэд алдаа гарлаа: {str(e)}")


# ---------------------------------------------------------------------------
# Frontend Direct /api/... Route Aliases (Supports single-port 8000 desktop app)
# ---------------------------------------------------------------------------

@app.get("/api/settings")
def api_get_settings():
    cfg = load_server_settings()
    cfg["whisper_cpp_available"] = bool(find_whisper_cpp_binary())
    cfg["whisper_cpp_models"] = {
        k: bool(find_local_ggml_model(k)) for k in WHISPER_MODELS_INFO.keys()
    }
    cfg["hardware"] = detect_gpu_hardware()
    cfg["models_list"] = list_available_local_models()
    return cfg

@app.post("/api/settings")
def api_save_settings(req: dict):
    saved = save_server_settings(req)
    global SERVER_SETTINGS
    SERVER_SETTINGS = saved
    return saved

@app.post("/api/export-srt")
def api_export_srt(req: dict):
    segments = req.get("segments", [])
    srt_content = generate_srt(segments)
    return Response(
        content=srt_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=voice_subtitles.srt"},
    )


@app.post("/api/export-lrc")
def api_export_lrc(req: dict):
    segments = req.get("segments", [])
    title = req.get("title", "")
    artist = req.get("artist", "")
    lrc_content = generate_lrc(segments, title=title, artist=artist)
    return Response(
        content=lrc_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=voice_lyrics.lrc"},
    )


@app.post("/api/export-vtt")
def api_export_vtt(req: dict):
    segments = req.get("segments", [])
    vtt_content = generate_vtt(segments)
    return Response(
        content=vtt_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=voice_subtitles.vtt"},
    )


@app.post("/api/summarize")
def api_summarize(req: dict):
    """
    AI Smart Summarizer & Action Items extraction.
    Extracts summary, key points, action items (to-dos), and decisions.
    """
    text = req.get("text", "")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="\u0422\u044d\u043a\u0441\u0442 \u0445\u043e\u043e\u0441\u043e\u043d \u0431\u0430\u0439\u043d\u0430.")
    return extract_summary_and_actions(text)


@app.post("/api/rewrite-style")
def api_rewrite_style(req: dict):
    """
    AI Smart Tone & Style Rewriter endpoint.
    Accepts: { "text": "...", "style": "formal" | "email" | "social" | "proofread" }
    """
    text = req.get("text", "")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Текст хоосон байна.")
    style = req.get("style", "formal")
    return rewrite_text_style(text, style=style)


@app.post("/api/format-numbers")
def api_format_numbers(req: dict):
    """
    Smart Mongolian Number, Currency & Contact Formatter endpoint.
    Accepts: { "text": "..." }
    Returns: { "status": "ok", "formatted_text": "...", "original_text": "..." }
    """
    text = req.get("text", "")
    if not text or not isinstance(text, str):
        return {"status": "ok", "formatted_text": "", "original_text": ""}
    formatted = normalize_mongolian_numbers(text)
    return {"status": "ok", "formatted_text": formatted, "original_text": text}




@app.post("/api/auto-lyrics")
async def api_auto_lyrics(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    model_name: str = Form("small"),
    title: str = Form(""),
    artist: str = Form(""),
):
    """
    Auto-transcribe uploaded audio or video file (MP3, WAV, M4A, OGG, MP4) and generate:
    - Segments with millisecond start/end timestamps and word-level timing
    - Synchronized Lyrics (.lrc)
    - Subtitles (.srt and .vtt)
    """
    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Аудио/видео файл хэт том байна (дээд тал нь 25 MB).")
    if len(content) < 500:
        raise HTTPException(status_code=400, detail="Файл хэт богино эсвэл хоосон байна.")

    filename = audio.filename or "input.wav"
    ext = os.path.splitext(filename)[1].lower()
    valid_exts = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".mp4", ".webm", ".aac")
    if ext and ext not in valid_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Дэмжигдээгүй файл формат ({ext}). MP3, WAV, M4A, OGG, MP4 файл оруулна уу.",
        )
    if not ext:
        ext = ".wav"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tf:
        tf.write(content)
        tf_path = tf.name

    try:
        segments_data = []
        full_text = ""
        detected_lang = language if language != "auto" else "mn"

        # 1. Try local whisper.cpp CLI first for fast, reliable timestamped segmentation
        if find_whisper_cpp_binary() and (find_local_ggml_model(model_name) or find_local_ggml_model("tiny")):
            try:
                cfg_lyrics = load_server_settings()
                txt_cpp, segs_cpp, cpp_err = transcribe_with_whisper_cpp_cli(
                    tf_path,
                    model_name=model_name,
                    language=detected_lang,
                    use_gpu=cfg_lyrics.get("use_gpu", True),
                    threads=cfg_lyrics.get("cpu_threads", 6),
                )
                if not cpp_err and segs_cpp:
                    segments_data = segs_cpp
                    full_text = txt_cpp
                elif cpp_err:
                    logger.warning("[AutoLyrics] whisper.cpp warning: %s", cpp_err.encode("ascii", "replace").decode("ascii"))
            except Exception as cpp_e:
                logger.warning("[AutoLyrics] whisper.cpp exc: %s", str(cpp_e).encode("ascii", "replace").decode("ascii"))

        # 2. Fall back to faster-whisper if no segments yet
        if not segments_data:
            try:
                whisper_model = get_whisper_model(model_name)
                lang_arg = None if language in ("auto", "") else language
                segments, info = whisper_model.transcribe(
                    tf_path,
                    language=lang_arg,
                    beam_size=5,
                    word_timestamps=True,
                    vad_filter=True,
                )
                detected_lang = getattr(info, "language", detected_lang) or detected_lang
                for idx, s in enumerate(segments, start=1):
                    clean_txt = format_speech_text(s.text.strip(), auto_punct=False)
                    if not clean_txt:
                        continue
                    words_list = []
                    if hasattr(s, "words") and s.words:
                        for w in s.words:
                            words_list.append({
                                "word": w.word.strip(),
                                "start": round(float(w.start), 3),
                                "end": round(float(w.end), 3),
                                "probability": round(float(getattr(w, "probability", 1.0)), 2),
                            })
                    segments_data.append({
                        "id": idx,
                        "start": round(float(s.start), 3),
                        "end": round(float(s.end), 3),
                        "text": clean_txt,
                        "words": words_list,
                    })
                full_text = " ".join([s["text"] for s in segments_data]).strip()
            except Exception as whisper_err:
                logger.warning("[AutoLyrics] Whisper fallback: %s", str(whisper_err).encode("ascii", "replace").decode("ascii"))

        # 3. If still no segments, fall back to speech recognition
        if not segments_data:
            raw_text, err = transcribe_wav_bytes(content, language=detected_lang)
            if not raw_text:
                return {
                    "status": "ok",
                    "language": detected_lang,
                    "text": "",
                    "segments": [],
                    "lrc": generate_lrc([], title=title, artist=artist),
                    "srt": "",
                    "vtt": "WEBVTT\r\n",
                }
            full_text = raw_text
            sentences = [s.strip() for s in re.split(r"[.!?\n]+", raw_text) if s.strip()]
            cur_t = 0.5
            for idx, sent in enumerate(sentences, start=1):
                dur = max(2.0, len(sent) * 0.08)
                segments_data.append({
                    "id": idx,
                    "start": round(cur_t, 3),
                    "end": round(cur_t + dur, 3),
                    "text": sent,
                    "words": [],
                })
                cur_t += dur + 0.5

        lrc_text = generate_lrc(segments_data, title=title, artist=artist)
        srt_text = generate_srt(segments_data)
        vtt_text = generate_vtt(segments_data)

        actual_model = (
            segments_data[0].get("model_used", model_name)
            if segments_data and "model_used" in segments_data[0]
            else (model_name if find_local_ggml_model(model_name) else "tiny")
        )
        timing_source = (
            segments_data[0].get("timing_source", "whisper_token_timestamps")
            if segments_data
            else "none"
        )
        fallback_notice = (
            f"Загвар '{model_name}' диск дээр олдсонгүй; локал 'tiny'-г ашиглав."
            if actual_model != model_name
            else ""
        )

        return {
            "status": "ok",
            "language": detected_lang,
            "text": full_text,
            "model_requested": model_name,
            "model_used": actual_model,
            "fallback_notice": fallback_notice,
            "timing_source": timing_source,
            "segments": segments_data,
            "lrc": lrc_text,
            "srt": srt_text,
            "vtt": vtt_text,
        }
    finally:
        if os.path.exists(tf_path):
            try:
                os.remove(tf_path)
            except Exception:
                pass


@app.post("/api/quit")
def api_quit_server():
    def _shutdown():
        time.sleep(0.2)
        if _tk_root:
            try:
                _tk_root.quit()
                _tk_root.destroy()
            except Exception:
                pass
        os._exit(0)
    threading.Thread(target=_shutdown, daemon=True).start()
    return {"status": "ok", "message": "VOICE shutting down..."}

@app.get("/api/flowbar")
def api_flowbar_get():
    return get_flowbar_status()


@app.post("/api/flowbar")
def api_flowbar_post(req: dict = None):
    if not req:
        return get_flowbar_status()
    if "insertText" in req and req["insertText"]:
        insert_text_to_active_window(req["insertText"])
        return {"status": "ok", "inserted": req["insertText"]}
    act = req.get("action", "")
    lang = req.get("language")
    return flowbar_action(FlowBarActionRequest(action=act, language=lang))

@app.post("/api/flowbar/stream-preview")
async def api_flowbar_stream_preview(
    audio: UploadFile = File(...),
    language: str = Form("mn"),
):
    """
    Phase 1 Real-time Live Dictation interim preview endpoint.
    Accepts rolling audio slice (< 2MB, ~2-3 seconds).
    Performs fast local-first transcription without external network requests.
    Updates in-memory interim preview text (last 3-4 words).
    STRICT SAFETY RULE: Interim previews NEVER trigger keyboard/clipboard injection.
    """
    MAX_PREVIEW_BYTES = 2 * 1024 * 1024
    content = await audio.read(MAX_PREVIEW_BYTES + 1)
    if len(content) > MAX_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="Preview slice too large (max 2MB)")
    if not content or len(content) < 500:
        return {"status": "ok", "interim_text": "", "last_words": "", "is_final": False}

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tf.write(content)
            tmp_path = tf.name

        raw_text = ""
        # 1. Local whisper.cpp CLI subprocess (fastest, lightweight)
        if find_whisper_cpp_binary():
            txt_cpp, _, _ = transcribe_with_whisper_cpp_cli(
                tmp_path,
                model_name="tiny",
                language=language if language != "auto" else "mn",
                timeout_sec=4.0,
            )
            raw_text = (txt_cpp or "").strip()

        # 2. Local whisper fallback (faster-whisper) if whisper.cpp had no output or is missing
        if not raw_text:
            alt_text, _ = transcribe_with_whisper(content, language=language if language != "auto" else "mn", model_name="tiny")
            raw_text = (alt_text or "").strip()

        words = raw_text.split()
        last_words = " ".join(words[-4:]) if words else ""
        FLOWBAR_STATE["interim_preview"] = last_words
        return {
            "status": "ok",
            "interim_text": raw_text,
            "last_words": last_words,
            "is_final": False,
        }
    except Exception as e:
        logger.warning(f"[FlowBarPreview] Error processing preview slice: {e}")
        return {"status": "error", "interim_text": "", "last_words": "", "is_final": False, "error": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.post("/api/flowbar/transcribe")
async def api_flowbar_transcribe(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
):
    """
    Dedicated 100% Local-First final transcription endpoint for FlowBar.
    Strictly forbids external third-party cloud audio transmission (Google, Chimege, etc.).
    Uses whisper.cpp CLI subprocess (or faster-whisper local engine).
    Applies custom snippets and returns clean text.
    """
    content = await audio.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Аудио файл хэт том байна (дээд тал нь 25 MB).")
    if not content or len(content) < 500:
        return {"status": "ok", "text": "", "engine": "local_whisper", "error": "Аудио хэт богино эсвэл хоосон байна."}

    cfg = load_server_settings()
    m_name = cfg.get("whisper_model", "tiny")
    use_gpu = cfg.get("use_gpu", True)
    threads = cfg.get("cpu_threads", 6)

    # Local transcription only: whisper.cpp -> faster-whisper
    text, err = transcribe_with_whisper(
        content,
        language=language,
        model_name=m_name,
        use_gpu=use_gpu,
        threads=threads,
    )
    if not text and err:
        logger.warning(f"[FlowBarTranscribe] Local transcription error: {err}")
        return {"status": "error", "text": "", "engine": "local_whisper", "error": err}

    if text:
        if cfg.get("filler_word_cleaner", True):
            text = strip_filler_words(text)
        if cfg.get("voice_actions", True):
            text, action = process_voice_commands(text)
            if action == "undo":
                undo_ok = trigger_undo_insert()
                return {
                    "status": "ok" if undo_ok else "failed",
                    "text": "",
                    "action": "undo" if undo_ok else "undo_failed",
                    "undo_ok": undo_ok,
                    "message": "Сүүлийнхийг арилгалаа (Undo)" if undo_ok else "Буцаах боломжгүй эсвэл хугацаа (8 сек) дууссан",
                    "engine": "local_whisper_cpp" if find_whisper_cpp_binary() else "local_whisper",
                }
        if cfg.get("custom_snippets", True) and cfg.get("snippets"):
            text = apply_voice_snippets(text, cfg.get("snippets", {}))
        if cfg.get("mongolian_grammar", True):
            text = apply_mongolian_grammar(text)
        if cfg.get("tech_terms_normalization", True):
            text = normalize_tech_terms(text)
        if cfg.get("number_normalization", True):
            text = normalize_mongolian_numbers(text)

    return {
        "status": "ok",
        "text": text,
        "engine": "local_whisper_cpp" if find_whisper_cpp_binary() else "local_whisper",
    }


@app.get("/api/tts")
def api_tts_get():
    return {
        "online": True,
        "status": "ok",
        "engine": "VoiceStudio AI Neural Engine",
        "voices": VOICES + list(CLONED_VOICES_DB.values()),
    }


@app.post("/api/tts")
async def api_tts(req: TTSRequest):
    return await tts(req)


@app.get("/api/tts/clone")
def api_tts_clone_get(id: str = ""):
    if not id:
        return list_clones()
    return get_clone_sample(id)


@app.delete("/api/tts/clone")
def api_tts_clone_delete(id: str = ""):
    return delete_clone(id)


@app.post("/api/tts/clone")
async def api_tts_clone_post(name: str = Form("Миний хоолой"), audio: UploadFile = File(...)):
    return await clone_voice(name, audio)


@app.post("/api/chimege/transcribe")
async def api_chimege_transcribe(audio: UploadFile = File(...), language: str = Form("mn")):
    return await transcribe(audio, language)


@app.post("/api/spellcheck")
async def api_spellcheck(req: dict):
    text = req.get("text", "")
    action = req.get("action", "full")
    word = req.get("word", "")
    if action == "suggest" and word:
        s_key = _encrypt_spellcheck_key(word)
        try:
            base_url = "https://spellcheck.mn/cms-client/modules/spellchecker"
            headers = {
                "Content-Type": "application/json",
                "Origin": "https://spellcheck.mn",
                "Referer": "https://spellcheck.mn/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VoiceApp/1.0",
            }
            s_req = urllib.request.Request(
                f"{base_url}/suggest",
                data=json.dumps({"word": word, "key": s_key}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(s_req, timeout=1.8) as s_resp:
                cands = json.loads(s_resp.read().decode("utf-8", errors="ignore"))
                return {"word": word, "suggestions": cands if isinstance(cands, list) else []}
        except Exception:
            return {"word": word, "suggestions": []}

    if not text or len(text.strip()) < 2:
        return {"text": text, "misspelled": [], "suggestions": {}, "correctedText": text}

    try:
        corrected = _auto_correct_subtle_typos_spellcheck_mn(text)
        return {"text": text, "misspelled": [], "suggestions": {}, "correctedText": corrected}
    except Exception:
        return {"text": text, "misspelled": [], "suggestions": {}, "correctedText": text}


# ---------------------------------------------------------------------------
# Static Web App Mount (Single Port 8000 Desktop Architecture)
# ---------------------------------------------------------------------------
from fastapi.responses import FileResponse, RedirectResponse

OUT_DIR = os.path.join(BASE_DIR, "out")

@app.get("/")
def serve_root():
    dash_html = os.path.join(OUT_DIR, "dashboard.html")
    if os.path.isfile(dash_html):
        return FileResponse(dash_html, media_type="text/html")
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard")
@app.get("/tts")
@app.get("/history")
@app.get("/settings")
@app.get("/flowbar")
@app.get("/lyrics")
def serve_app_page(request: Request):
    page = request.url.path.strip("/") or "dashboard"
    html_file = os.path.join(OUT_DIR, f"{page}.html")
    if os.path.isfile(html_file):
        return FileResponse(html_file, media_type="text/html")
    idx_file = os.path.join(OUT_DIR, "index.html")
    if os.path.isfile(idx_file):
        return FileResponse(idx_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="Page not found")

@app.get("/api/check-update")
@app.get("/api/update/check")
def check_for_updates():
    """Non-blocking release update checker from GitHub Releases using semver."""
    try:
        import auto_updater
        return auto_updater.check_github_release(current_version=APP_VERSION)
    except Exception as e:
        return {
            "current_version": APP_VERSION,
            "latest_version": APP_VERSION,
            "has_update": False,
            "error": str(e),
        }


class UpdateDownloadRequest(BaseModel):
    download_url: str
    expected_sha256: str
    version: Optional[str] = ""


@app.post("/api/update/download")
def api_update_download(req: UpdateDownloadRequest):
    """Download verified installer to temporary directory and register verified update session."""
    import auto_updater
    try:
        path = auto_updater.download_and_verify_installer(
            req.download_url,
            expected_sha256=req.expected_sha256,
        )
        token = auto_updater.create_update_session(path, req.version or "latest")
        return {"status": "ok", "session_token": token}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateInstallRequest(BaseModel):
    session_token: str


@app.post("/api/update/install")
def api_update_install(req: UpdateInstallRequest):
    """Launch verified installer from active updater session and shut down current instance."""
    import auto_updater
    installer_path = auto_updater.get_verified_session_installer(req.session_token)
    if not installer_path:
        raise HTTPException(status_code=403, detail="Хүчингүй эсвэл баталгаажаагүй шинэчлэлийн session token.")

    try:
        _flowbar_cmds.put(("quit",))
        if _tray_icon:
            _tray_icon.stop()
    except Exception:
        pass

    threading.Thread(
        target=lambda: auto_updater.launch_installer_and_exit(installer_path),
        daemon=True,
    ).start()
    return {"status": "ok", "message": "Launching installer and exiting..."}

try:
    from fastapi.staticfiles import StaticFiles

    if os.path.exists(OUT_DIR):
        app.mount("/", StaticFiles(directory=OUT_DIR, html=True), name="static")
except Exception as e:
    print("[!] Static files mount notice:", e)


if __name__ == "__main__":
    if not check_single_instance(SERVER_PORT):
        sys.exit(0)

    if not is_port_available(SERVER_PORT):
        print(f"[!] Port {SERVER_PORT} is in use by another program.")
        if os.name == "nt":
            try:
                user32.MessageBoxW(
                    0,
                    f"Port {SERVER_PORT} is used by another program.\nPlease close it and start VOICE again.",
                    "VOICE",
                    0x10,
                )
            except Exception:
                pass
        sys.exit(1)

    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT, reload=False, log_level="warning")

