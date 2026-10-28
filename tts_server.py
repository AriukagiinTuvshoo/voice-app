import asyncio
import ctypes
from ctypes import wintypes
import io
import json
import math
import os
import re
import threading
import time
import tempfile
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
import numpy as np
from scipy import signal as sp_signal
from scipy.io import wavfile

app = FastAPI(
    title="VOICE & VoiceStudio AI Engine (TTS, STT, Voice Cloning & Duudlaga Flow)",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLONES_DIR = os.path.join(BASE_DIR, "clones")
CLONES_JSON = os.path.join(CLONES_DIR, "voices.json")
BASE_ENVELOPES_CACHE: dict[str, np.ndarray] = {}

os.makedirs(CLONES_DIR, exist_ok=True)

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
    """Decode WAV, MP3, FLAC, OGG into mono float32 numpy array at target_sr."""
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
            return data
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

# Common English & Japanese terms frequently mixed into Mongolian speech
CODESWITCH_PHRASE_MAP: list[tuple[str, str]] = [
    # Multi-word phrases first
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
    # Japanese expressions commonly spoken in Mongolian conversation
    (r"\bаригато\s+гозаймас\b", "ありがとうございます (Arigatou gozaimasu)"),
    (r"\bаригато\b", "ありがとう (Arigatou)"),
    (r"\bконничива\b", "こんにちは (Konnichiwa)"),
    (r"\bконичива\b", "こんにちは (Konnichiwa)"),
    (r"\bохаёо\s+гозаймас\b", "おはようございます (Ohayou gozaimasu)"),
    (r"\bохаёо\b", "おはよう (Ohayou)"),
    (r"\bсумимасэн\b", "すみません (Sumimasen)"),
    (r"\bсумимасен\b", "すみません (Sumimasen)"),
    (r"\bсаёонара\b", "さようなら (Sayounara)"),
    (r"\bсугой\b", "すごい (Sugoi)"),
    (r"\bкавайи\b", "かわいい (Kawaii)"),
    (r"\bкавай\b", "かわいい (Kawaii)"),
    (r"\bсэнсэй\b", "先生 (Sensei)"),
    (r"\bсенсей\b", "先生 (Sensei)"),
    (r"\bдайжообү\b", "大丈夫 (Daijoubu)"),
    (r"\bдайжобү\b", "大丈夫 (Daijoubu)"),
    (r"\bганбаттэ\b", "頑張って (Ganbatte)"),
    # Single English tech & daily loanwords (preserving Mongolian suffixes if attached)
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


def restore_codeswitch_terms(mn_text: str, en_text: str = "", ja_text: str = "") -> str:
    """
    1. Applies curated Mongolian-English-Japanese code-switching dictionary.
    2. Aligns phonetic Cyrillic tokens with high-confidence English words recognized in parallel on the same audio!
    """
    if not mn_text:
        return mn_text

    out = mn_text
    for pattern, replacement in CODESWITCH_PHRASE_MAP:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)

    # If parallel English STT heard words, check if any Cyrillic word in mn_text is a direct phonetic transliteration
    # of an English word from en_text (e.g., user said an English technical term mid-sentence)
    if en_text:
        en_words = [w.strip(".,!?\"'()[]{}") for w in en_text.split() if len(w.strip(".,!?")) >= 4]
        # Exclude common short English function words that might accidentally match Mongolian words
        en_stop = {"that", "this", "with", "from", "have", "what", "when", "where", "your", "they", "will", "been", "were", "there", "about"}
        en_candidates = [w for w in en_words if w.lower() not in en_stop and w.isascii() and w.isalpha()]

        if en_candidates:
            tokens = out.split()
            new_tokens = []
            for tok in tokens:
                clean_tok = tok.strip(".,!?")
                punct_suffix = tok[len(clean_tok) :]
                replaced = False
                # Check if clean_tok (or stem before hyphen) matches an English candidate phonetically
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

    return out


def split_audio_on_pauses(samples: np.ndarray, sample_rate: int = 16000) -> list[np.ndarray]:
    """
    Splits audio into natural clause segments at pauses >= 280ms so code-switched clauses
    (e.g. Mongolian clause -> English/Japanese clause -> Mongolian clause) are recognized in their own language!
    """
    duration = samples.size / float(sample_rate)
    if duration < 2.4:
        return [samples]

    frame_len = int(0.02 * sample_rate)  # 20ms frames
    n_frames = samples.size // frame_len
    if n_frames < 20:
        return [samples]

    framed = samples[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms = np.sqrt(np.mean(framed ** 2, axis=1) + 1e-10)
    thresh = max(0.014, float(np.percentile(rms, 22)) * 1.15)
    is_silent = rms < thresh

    # Find contiguous silent runs >= 14 frames (280ms)
    segments: list[np.ndarray] = []
    seg_start_sample = 0
    silent_run = 0

    for i, sil in enumerate(is_silent):
        if sil:
            silent_run += 1
        else:
            if silent_run >= 14:
                split_frame = i - (silent_run // 2)
                split_sample = split_frame * frame_len
                if (split_sample - seg_start_sample) >= int(0.85 * sample_rate):
                    segments.append(samples[seg_start_sample:split_sample])
                    seg_start_sample = split_sample
            silent_run = 0

    tail = samples[seg_start_sample:]
    if tail.size >= int(0.45 * sample_rate) or not segments:
        segments.append(tail)
    elif segments:
        segments[-1] = np.concatenate([segments[-1], tail])

    # Cap at 5 segments max to avoid excessive API calls
    if len(segments) > 5:
        return [samples]
    return segments


def _recognize_single_lang(wav_bytes: bytes, lang_code: str) -> tuple[str, float]:
    """Run Google STT with show_all=True and return (best_transcript, confidence)."""
    r = sr.Recognizer()
    r.dynamic_energy_threshold = False
    try:
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio_data = r.record(source)
        res = r.recognize_google(audio_data, language=lang_code, show_all=True)
        if isinstance(res, dict) and "alternative" in res and res["alternative"]:
            alts = res["alternative"]
            best = alts[0]
            text = (best.get("transcript") or "").strip()
            conf = float(best.get("confidence", 0.78))
            return text, conf
    except Exception:
        pass
    return "", 0.0


def transcribe_wav_bytes(raw_bytes: bytes, language: str = "mn") -> tuple[str, str]:
    """
    Studio-grade Multilingual & Code-Switching STT Engine:
    1. Pre-emphasizes consonants (sibilants/plosives), filters 75Hz rumble, levels speech dynamics, normalizes to -1.0 dBFS.
    2. Splits long utterances on natural pauses into clauses.
    3. Runs parallel multi-language recognition (mn-MN, en-US, ja-JP) with confidence comparison.
    4. Fuses English/Japanese code-switched words inside Mongolian sentences cleanly.
    """
    if not HAS_SR:
        return "", "SpeechRecognition суугаагүй байна."

    try:
        samples = decode_audio_bytes(raw_bytes, target_sr=16000)
    except Exception as e:
        return "", f"Аудио уншихад алдаа: {e}"

    if samples.size < 2400:  # < 0.15s
        return "", "Аудио хэт богино байна."

    # 1. Studio Audio Cleaning for Crisp Speech Recognition
    try:
        # 75Hz high-pass filter to remove mic pop & room rumble
        sos = sp_signal.butter(2, 75.0 / 8000.0, btype="highpass", output="sos")
        samples = sp_signal.sosfiltfilt(sos, samples.astype(np.float64)).astype(np.float32)
        # Subtle pre-emphasis to sharpen Mongolian/English/Japanese consonants
        pre_emph = np.append(samples[0], samples[1:] - 0.55 * samples[:-1]).astype(np.float32)
        samples = 0.70 * samples + 0.30 * pre_emph
    except Exception:
        pass

    samples = trim_silence(samples, 16000, threshold_db=-46.0)
    samples = level_speech_np(samples, 16000)
    samples = normalize_audio_np(samples, target_dbfs=-1.0)

    req_lang = (language or "mn").lower().strip()
    segments = split_audio_on_pauses(samples, 16000)

    final_clauses: list[str] = []

    with ThreadPoolExecutor(max_workers=3) as pool:
        for seg in segments:
            seg_wav = encode_wav_bytes(seg, 16000)

            if req_lang in ("en", "en-us"):
                fut_en = pool.submit(_recognize_single_lang, seg_wav, "en-US")
                fut_mn = pool.submit(_recognize_single_lang, seg_wav, "mn-MN")
                en_txt, en_conf = fut_en.result()
                mn_txt, mn_conf = fut_mn.result()
                chosen = en_txt if (en_txt and en_conf >= mn_conf - 0.1) else (mn_txt or en_txt)
                if chosen:
                    final_clauses.append(chosen)

            elif req_lang in ("ja", "ja-jp"):
                fut_ja = pool.submit(_recognize_single_lang, seg_wav, "ja-JP")
                fut_mn = pool.submit(_recognize_single_lang, seg_wav, "mn-MN")
                ja_txt, ja_conf = fut_ja.result()
                mn_txt, mn_conf = fut_mn.result()
                chosen = ja_txt if (ja_txt and ja_conf >= mn_conf - 0.1) else (mn_txt or ja_txt)
                if chosen:
                    final_clauses.append(chosen)

            else:
                # Multilingual Code-Switching Mode (Mongolian + English + Japanese simultaneously!)
                fut_mn = pool.submit(_recognize_single_lang, seg_wav, "mn-MN")
                fut_en = pool.submit(_recognize_single_lang, seg_wav, "en-US")
                fut_ja = pool.submit(_recognize_single_lang, seg_wav, "ja-JP")

                mn_txt, mn_conf = fut_mn.result()
                en_txt, en_conf = fut_en.result()
                ja_txt, ja_conf = fut_ja.result()

                # Decide if this clause was spoken primarily in Japanese, English, or Mongolian:
                if ja_txt and (not mn_txt or (ja_conf >= 0.84 and ja_conf - mn_conf >= 0.14)):
                    chosen = ja_txt
                elif en_txt and (not mn_txt or (en_conf >= 0.84 and en_conf - mn_conf >= 0.14)):
                    chosen = en_txt
                elif mn_txt:
                    # Mongolian base clause with smart English/Japanese code-switch token restoration!
                    chosen = restore_codeswitch_terms(mn_txt, en_text=en_txt, ja_text=ja_txt)
                else:
                    chosen = en_txt or ja_txt or ""

                if chosen:
                    final_clauses.append(chosen)

    text = " ".join(c.strip() for c in final_clauses if c.strip()).strip()
    if text:
        text = text[0].upper() + text[1:]
        if text[-1] not in ".!?。！？":
            text += "."
        return text, ""

    return "", "Яриа танигдсангүй. Микрофондоо ойрхон, тод ярина уу."


# ---------------------------------------------------------------------------
# Native Windows Duudlaga Flow Engine:
# Global Ctrl+Alt / F8 Hook + Always-On-Top Floating Pill + Direct Word/Facebook Typing
# ---------------------------------------------------------------------------

FLOWBAR_STATE = {
    "status": "idle",        # idle | recording | processing | success | error
    "visible": True,
    "last_text": "",
    "last_timestamp": 0,
    "error": "",
    "seconds": 0,
    "levels": [4, 8, 12, 8, 4],
    "language": "mn",
    "target_window": "",
    "desktop": "",
    "last_insert_debug": "",
}

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

    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040

    INPUT_KEYBOARD = 1
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_LCONTROL = 0xA2
    VK_RCONTROL = 0xA3
    VK_MENU = 0x12
    VK_LMENU = 0xA4
    VK_RMENU = 0xA5
    VK_SPACE = 0x20
    VK_F8 = 0x77
    VK_V = 0x56
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

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
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL

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


def copy_to_windows_clipboard(text: str) -> None:
    """
    Thread-safe native Win32 clipboard copy using CF_UNICODETEXT.
    Never touches Tkinter from background threads and never spawns clip.exe!
    """
    if not text or os.name != "nt":
        return
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


def restore_window_focus(target: int) -> bool:
    """Unconditionally restore foreground & keyboard focus to target HWND."""
    if not target or os.name != "nt" or is_own_process_window(target):
        return False
    try:
        target_tid = user32.GetWindowThreadProcessId(target, None)
        curr_tid = kernel32.GetCurrentThreadId()
        attached = False
        if target_tid and target_tid != curr_tid:
            attached = bool(user32.AttachThreadInput(curr_tid, target_tid, True))
        try:
            user32.SetForegroundWindow(target)
            user32.BringWindowToTop(target)
            user32.SetFocus(target)
        finally:
            if attached:
                user32.AttachThreadInput(curr_tid, target_tid, False)
        return True
    except Exception:
        return False


def insert_text_to_active_window(text: str, hwnd: int = 0) -> bool:
    """
    Ported & hardened from DuudlagaFlow TextInsertionService.cs:
    1. Copies text to Windows clipboard via thread-safe Win32 CF_UNICODETEXT.
    2. Restores focus to captured target window (Antigravity IDE, Word, Facebook, Chrome, Telegram).
    3. Releases any lingering Ctrl/Alt keys and types every Unicode character via SendInput(KEYEVENTF_UNICODE).
    """
    if not text or os.name != "nt":
        return False

    copy_to_windows_clipboard(text)

    # Pick best non-self target window
    candidates = [hwnd, _target_hwnd, _last_external_hwnd, _last_active_hwnd, user32.GetForegroundWindow()]
    target = 0
    for c in candidates:
        if c and not is_own_process_window(c):
            t_title = get_window_title(c)
            if t_title != "Task Switching":
                target = c
                break

    if target:
        restore_window_focus(target)
        for _ in range(12):
            time.sleep(0.02)
            if user32.GetForegroundWindow() == target:
                break
        time.sleep(0.04)

    # Wait up to 300ms if user's fingers are still physically holding Ctrl or Alt
    for _ in range(12):
        c_down = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0
        a_down = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
        if not c_down and not a_down:
            break
        time.sleep(0.025)

    # Explicitly release all Ctrl and Alt modifier keys so target app receives pure Unicode chars
    mod_vks = [VK_CONTROL, VK_LCONTROL, VK_RCONTROL, VK_MENU, VK_LMENU, VK_RMENU]
    release_mods = (INPUT * len(mod_vks))()
    for i, vk in enumerate(mod_vks):
        release_mods[i].type = INPUT_KEYBOARD
        release_mods[i].union.ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, 0)
    user32.SendInput(len(mod_vks), ctypes.byref(release_mods), ctypes.sizeof(INPUT))
    time.sleep(0.025)

    # Type each character 2 events at a time (exact match to DuudlagaFlow TypeText)
    text_with_space = text if text.endswith(" ") else text + " "
    total_sent = 0
    pair = (INPUT * 2)()
    for idx, ch in enumerate(text_with_space):
        code = ord(ch)
        pair[0].type = INPUT_KEYBOARD
        pair[0].union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)
        pair[1].type = INPUT_KEYBOARD
        pair[1].union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
        sent = user32.SendInput(2, ctypes.byref(pair), ctypes.sizeof(INPUT))
        total_sent += sent
        if idx % 14 == 13:
            time.sleep(0.002)

    target_title = get_window_title(target)
    fg_now = user32.GetForegroundWindow()
    FLOWBAR_STATE["last_insert_debug"] = (
        f"target=0x{target:X}('{target_title[:25]}') fg=0x{fg_now:X} sent={total_sent}/{len(text_with_space)*2}"
    )
    print(f"[FlowBar] {FLOWBAR_STATE['last_insert_debug']}")
    return total_sent > 0


def start_native_flowbar_recording(from_ui_button: bool = False) -> None:
    global _is_recording, _target_hwnd, _record_start_time, _last_speech_time, _has_spoken, _speech_frames_count
    if _is_recording or FLOWBAR_STATE["status"] == "processing":
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


def stop_native_flowbar_recording() -> None:
    global _is_recording, _last_stop_time
    if not _is_recording:
        return
    _is_recording = False
    _last_stop_time = time.time()
    FLOWBAR_STATE["status"] = "processing"
    threading.Thread(target=_process_native_recording, daemon=True).start()


def _process_native_recording() -> None:
    global _last_stop_time
    with _recording_lock:
        if not _recording_Buffer:
            FLOWBAR_STATE["status"] = "error"
            FLOWBAR_STATE["error"] = "Яриа сонсогдсонгүй"
            time.sleep(1.5)
            FLOWBAR_STATE["status"] = "idle"
            return
        audio_np = np.concatenate(_recording_Buffer, axis=0).reshape(-1)
        _recording_Buffer.clear()

    if audio_np.size < 3200:
        FLOWBAR_STATE["status"] = "error"
        FLOWBAR_STATE["error"] = "Хэт богино байна"
        time.sleep(1.5)
        FLOWBAR_STATE["status"] = "idle"
        return

    wav_bytes = encode_wav_bytes(audio_np, 16000)
    text, err = transcribe_wav_bytes(wav_bytes, language=FLOWBAR_STATE.get("language", "mn"))
    _last_stop_time = time.time()
    if text:
        FLOWBAR_STATE["last_text"] = text
        FLOWBAR_STATE["last_timestamp"] = int(time.time() * 1000)
        FLOWBAR_STATE["status"] = "success"
        insert_text_to_active_window(text, _target_hwnd)
        time.sleep(1.8)
        FLOWBAR_STATE["status"] = "idle"
    else:
        FLOWBAR_STATE["status"] = "error"
        FLOWBAR_STATE["error"] = "Тод ярина уу"
        print("[FlowBar] STT empty:", err)
        time.sleep(1.8)
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
    if HAS_SOUNDDEVICE:
        try:
            stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                blocksize=1024,
                callback=audio_callback,
            )
            stream.start()
            print(f"[+] Native Windows Microphone Stream ready (Desktop: {FLOWBAR_STATE['desktop']})")
        except Exception as e:
            print("[-] Native microphone stream warning:", e)

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
            f8_down = bool(user32.GetAsyncKeyState(VK_F8) & 0x8000)
            shift_down = bool(user32.GetAsyncKeyState(0x10) & 0x8000)
            hotkey_down = (ctrl_down and alt_down and not shift_down) or f8_down

            now = time.time()

            if hotkey_down and not was_hotkey_down:
                hotkey_press_time = now
                if alt_down:
                    _suppress_alt_menu_activation()
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

            # Update timer & silence auto-stop (if in Toggle mode and user paused for 2.2s after speaking)
            if _is_recording:
                FLOWBAR_STATE["seconds"] = int(now - _record_start_time)
                if not hotkey_down and _has_spoken and (now - _last_speech_time) > 2.2:
                    stop_native_flowbar_recording()

        except Exception as e:
            print("Hotkey worker error:", e)

        time.sleep(0.025)


