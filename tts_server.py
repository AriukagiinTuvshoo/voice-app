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
        "description": "Эелдэг, уян зөөлөн, байгалийн өнгө аяс",
        "tag": "Үндсэн • Эмэгтэй",
    },
    {
        "id": "mn-MN-BataaNeural",
        "name": "Батаа",
        "gender": "male",
        "engine": "edge-neural",
        "description": "Цэвэр тод, өөртөө итгэлтэй, баргил",
        "tag": "Үндсэн • Эрэгтэй",
    },
]

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
# STT Helper with Audio Enhancement for High Accuracy
# ---------------------------------------------------------------------------

def transcribe_wav_bytes(raw_bytes: bytes, language: str = "mn") -> tuple[str, str]:
    """
    Enhance recorded audio (decode, remove rumble, trim silence, normalize to -1.5 dBFS)
    and transcribe via Google STT (mn-MN, en-US, ja-JP).
    """
    if not HAS_SR:
        return "", "SpeechRecognition суугаагүй байна."

    try:
        samples = decode_audio_bytes(raw_bytes, target_sr=16000)
    except Exception as e:
        return "", f"Аудио уншихад алдаа: {e}"

    if samples.size < 2400:  # < 0.15s
        return "", "Аудио хэт богино байна."

    # High-pass filter at 75Hz to clean mic rumble/hum + normalize volume for STT clarity
    try:
        sos = sp_signal.butter(2, 75.0 / 8000.0, btype="highpass", output="sos")
        samples = sp_signal.sosfiltfilt(sos, samples.astype(np.float64)).astype(np.float32)
    except Exception:
        pass

    samples = trim_silence(samples, 16000, threshold_db=-48.0)
    samples = normalize_audio_np(samples, target_dbfs=-1.5)

    clean_wav = encode_wav_bytes(samples, 16000)

    lang_map = {
        "mn": "mn-MN",
        "mn-mn": "mn-MN",
        "en": "en-US",
        "en-us": "en-US",
        "ja": "ja-JP",
        "ja-jp": "ja-JP",
        "auto": "mn-MN",
    }
    lang_code = lang_map.get((language or "mn").lower().strip(), "mn-MN")

    r = sr.Recognizer()
    r.dynamic_energy_threshold = False
    with sr.AudioFile(io.BytesIO(clean_wav)) as source:
        audio_data = r.record(source)

    try:
        text = r.recognize_google(audio_data, language=lang_code)
        text = (text or "").strip()
        if text:
            # Capitalize first letter
            text = text[0].upper() + text[1:]
            if text[-1] not in ".!?":
                text += "."
        return text, ""
    except sr.UnknownValueError:
        return "", "Яриа танигдсангүй. Микрофондоо ойрхон, тод ярина уу."
    except sr.RequestError as e:
        return "", f"Яриа таних сервертэй холбогдож чадсангүй: {e}"


# ---------------------------------------------------------------------------
# Native Windows Duudlaga Flow Engine:
# Global Ctrl+Alt Hook + Always-On-Top Floating Pill + Direct Word/Facebook Typing
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
}

_target_hwnd: int = 0
_recording_Buffer: list[np.ndarray] = []
_recording_lock = threading.Lock()
_is_recording = False
_record_start_time = 0.0
_last_speech_time = 0.0
_has_spoken = False
_tk_root = None

if os.name == "nt":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    GWL_EXSTYLE = -20
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_TOPMOST = 0x00000008

    INPUT_KEYBOARD = 1
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_MENU = 0x12
    VK_V = 0x56

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


def copy_to_windows_clipboard(text: str) -> None:
    """Copy Unicode text to Windows clipboard cleanly."""
    if _tk_root is not None:
        try:
            _tk_root.clipboard_clear()
            _tk_root.clipboard_append(text)
            _tk_root.update()
            return
        except Exception:
            pass
    try:
        import subprocess
        p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        p.communicate(input=text.encode("utf-16-le"))
    except Exception:
        pass


def insert_text_to_active_window(text: str, hwnd: int = 0) -> bool:
    """
    Ported directly from DuudlagaFlow TextInsertionService.cs:
    1. Copies text to clipboard.
    2. Restores focus to captured target window (Word, Facebook, Chrome, Telegram) if needed.
    3. Types every Unicode Cyrillic character directly via Win32 SendInput(KEYEVENTF_UNICODE).
    """
    if not text or os.name != "nt":
        return False

    copy_to_windows_clipboard(text)

    target = hwnd or _target_hwnd or user32.GetForegroundWindow()
    if target:
        curr_fg = user32.GetForegroundWindow()
        if curr_fg != target:
            target_tid = user32.GetWindowThreadProcessId(target, None)
            curr_tid = kernel32.GetCurrentThreadId()
            attached = False
            if target_tid != curr_tid:
                attached = bool(user32.AttachThreadInput(curr_tid, target_tid, True))
            try:
                user32.SetForegroundWindow(target)
                time.sleep(0.06)
            finally:
                if attached:
                    user32.AttachThreadInput(curr_tid, target_tid, False)

    # Release any lingering Ctrl or Alt modifier state so target app sees clean Unicode typing
    release_mods = (INPUT * 2)()
    release_mods[0].type = INPUT_KEYBOARD
    release_mods[0].union.ki = KEYBDINPUT(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0, 0)
    release_mods[1].type = INPUT_KEYBOARD
    release_mods[1].union.ki = KEYBDINPUT(VK_MENU, 0, KEYEVENTF_KEYUP, 0, 0)
    user32.SendInput(2, ctypes.byref(release_mods), ctypes.sizeof(INPUT))
    time.sleep(0.03)

    # Send Unicode characters directly (works in MS Word, Facebook, Chrome, Notepad, etc.)
    text_with_space = text if text.endswith(" ") else text + " "
    n_chars = len(text_with_space)
    inputs = (INPUT * (n_chars * 2))()
    for idx, ch in enumerate(text_with_space):
        code = ord(ch)
        i_down = idx * 2
        i_up = idx * 2 + 1
        inputs[i_down].type = INPUT_KEYBOARD
        inputs[i_down].union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0)
        inputs[i_up].type = INPUT_KEYBOARD
        inputs[i_up].union.ki = KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)

    sent = user32.SendInput(n_chars * 2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    print(f"[FlowBar] Typed {len(text)} chars into HWND 0x{target:X} (SendInput={sent})")
    return sent > 0


def start_native_flowbar_recording() -> None:
    global _is_recording, _target_hwnd, _record_start_time, _last_speech_time, _has_spoken
    if _is_recording or FLOWBAR_STATE["status"] == "processing":
        return

    if os.name == "nt":
        fg = user32.GetForegroundWindow()
        if fg:
            _target_hwnd = fg

    with _recording_lock:
        _recording_Buffer.clear()

    _record_start_time = time.time()
    _last_speech_time = time.time()
    _has_spoken = False
    _is_recording = True
    FLOWBAR_STATE["status"] = "recording"
    FLOWBAR_STATE["seconds"] = 0
    FLOWBAR_STATE["error"] = ""
    FLOWBAR_STATE["visible"] = True
    print(f"[FlowBar] Recording started (Target HWND: 0x{_target_hwnd:X})")


def stop_native_flowbar_recording() -> None:
    global _is_recording
    if not _is_recording:
        return
    _is_recording = False
    FLOWBAR_STATE["status"] = "processing"
    threading.Thread(target=_process_native_recording, daemon=True).start()


def _process_native_recording() -> None:
    with _recording_lock:
        if not _recording_Buffer:
            FLOWBAR_STATE["status"] = "error"
            FLOWBAR_STATE["error"] = "Яриа сонсогдсонгүй"
            time.sleep(1.8)
            FLOWBAR_STATE["status"] = "idle"
            return
        audio_np = np.concatenate(_recording_Buffer, axis=0).reshape(-1)
        _recording_Buffer.clear()

    if audio_np.size < 3200:
        FLOWBAR_STATE["status"] = "error"
        FLOWBAR_STATE["error"] = "Хэт богино байна"
        time.sleep(1.8)
        FLOWBAR_STATE["status"] = "idle"
        return

    wav_bytes = encode_wav_bytes(audio_np, 16000)
    text, err = transcribe_wav_bytes(wav_bytes, language=FLOWBAR_STATE.get("language", "mn"))
    if text:
        FLOWBAR_STATE["last_text"] = text
        FLOWBAR_STATE["last_timestamp"] = int(time.time() * 1000)
        FLOWBAR_STATE["status"] = "success"
        insert_text_to_active_window(text, _target_hwnd)
        time.sleep(2.0)
        FLOWBAR_STATE["status"] = "idle"
    else:
        FLOWBAR_STATE["status"] = "error"
        FLOWBAR_STATE["error"] = "Тод ярина уу"
        print("[FlowBar] STT empty:", err)
        time.sleep(2.0)
        FLOWBAR_STATE["status"] = "idle"


def _native_audio_hotkey_worker() -> None:
    """
    Background worker that:
    1. Polls Windows hardware Ctrl+Alt state at 35Hz (supports both Hold-to-Talk and Tap-to-Toggle!).
    2. Captures microphone audio via sounddevice while _is_recording is True.
    """
    if os.name != "nt":
        return

    was_hotkey_down = False
    hotkey_press_time = 0.0
    started_by_current_press = False

    def audio_callback(indata, frames, time_info, status):
        global _last_speech_time, _has_spoken
        if not _is_recording:
            return
        chunk = indata[:, 0].copy()
        with _recording_lock:
            _recording_Buffer.append(chunk)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        lvl = int(min(22, max(4, rms * 260)))
        FLOWBAR_STATE["levels"] = FLOWBAR_STATE["levels"][1:] + [lvl]
        FLOWBAR_STATE["seconds"] = int(time.time() - _record_start_time)
        if rms > 0.018:
            _has_spoken = True
            _last_speech_time = time.time()

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
            print("[+] Native Windows Microphone Stream ready for Ctrl+Alt Dictation")
        except Exception as e:
            print("[-] Native microphone stream warning:", e)

    while True:
        try:
            ctrl_down = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0
            alt_down = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
            # Check that Shift or Win are not pressed
            shift_down = (user32.GetAsyncKeyState(0x10) & 0x8000) != 0
            hotkey_down = ctrl_down and alt_down and not shift_down

            now = time.time()

            if hotkey_down and not was_hotkey_down:
                hotkey_press_time = now
                if not _is_recording and FLOWBAR_STATE["status"] != "processing":
                    start_native_flowbar_recording()
                    started_by_current_press = True
                elif _is_recording:
                    # Tapped Ctrl+Alt again to stop!
                    started_by_current_press = False
                    stop_native_flowbar_recording()

            elif not hotkey_down and was_hotkey_down:
                held_duration = now - hotkey_press_time
                # If user held Ctrl+Alt for >= 0.55s (Push-to-Talk), stop on release!
                if _is_recording and started_by_current_press and held_duration >= 0.55:
                    stop_native_flowbar_recording()
                started_by_current_press = False

            was_hotkey_down = hotkey_down

            # Update timer & silence auto-stop (if in Toggle mode and user paused for 2.5s after speaking)
            if _is_recording:
                FLOWBAR_STATE["seconds"] = int(now - _record_start_time)
                if not hotkey_down and _has_spoken and (now - _last_speech_time) > 2.5:
                    stop_native_flowbar_recording()

        except Exception as e:
            print("Hotkey worker error:", e)

        time.sleep(0.028)


def _native_flowbar_ui_worker() -> None:
    """
    Native Always-On-Top Floating Pill Window (exact equivalent of DuudlagaFlow FlowBarWindow.xaml)
    with WS_EX_NOACTIVATE so clicking it never steals focus from Word or Facebook!
    """
    global _tk_root
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
        root.attributes("-alpha", 0.95)
        root.configure(bg="#090d16")

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        bar_w, bar_h = 236, 42
        pos_x = (screen_w - bar_w) // 2
        pos_y = screen_h - bar_h - 62
        root.geometry(f"{bar_w}x{bar_h}+{pos_x}+{pos_y}")

        canvas = tk.Canvas(
            root,
            width=bar_w,
            height=bar_h,
            bg="#0f131a",
            highlightthickness=1,
            highlightbackground="#334155",
            bd=0,
            cursor="hand2",
        )
        canvas.pack(fill="both", expand=True)

        # Apply WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW so clicking never steals focus from Word/Facebook
        root.update_idletasks()
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, ex_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
        )

        drag_data = {"x": 0, "y": 0, "moved": False}

        def on_press(event):
            drag_data["x"] = event.x
            drag_data["y"] = event.y
            drag_data["moved"] = False
            # Capture active foreground window before click
            fg = user32.GetForegroundWindow()
            if fg and fg != hwnd:
                global _target_hwnd
                _target_hwnd = fg

        def on_drag(event):
            dx = event.x - drag_data["x"]
            dy = event.y - drag_data["y"]
            if abs(dx) > 4 or abs(dy) > 4:
                drag_data["moved"] = True
                nx = root.winfo_x() + dx
                ny = root.winfo_y() + dy
                root.geometry(f"{bar_w}x{bar_h}+{nx}+{ny}")

        def on_release(event):
            if not drag_data["moved"]:
                if _is_recording:
                    stop_native_flowbar_recording()
                elif FLOWBAR_STATE["status"] != "processing":
                    start_native_flowbar_recording()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        def refresh_ui():
            if not FLOWBAR_STATE.get("visible", True):
                root.withdraw()
            else:
                root.deiconify()
                root.attributes("-topmost", True)

            st = FLOWBAR_STATE["status"]
            canvas.delete("all")

            if st == "idle":
                canvas.configure(bg="#0f131a", highlightbackground="#4f46e5")
                canvas.create_oval(16, 15, 26, 25, fill="#818cf8", outline="")
                canvas.create_text(
                    126,
                    21,
                    text="🎙️ VOICE FLOW  (Ctrl+Alt)",
                    fill="#f8fafc",
                    font=("Segoe UI", 9, "bold"),
                )
            elif st == "recording":
                canvas.configure(bg="#b91c1c", highlightbackground="#f87171")
                canvas.create_oval(14, 15, 24, 25, fill="#ffffff", outline="")
                secs = FLOWBAR_STATE.get("seconds", 0)
                canvas.create_text(
                    85,
                    21,
                    text=f"Ярьж байна... {secs}с",
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )
                lvls = FLOWBAR_STATE.get("levels", [6, 12, 16, 12, 6])
                for i, l in enumerate(lvls):
                    bx = 162 + i * 10
                    bh = max(4, min(26, l))
                    by0 = 21 - bh // 2
                    by1 = 21 + bh // 2
                    canvas.create_rectangle(bx, by0, bx + 5, by1, fill="#ffffff", outline="")
            elif st == "processing":
                canvas.configure(bg="#4338ca", highlightbackground="#818cf8")
                canvas.create_text(
                    118,
                    21,
                    text="⏳ Текст болгож байна...",
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )
            elif st == "success":
                canvas.configure(bg="#047857", highlightbackground="#34d399")
                preview = FLOWBAR_STATE.get("last_text", "")[:18]
                canvas.create_text(
                    118,
                    21,
                    text=f"✅ Бичигдлээ: {preview}",
                    fill="#ffffff",
                    font=("Segoe UI", 9, "bold"),
                )
            else:
                canvas.configure(bg="#7f1d1d", highlightbackground="#ef4444")
                err_txt = FLOWBAR_STATE.get("error", "Дахин ярина уу")[:22]
                canvas.create_text(
                    118,
                    21,
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
        start_native_flowbar_recording()
    elif act == "stop":
        stop_native_flowbar_recording()
    elif act == "set_language" and req.language:
        FLOWBAR_STATE["language"] = req.language
    return FLOWBAR_STATE


@app.post("/insert-text")
def api_insert_text(req: InsertTextRequest):
    ok = insert_text_to_active_window(req.text)
    return {"inserted": ok, "text": req.text}


@app.post("/tts")
async def tts(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    voice_id = (req.voice or "mn-MN-YesuiNeural").strip()
    preset_id = (req.preset or "broadcast").strip().lower()
    timbre_strength = float(np.clip(req.timbreStrength if req.timbreStrength is not None else 0.92, 0.0, 1.0))

    clone_profile = CLONED_VOICES_DB.get(voice_id)
    is_cloned = clone_profile is not None or voice_id.startswith("cloned_")

    # Determine base neural voice & prosody parameters
    if clone_profile:
        base_voice = clone_profile.get("baseVoice", "mn-MN-BataaNeural")
        speaker_f0 = float(clone_profile.get("f0", 135.0))
        speaker_rate = float(clone_profile.get("rate_hz", 4.2))
        base_f0 = 122.0 if "bataa" in base_voice.lower() else 210.0
        # Shift pitch in Hz directly toward speaker's measured F0
        f0_diff_hz = int(np.clip(speaker_f0 - base_f0, -45, 45))
        user_pitch_adj = int(((req.pitch or 1.0) - 1.0) * 40)
        pitch_str = f"{f0_diff_hz + user_pitch_adj:+d}Hz"

        # Match speaking cadence + user speed slider
        cadence_ratio = np.clip(speaker_rate / 4.2, 0.88, 1.15)
        total_speed = (req.speed or 1.0) * cadence_ratio
        rate_percent = int(np.clip((total_speed - 1.0) * 100, -45, 60))
        rate_str = f"{rate_percent:+d}%"
    else:
        base_voice = "mn-MN-BataaNeural" if ("bataa" in voice_id.lower() or "male" in voice_id.lower()) else "mn-MN-YesuiNeural"
        rate_percent = int(((req.speed or 1.0) - 1.0) * 100)
        rate_str = f"{rate_percent:+d}%"
        pitch_hz = int(((req.pitch or 1.0) - 1.0) * 45)
        pitch_str = f"{pitch_hz:+d}Hz"

    if not HAS_EDGE_TTS:
        raise HTTPException(status_code=503, detail="Edge-TTS engine not installed")

    try:
        communicate = edge_tts.Communicate(
            text=text,
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

        # Decode to 24kHz float32 PCM so we can run VoiceStudio Timbre Transfer & Mastering DSP
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