def _native_flowbar_ui_worker() -> None:
    """
    Native Always-On-Top Floating Pill Window (exact equivalent of DuudlagaFlow FlowBarWindow.xaml)
    with WS_EX_NOACTIVATE and SWP_NOACTIVATE so clicking it never steals focus from Antigravity, Word, or Facebook!
    """
    global _tk_root, _flowbar_hwnd
    if os.name != "nt":
        return

    try:
        import tkinter as tk
    except ImportError:
        return

    try:
        root = tk.Tk()
        _tk_root = root
        root.title("VOICE FlowBar")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.96)
        root.configure(bg="#090d16")

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        bar_w, bar_h = 286, 46
        pos_x = (screen_w - bar_w) // 2
        pos_y = screen_h - bar_h - 58
        root.geometry(f"{bar_w}x{bar_h}+{pos_x}+{pos_y}")

        canvas = tk.Canvas(
            root,
            width=bar_w,
            height=bar_h,
            bg="#0f1420",
            highlightthickness=2,
            highlightbackground="#6366f1",
            bd=0,
            cursor="hand2",
        )
        canvas.pack(fill="both", expand=True)

        # Apply WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW to both outer and inner Tk HWNDs
        root.update_idletasks()
        inner_hwnd = root.winfo_id()
        outer_hwnd = user32.GetParent(inner_hwnd) or inner_hwnd
        _flowbar_hwnd = outer_hwnd
        for h in {inner_hwnd, outer_hwnd}:
            if h:
                ex_style = user32.GetWindowLongW(h, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    h, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
                )

        drag_data = {"x": 0, "y": 0, "moved": False}
        was_visible = True

        def on_press(event):
            drag_data["x"] = event.x
            drag_data["y"] = event.y
            drag_data["moved"] = False
            # Immediately restore focus to last external window if Tk grabbed focus on click
            if _last_external_hwnd:
                restore_window_focus(_last_external_hwnd)

        def on_drag(event):
            dx = event.x - drag_data["x"]
            dy = event.y - drag_data["y"]
            if abs(dx) > 4 or abs(dy) > 4:
                drag_data["moved"] = True
                nx = root.winfo_x() + dx
                ny = root.winfo_y() + dy
                root.geometry(f"{bar_w}x{bar_h}+{nx}+{ny}")

        def on_release(event):
            if _last_external_hwnd:
                restore_window_focus(_last_external_hwnd)
            if not drag_data["moved"]:
                if _is_recording:
                    stop_native_flowbar_recording()
                elif FLOWBAR_STATE["status"] != "processing":
                    start_native_flowbar_recording(from_ui_button=False)

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        def refresh_ui():
            nonlocal was_visible
            vis = bool(FLOWBAR_STATE.get("visible", True))
            if not vis and was_visible:
                root.withdraw()
                was_visible = False
            elif vis and not was_visible:
                root.deiconify()
                was_visible = True

            if vis and outer_hwnd:
                # Keep topmost WITHOUT activating the window!
                user32.SetWindowPos(
                    outer_hwnd,
                    HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
                )

            st = FLOWBAR_STATE["status"]
            canvas.delete("all")

            if st == "idle":
                canvas.configure(bg="#0f1420", highlightbackground="#6366f1")
                canvas.create_oval(14, 13, 34, 33, fill="#4f46e5", outline="#818cf8", width=1)
                canvas.create_text(24, 23, text="🎙", fill="#ffffff", font=("Segoe UI Emoji", 10))
                canvas.create_text(
                    158,
                    16,
                    text="VOICE FLOW • Энд дарж ярина уу",
                    fill="#f8fafc",
                    font=("Segoe UI", 9, "bold"),
                )
                canvas.create_text(
                    158,
                    32,
                    text="Товчлуур: Ctrl + Alt  эсвэл  F8",
                    fill="#94a3b8",
                    font=("Segoe UI", 8),
                )
            elif st == "recording":
                canvas.configure(bg="#b91c1c", highlightbackground="#fca5a5")
                canvas.create_oval(14, 15, 28, 29, fill="#ffffff", outline="")
                secs = FLOWBAR_STATE.get("seconds", 0)
                canvas.create_text(
                    112,
                    23,
                    text=f"Ярьж байна... {secs}с (Дараад дуусгах)",
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )
                lvls = FLOWBAR_STATE.get("levels", [6, 12, 16, 12, 6])
                for i, l in enumerate(lvls):
                    bx = 222 + i * 10
                    bh = max(4, min(28, l))
                    by0 = 23 - bh // 2
                    by1 = 23 + bh // 2
                    canvas.create_rectangle(bx, by0, bx + 5, by1, fill="#ffffff", outline="")
            elif st == "processing":
                canvas.configure(bg="#4338ca", highlightbackground="#a5b4fc")
                canvas.create_text(
                    143,
                    23,
                    text="⏳ Текст болгож бичиж байна...",
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )
            elif st == "success":
                canvas.configure(bg="#047857", highlightbackground="#6ee7b7")
                preview = FLOWBAR_STATE.get("last_text", "")[:22]
                canvas.create_text(
                    143,
                    23,
                    text=f"✅ Бичигдлээ: {preview}",
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )
            else:
                canvas.configure(bg="#7f1d1d", highlightbackground="#f87171")
                err_txt = FLOWBAR_STATE.get("error", "Дахин ярина уу")[:24]
                canvas.create_text(
                    143,
                    23,
                    text=f"⚠️ {err_txt}",
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )

            root.after(80, refresh_ui)

        root.after(100, refresh_ui)
        root.mainloop()
    except Exception as e:
        print("FlowBar Tkinter UI warning:", e)


# Start background threads once
_bg_started = False


@app.on_event("startup")
def on_startup():
    global _bg_started
    if not _bg_started and os.name == "nt":
        _bg_started = True
        threading.Thread(target=_native_audio_hotkey_worker, daemon=True).start()
        threading.Thread(target=_native_flowbar_ui_worker, daemon=True).start()
        print("[+] Duudlaga Flow Native Ctrl+Alt & Floating Pill started!")


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


class InsertTextRequest(BaseModel):
    text: str


class FlowBarActionRequest(BaseModel):
    action: str  # "toggle_visibility" | "show" | "hide" | "start" | "stop" | "set_language"
    language: Optional[str] = "mn"


@app.get("/")
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
    return {
        "status": "ok",
        "has_edge": HAS_EDGE_TTS,
        "has_stt": HAS_SR,
        "has_mms": mms_model is not None,
        "has_miniaudio": HAS_MINIAUDIO,
        "voice_cloning": True,
        "flowbar_status": FLOWBAR_STATE["status"],
        "flowbar_visible": FLOWBAR_STATE["visible"],
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


@app.get("/clones/{voice_id}/sample")
def get_clone_sample(voice_id: str):
    wav_path = os.path.join(CLONES_DIR, f"{voice_id}.wav")
    if not os.path.exists(wav_path):
        raise HTTPException(status_code=404, detail="Sample audio not found")
    return FileResponse(wav_path, media_type="audio/wav", filename=f"{voice_id}.wav")


@app.delete("/clones/{voice_id}")
def delete_clone(voice_id: str):
    CLONED_VOICES_DB.pop(voice_id, None)
    save_cloned_voices_db(CLONED_VOICES_DB)
    wav_path = os.path.join(CLONES_DIR, f"{voice_id}.wav")
    if os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass
    return {"deleted": voice_id}


@app.get("/flowbar/status")
def get_flowbar_status():
    return FLOWBAR_STATE


@app.post("/flowbar/action")
def flowbar_action(req: FlowBarActionRequest):
    act = (req.action or "").lower()
    if act == "toggle_visibility":
        FLOWBAR_STATE["visible"] = not FLOWBAR_STATE["visible"]
    elif act == "show":
        FLOWBAR_STATE["visible"] = True
    elif act == "hide":
        FLOWBAR_STATE["visible"] = False
    elif act == "start":
        start_native_flowbar_recording(from_ui_button=True)
    elif act == "stop":
        stop_native_flowbar_recording()
    elif act == "set_language" and req.language:
        FLOWBAR_STATE["language"] = req.language
    return FLOWBAR_STATE


@app.post("/insert-text")
def api_insert_text(req: InsertTextRequest):
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

    try:
        communicate = edge_tts.Communicate(
            text=synth_text,
            voice=base_voice,
            rate=rate_str,
            pitch=pitch_str,
        )
        raw_mp3 = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                raw_mp3.extend(chunk["data"])

        if not raw_mp3:
            raise HTTPException(status_code=500, detail="Empty audio generated")

        # Decode to 24kHz float32 PCM so we can run VoiceStudio Timbre Transfer, Persona Warp & Mastering DSP
        if HAS_MINIAUDIO:
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
    content = await audio.read()
    if not content or len(content) < 500:
        return {"text": "", "error": "Аудио хэт богино эсвэл хоосон байна."}

    text, err = transcribe_wav_bytes(content, language=language)
    if text:
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
    content = await audio.read()
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
        ref_text, _ = transcribe_wav_bytes(clean_wav_bytes, language="mn")

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

        # Return profile without huge envelope array to keep frontend payload small
        resp_profile = {k: v for k, v in profile.items() if k != "envelope"}
        return resp_profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Хоолой хувилахад алдаа гарлаа: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tts_server:app", host="0.0.0.0", port=8000, reload=True)
