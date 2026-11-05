"""
VOICE Desktop — Studio Acoustic DSP, Formant Warping, Timbre Transfer & Offline TTS Engine.
Provides broadcast-grade 3-band zero-phase EQ, dynamic de-esser, early-reflections room ambience,
EBU R128 phrase leveler, cepstral vocal-tract timbre transfer, and offline SAPI5 fallback synthesis.
"""

from __future__ import annotations

import io
import math
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import signal as sp_signal
from scipy.io import wavfile

try:
    import miniaudio
    HAS_MINIAUDIO = True
except Exception:
    miniaudio = None
    HAS_MINIAUDIO = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except Exception:
    sf = None
    HAS_SOUNDFILE = False

TARGET_SR = 24000
STFT_NPERSEG = 1024
STFT_NOVERLAP = 768
CEPSTRAL_LIFTER = 30  # Quefrency cutoff capturing vocal tract formants F1..F4

BASE_ENVELOPES_CACHE: Dict[str, np.ndarray] = {}

VOICESTUDIO_PRESETS: Dict[str, Dict[str, Any]] = {
    "broadcast": {
        "label": "Broadcast (Студи стандарт)",
        "icon": "📻",
        "description": "Тэнцвэртэй, тод, радио болон ТВ нэвтрүүлгийн стандарт.",
        "low_db": 1.2,
        "mid_db": 1.4,
        "high_db": 1.8,
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
        "low_db": 2.4,
        "mid_db": 0.8,
        "high_db": -1.0,
        "leveler": True,
        "reverb": 0.04,
    },
    "bright": {
        "label": "Bright (Тод цэвэр)",
        "icon": "✨",
        "description": "Өндөр давтамж тодорсон, маш цэвэрхэн дуудлага.",
        "low_db": -0.8,
        "mid_db": 0.6,
        "high_db": 2.8,
        "leveler": True,
        "reverb": 0.0,
    },
    "cinematic": {
        "label": "Cinematic (Кино студи)",
        "icon": "🎬",
        "description": "Бага зэргийн орон зайн цуурайтай, сүрлэг өнгө.",
        "low_db": 1.8,
        "mid_db": 0.0,
        "high_db": 1.4,
        "leveler": True,
        "reverb": 0.08,
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

VOICES: List[Dict[str, Any]] = [
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
        "pitch": 0.91,
        "speed": 0.95,
        "formantWarp": 0.95,
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
        "pitch": 1.03,
        "speed": 1.05,
        "formantWarp": 1.02,
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
        "pitch": 0.96,
        "speed": 1.02,
        "formantWarp": 0.97,
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
        "pitch": 0.95,
        "speed": 0.93,
        "formantWarp": 0.97,
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
        "pitch": 0.86,
        "speed": 0.91,
        "formantWarp": 0.93,
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
        "pitch": 1.15,
        "speed": 1.04,
        "formantWarp": 1.06,
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

VOICES_BY_ID: Dict[str, Dict[str, Any]] = {v["id"]: v for v in VOICES}


def decode_audio_bytes(raw_bytes: bytes, target_sr: int = TARGET_SR) -> np.ndarray:
    """Decode WAV, MP3, M4A, WEBM, FLAC, OGG into mono float32 numpy array at target_sr."""
    if HAS_MINIAUDIO and miniaudio is not None:
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

    if HAS_SOUNDFILE and sf is not None:
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
    """Trim leading and trailing silence while keeping natural 60ms breath padding."""
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
    """Peak-normalize audio to target_dbfs."""
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
    """EBU R128-style phrase leveler preserving natural breath dynamics."""
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
    """Apply studio-grade broadcast mastering, zero-phase 3-band EQ, de-esser & natural room ambience."""
    if samples.size == 0:
        return samples

    preset = VOICESTUDIO_PRESETS.get(preset_id, VOICESTUDIO_PRESETS["broadcast"])
    if preset_id == "raw":
        return normalize_audio_np(samples, -1.8)

    y = samples.astype(np.float64)
    nyq = sample_rate / 2.0

    # 1. Highpass at 65 Hz to remove DC / plosive rumble
    sos_hp = sp_signal.butter(2, 65.0 / nyq, btype="highpass", output="sos")
    y = sp_signal.sosfiltfilt(sos_hp, y)

    # 1.1 Dynamic Envelope De-Esser (5.8 kHz - 8.5 kHz) to tame harsh sibilance ('с', 'ш', 'ц', 'з')
    if y.size >= 1024 and sample_rate >= 16000:
        try:
            sos_sib = sp_signal.butter(2, [5800.0 / nyq, min(0.95, 8500.0 / nyq)], btype="bandpass", output="sos")
            sib_band = sp_signal.sosfiltfilt(sos_sib, y)
            win_len = max(64, int(sample_rate * 0.012))
            kernel = np.ones(win_len, dtype=np.float64) / win_len
            sib_env = np.sqrt(np.convolve(sib_band ** 2, kernel, mode="same") + 1e-12)
            broad_env = np.sqrt(np.convolve(y ** 2, kernel, mode="same") + 1e-12)
            ratio = sib_env / np.maximum(broad_env, 1e-6)
            reduction = np.clip((ratio - 0.34) * 0.65, 0.0, 0.42)
            y = y - reduction * sib_band
        except Exception:
            pass

    # 2. Zero-Phase Time-Domain 3-Band EQ (avoids double STFT/ISTFT transient smearing)
    low_db = float(preset.get("low_db", 0.0))
    mid_db = float(preset.get("mid_db", 0.0))
    high_db = float(preset.get("high_db", 0.0))

    if abs(low_db) > 0.1:
        sos_low = sp_signal.butter(2, 250.0 / nyq, btype="lowpass", output="sos")
        low_band = sp_signal.sosfiltfilt(sos_low, y)
        low_gain = (10.0 ** (low_db / 20.0)) - 1.0
        y = y + low_gain * low_band

    if abs(mid_db) > 0.1:
        sos_mid = sp_signal.butter(2, [450.0 / nyq, 2600.0 / nyq], btype="bandpass", output="sos")
        mid_band = sp_signal.sosfiltfilt(sos_mid, y)
        mid_gain = (10.0 ** (mid_db / 20.0)) - 1.0
        y = y + mid_gain * mid_band

    if abs(high_db) > 0.1:
        sos_high = sp_signal.butter(2, 3600.0 / nyq, btype="highpass", output="sos")
        high_band = sp_signal.sosfiltfilt(sos_high, y)
        high_gain = (10.0 ** (high_db / 20.0)) - 1.0
        y = y + high_gain * high_band

    # 3. Natural Studio Early-Reflections Ambience (with 22ms pre-delay & L2 energy normalization)
    reverb_wet = float(preset.get("reverb", 0.0))
    if reverb_wet > 0.005 and y.size > 1024:
        predelay = int(sample_rate * 0.022)
        ir_len = int(sample_rate * 0.24)
        rng = np.random.default_rng(42)
        t_ir = np.linspace(0.0, 1.0, ir_len)
        ir = np.zeros(predelay + ir_len, dtype=np.float64)
        for tap_ms, tap_gain in ((22, 0.55), (37, -0.38), (53, 0.28), (71, -0.20)):
            idx_tap = int(sample_rate * (tap_ms / 1000.0))
            if idx_tap < ir.size:
                ir[idx_tap] += tap_gain
        tail = rng.standard_normal(ir_len) * np.exp(-7.5 * t_ir) * 0.18
        ir[predelay:] += tail
        sos_rev = sp_signal.butter(2, [220.0 / nyq, 3200.0 / nyq], btype="bandpass", output="sos")
        ir = sp_signal.sosfilt(sos_rev, ir)
        ir_norm = np.linalg.norm(ir) + 1e-9
        ir = ir / ir_norm
        wet = sp_signal.fftconvolve(y, ir, mode="full")[: y.size]
        y = (1.0 - reverb_wet * 0.35) * y + reverb_wet * wet

    # 4. Gentle EBU R128 phrase leveler
    y_f32 = y.astype(np.float32)
    if preset.get("leveler", True):
        y_f32 = level_speech_np(
            y_f32,
            sample_rate,
            window_ms=450.0,
            amount=0.35,
            max_gain_db=3.5,
            smooth_ms=240.0,
        )

    # 5. Transparent True-Peak Soft-Knee Limiter & micro fade-in/out
    peak = float(np.max(np.abs(y_f32)))
    if peak > 1e-6:
        y_f32 = y_f32 * (0.82 / peak)
    knee = 0.72
    over = np.abs(y_f32) > knee
    if np.any(over):
        sign = np.sign(y_f32[over])
        mag_over = np.abs(y_f32[over]) - knee
        y_f32[over] = sign * (knee + (1.0 - knee) * np.tanh(mag_over / (1.0 - knee)))

    fade_in = min(int(sample_rate * 0.010), y_f32.size // 4)
    fade_out = min(int(sample_rate * 0.018), y_f32.size // 4)
    if fade_in > 1:
        y_f32[:fade_in] *= np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    if fade_out > 1:
        y_f32[-fade_out:] *= np.linspace(1.0, 0.0, fade_out, dtype=np.float32)

    return normalize_audio_np(y_f32, -1.8)


def extract_cepstral_envelope(samples: np.ndarray, sample_rate: int = TARGET_SR) -> np.ndarray:
    """
    Extract smooth vocal tract spectral envelope (formants F1..F4 + throat/chest timbre)
    from voiced frames using Cosine-Tapered Cepstral Liftering in the STFT domain.
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

    log_mag = np.log(mag[:, voiced_cols])
    mean_log_mag = np.mean(log_mag, axis=1)

    cepstrum = np.fft.irfft(mean_log_mag)
    lifter = np.zeros_like(cepstrum)
    lifter[:CEPSTRAL_LIFTER] = 1.0
    lifter[-CEPSTRAL_LIFTER + 1 :] = 1.0
    taper = 8
    for k in range(taper):
        w = 0.5 * (1.0 + math.cos(math.pi * k / taper))
        lifter[CEPSTRAL_LIFTER - taper + k] = w
        lifter[-(CEPSTRAL_LIFTER - taper + k)] = w

    smooth_env_log = np.real(np.fft.rfft(cepstrum * lifter))
    smooth_env_log = smooth_env_log - np.mean(smooth_env_log)
    return smooth_env_log.astype(np.float32)


def analyze_speaker_prosody(samples: np.ndarray, sample_rate: int = TARGET_SR) -> Dict[str, Any]:
    """
    Measures median F0 (Hz), pitch spread (semitones), speaking rate (syllables/sec),
    formant centroid (Hz), harmonic-to-noise ratio (HNR dB), high-frequency presence ratio,
    and 513-bin vocal tract cepstral envelope.
    """
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
            "hnr_db": 14.0,
            "presence_db": 0.0,
            "envelope": extract_cepstral_envelope(samples, sample_rate).tolist(),
        }

    n_frames = 1 + (sig16.size - frame_len) // hop_len
    frames = np.lib.stride_tricks.sliding_window_view(sig16, frame_len)[::hop_len][:n_frames]
    power = np.mean(frames.astype(np.float64) ** 2, axis=1)
    level_db = 10.0 * np.log10(np.maximum(power, 1e-12))
    thresh_db = max(-52.0, float(np.max(level_db)) - 28.0)
    active = level_db > thresh_db

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
    voiced_mask = peak_val >= 0.38
    voiced_lags = (lag_lo + peak_idx)[voiced_mask]

    if voiced_lags.size >= 3:
        f0_vals = sr16 / voiced_lags.astype(np.float64)
        f0_vals = f0_vals[(f0_vals >= 72.0) & (f0_vals <= 350.0)]
        f0_median = float(np.median(f0_vals)) if f0_vals.size > 0 else 150.0
        if f0_vals.size >= 4:
            st = 12.0 * np.log2(f0_vals / 100.0)
            pitch_spread = float(np.percentile(st, 85) - np.percentile(st, 15))
        else:
            pitch_spread = 2.5
        r_max = float(np.clip(np.median(peak_val[voiced_mask]), 0.4, 0.98))
        hnr_db = float(10.0 * np.log10(r_max / max(1.0 - r_max, 1e-3)))
    else:
        f0_median = 150.0
        pitch_spread = 2.5
        hnr_db = 12.0

    active_s = max(0.4, float(np.sum(active)) * 0.010)
    smooth_lvl = np.convolve(level_db, np.ones(5) / 5.0, mode="same")
    peaks, _ = sp_signal.find_peaks(smooth_lvl, height=thresh_db + 3.0, distance=8)
    rate_hz = float(np.clip(len(peaks) / active_s, 2.5, 6.8))

    env_log = extract_cepstral_envelope(samples, sample_rate)
    freqs = np.linspace(0, sample_rate / 2.0, env_log.size)
    band = (freqs >= 250.0) & (freqs <= 3800.0)
    weights = np.exp(env_log[band] - np.max(env_log[band]))
    formant_centroid = float(np.sum(freqs[band] * weights) / (np.sum(weights) + 1e-9))

    mid_band = (freqs >= 400.0) & (freqs <= 2400.0)
    pres_band = (freqs >= 2800.0) & (freqs <= 6000.0)
    presence_db = float((np.mean(env_log[pres_band]) - np.mean(env_log[mid_band])) * 8.6858896)

    return {
        "f0": round(f0_median, 1),
        "pitch_spread_st": round(pitch_spread, 2),
        "rate_hz": round(rate_hz, 2),
        "formant_centroid": round(formant_centroid, 1),
        "hnr_db": round(hnr_db, 2),
        "presence_db": round(presence_db, 2),
        "envelope": [round(float(x), 4) for x in env_log],
    }


def apply_voice_clone_timbre(
    src_samples: np.ndarray,
    base_voice_id: str,
    clone_profile: dict,
    timbre_strength: float = 0.92,
    sample_rate: int = TARGET_SR,
    clones_dir: Optional[str] = None,
) -> np.ndarray:
    """
    Transform synthesized base speech so its vocal tract resonance (formants F1..F4),
    spectral envelope, harmonic chestiness, and high-frequency presence match the cloned
    speaker's reference recording.
    """
    if src_samples.size < STFT_NPERSEG * 2:
        return src_samples

    target_env_list = clone_profile.get("envelope")
    c_dir = clones_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "clones")
    ref_wav = os.path.join(c_dir, f"{clone_profile.get('id', '')}.wav")
    if os.path.exists(ref_wav) and (not target_env_list or len(target_env_list) != (STFT_NPERSEG // 2 + 1)):
        with open(ref_wav, "rb") as f:
            ref_samples = decode_audio_bytes(f.read(), sample_rate)
        target_env = extract_cepstral_envelope(ref_samples, sample_rate)
        clone_profile["envelope"] = [round(float(x), 4) for x in target_env]
    elif target_env_list and len(target_env_list) == (STFT_NPERSEG // 2 + 1):
        target_env = np.array(target_env_list, dtype=np.float32)
    else:
        return src_samples

    src_env = extract_cepstral_envelope(src_samples, sample_rate)
    if base_voice_id not in BASE_ENVELOPES_CACHE:
        BASE_ENVELOPES_CACHE[base_voice_id] = src_env.copy()
    else:
        BASE_ENVELOPES_CACHE[base_voice_id] = (
            0.5 * BASE_ENVELOPES_CACHE[base_voice_id] + 0.5 * src_env
        )
    base_env = 0.65 * src_env + 0.35 * BASE_ENVELOPES_CACHE[base_voice_id]

    freqs = np.linspace(0.0, sample_rate / 2.0, target_env.size, dtype=np.float32)
    band = (freqs >= 250.0) & (freqs <= 3800.0)
    t_weights = np.exp(target_env[band] - np.max(target_env[band]))
    measured_target_centroid = float(np.sum(freqs[band] * t_weights) / (np.sum(t_weights) + 1e-9))
    s_weights = np.exp(base_env[band] - np.max(base_env[band]))
    measured_src_centroid = float(np.sum(freqs[band] * s_weights) / (np.sum(s_weights) + 1e-9))

    warp_ratio = float(np.clip(measured_target_centroid / max(measured_src_centroid, 300.0), 0.84, 1.18))

    _, _, Zxx = sp_signal.stft(
        src_samples, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    mag = np.abs(Zxx) + 1e-8
    phase = np.angle(Zxx)
    n_bins, n_frames = mag.shape

    bins = np.arange(n_bins, dtype=np.float32)

    low_taper = np.clip((freqs - 85.0) / 95.0, 0.0, 1.0)
    high_taper = np.clip((7400.0 - freqs) / 1400.0, 0.0, 1.0)
    formant_mask = (low_taper * high_taper).astype(np.float32)

    # Target envelope is ALREADY at the cloned speaker's true formant frequencies!
    # Do NOT warp target_env away from its true frequencies.
    max_transfer_nepers = 14.5 / 8.6858896
    diff_log_env = np.clip(
        timbre_strength * (target_env - base_env) * formant_mask,
        -max_transfer_nepers,
        max_transfer_nepers,
    )[:, None]

    lifter = np.zeros(STFT_NPERSEG, dtype=np.float64)
    lifter[:CEPSTRAL_LIFTER] = 1.0
    lifter[-CEPSTRAL_LIFTER + 1 :] = 1.0
    taper = 8
    for k in range(taper):
        w = 0.5 * (1.0 + math.cos(math.pi * k / taper))
        lifter[CEPSTRAL_LIFTER - taper + k] = w
        lifter[-(CEPSTRAL_LIFTER - taper + k)] = w

    frame_log = np.log(mag)
    cep = np.fft.irfft(frame_log, n=STFT_NPERSEG, axis=0)
    inst_env = np.real(np.fft.rfft(cep * lifter[:, None], n=STFT_NPERSEG, axis=0))

    if n_frames >= 3:
        inst_env_smooth = inst_env.copy()
        inst_env_smooth[:, 1:-1] = (
            0.25 * inst_env[:, :-2] + 0.50 * inst_env[:, 1:-1] + 0.25 * inst_env[:, 2:]
        )
    else:
        inst_env_smooth = inst_env

    # Warp only the zero-mean dynamic phoneme variations (inst_env_smooth - base_env)
    # so vowel transitions track the speaker's vocal tract scale while mean envelope = target_env
    eff_warp = 1.0 + 0.65 * (warp_ratio - 1.0) * formant_mask
    warped_bins = bins / eff_warp
    dyn_variation = inst_env_smooth - base_env[:, None]
    inst_delta = np.zeros_like(inst_env_smooth)
    for t in range(n_frames):
        w_var = np.interp(warped_bins, bins, dyn_variation[:, t])
        inst_delta[:, t] = timbre_strength * (w_var - dyn_variation[:, t]) * formant_mask

    total_delta = np.clip(diff_log_env + inst_delta, -max_transfer_nepers, max_transfer_nepers)
    new_mag = mag * np.exp(total_delta)

    Zxx_mod = new_mag * np.exp(1j * phase)
    _, y_out = sp_signal.istft(
        Zxx_mod, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    y_out = y_out[: src_samples.size].astype(np.float32)

    target_f0 = float(clone_profile.get("f0", 140.0))
    if target_f0 < 155.0:
        sos_sub = sp_signal.butter(
            2, [80.0 / (sample_rate / 2.0), 250.0 / (sample_rate / 2.0)], btype="bandpass", output="sos"
        )
        sub_band = sp_signal.sosfiltfilt(sos_sub, y_out)
        chest_gain = min(0.28, max(0.06, (160.0 - target_f0) / 160.0)) * timbre_strength
        y_out = y_out + chest_gain * sub_band.astype(np.float32)

    return y_out


def apply_persona_formant_warp(
    src_samples: np.ndarray,
    warp_ratio: float,
    sample_rate: int = TARGET_SR,
) -> np.ndarray:
    """
    VoiceStudio Persona Formant Warping:
    Shifts vocal tract resonance formants (F1..F4 in 180Hz..4200Hz) without altering glottal
    harmonic pitch or unvoiced sibilants (>4.5kHz).
    """
    if abs(warp_ratio - 1.0) < 0.012 or src_samples.size < 2048:
        return src_samples

    _, _, Zxx = sp_signal.stft(
        src_samples, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    mag = np.abs(Zxx) + 1e-8
    phase = np.angle(Zxx)
    n_bins, n_frames = mag.shape
    bins = np.arange(n_bins, dtype=np.float32)
    freqs = np.linspace(0.0, sample_rate / 2.0, n_bins, dtype=np.float32)

    low_taper = np.clip((freqs - 140.0) / 140.0, 0.0, 1.0)
    high_taper = np.clip((5000.0 - freqs) / 1100.0, 0.0, 1.0)
    formant_mask = (low_taper * high_taper).astype(np.float32)

    lifter = np.zeros(STFT_NPERSEG, dtype=np.float64)
    lifter[:CEPSTRAL_LIFTER] = 1.0
    lifter[-CEPSTRAL_LIFTER + 1 :] = 1.0
    taper = 8
    for k in range(taper):
        w = 0.5 * (1.0 + math.cos(math.pi * k / taper))
        lifter[CEPSTRAL_LIFTER - taper + k] = w
        lifter[-(CEPSTRAL_LIFTER - taper + k)] = w

    frame_log = np.log(mag)
    cep = np.fft.irfft(frame_log, n=STFT_NPERSEG, axis=0)
    inst_env = np.real(np.fft.rfft(cep * lifter[:, None], n=STFT_NPERSEG, axis=0))

    if n_frames >= 3:
        inst_env_smooth = inst_env.copy()
        inst_env_smooth[:, 1:-1] = (
            0.25 * inst_env[:, :-2] + 0.50 * inst_env[:, 1:-1] + 0.25 * inst_env[:, 2:]
        )
    else:
        inst_env_smooth = inst_env

    eff_warp = 1.0 + (warp_ratio - 1.0) * formant_mask
    warped_bins = bins / eff_warp
    max_nepers = 8.5 / 8.6858896
    delta_env = np.zeros_like(inst_env_smooth)
    for t in range(n_frames):
        w_env = np.interp(warped_bins, bins, inst_env_smooth[:, t])
        delta_env[:, t] = np.clip((w_env - inst_env_smooth[:, t]) * formant_mask, -max_nepers, max_nepers)

    new_mag = mag * np.exp(delta_env)

    Zxx_mod = new_mag * np.exp(1j * phase)
    _, y_out = sp_signal.istft(
        Zxx_mod, fs=sample_rate, nperseg=STFT_NPERSEG, noverlap=STFT_NOVERLAP
    )
    y_out = y_out[: src_samples.size].astype(np.float32)

    if warp_ratio < 0.96:
        sos_sub = sp_signal.butter(
            2, [85.0 / (sample_rate / 2.0), 220.0 / (sample_rate / 2.0)], btype="bandpass", output="sos"
        )
        sub_band = sp_signal.sosfiltfilt(sos_sub, y_out)
        y_out = y_out + float((0.97 - warp_ratio) * 1.1) * sub_band.astype(np.float32)

    return y_out


_ENG_TO_MN_TTS_MAP: List[Tuple[str, str]] = [
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

_MN_ACRONYM_AND_SYMBOL_TTS_MAP: List[Tuple[str, str]] = [
    (r"%-ийн\b", " хувийн"),
    (r"%-ийг\b", " хувийг"),
    (r"%-иар\b", " хувиар"),
    (r"%-д\b", " хувьд"),
    (r"%-тай\b", " хувьтай"),
    (r"%", " хувь "),
    (r"₮-ийн\b", " төгрөгийн"),
    (r"₮-өөр\b", " төгрөгөөр"),
    (r"₮", " төгрөг "),
    (r"\$", " доллар "),
    (r"€", " евро "),
    (r"¥", " иен "),
    (r"(?:°C|℃)", " хэм "),
    (r"\bкм/ц\b", "километр цаг"),
    (r"\bм/с\b", "метр секунд"),
    (r"№\s*(\d+)", r"\1 дүгээр"),
    (r"\bУБ-ын\b", "Улаанбаатарын"),
    (r"\bУБ-т\b", "Улаанбаатарт"),
    (r"\bУБ-аас\b", "Улаанбаатараас"),
    (r"\bУБ\b", "Улаанбаатар"),
    (r"\bМУИС-ийн\b", "Монгол Улсын Их Сургуулийн"),
    (r"\bМУИС-д\b", "Монгол Улсын Их Сургуульд"),
    (r"\bМУИС\b", "Монгол Улсын Их Сургууль"),
    (r"\bШУТИС-ийн\b", "Шинжлэх Ухаан Технологийн Их Сургуулийн"),
    (r"\bШУТИС-д\b", "Шинжлэх Ухаан Технологийн Их Сургуульд"),
    (r"\bШУТИС\b", "Шинжлэх Ухаан Технологийн Их Сургууль"),
    (r"\bУИХ-ын\b", "Улсын Их Хурлын"),
    (r"\bУИХ-аас\b", "Улсын Их Хурлаас"),
    (r"\bУИХ\b", "Улсын Их Хурал"),
    (r"\bХХК-ийн\b", "хязгаарлагдмал хариуцлагатай компанийн"),
    (r"\bХХК\b", "хязгаарлагдмал хариуцлагатай компани"),
    (r"\bТББ\b", "төрийн бус байгууллага"),
    (r"\bАНУ-ын\b", "Америкийн Нэгдсэн Улсын"),
    (r"\bАНУ-д\b", "Америкийн Нэгдсэн Улсад"),
    (r"\bАНУ\b", "Америкийн Нэгдсэн Улс"),
    (r"\bБНХАУ\b", "Бүгд Найрамдах Хятад Ард Улс"),
    (r"\bОХУ\b", "Оросын Холбооны Улс"),
    (r"\bБНСУ\b", "Бүгд Найрамдах Солонгос Улс"),
]


def prepare_tts_text_for_voice(text: str, base_voice: str) -> str:
    """Adapt Mongolian symbols, numbers, acronyms, and English loanwords for natural neural TTS pronunciation."""
    if not base_voice.startswith("mn-MN"):
        return text
    out = text
    out = re.sub(r"(?<=\d),(?=\d{3}\b)", "", out)
    for pat, repl in _MN_ACRONYM_AND_SYMBOL_TTS_MAP:
        out = re.sub(pat, repl, out)
    for pat, repl in _ENG_TO_MN_TTS_MAP:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"\s+[—–-]\s+", ", ", out)
    out = re.sub(r"\.{3,}", ". ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


_CYR_TO_LAT_SAPI = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "ye", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "ө": "u", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ү": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "Ye", "Ё": "Yo",
    "Ж": "J", "З": "Z", "И": "I", "Й": "I", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "Ө": "U", "П": "P", "Р": "R", "С": "S", "Т": "T",
    "У": "U", "Ү": "U", "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh",
    "Щ": "Sh", "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E", "Ю": "Yu", "Я": "Ya",
})


def synthesize_offline_fallback(
    text: str,
    gender: str = "female",
    rate_percent: int = 0,
    pitch_hz: int = 0,
    target_sr: int = TARGET_SR,
) -> np.ndarray:
    """
    Offline local TTS fallback when internet / Edge-TTS is unreachable or offline_only is enabled.
    On Windows, uses System.Speech.Synthesis (SAPI5) with phonetic transliteration if no Cyrillic
    voice is installed, or falls back to a harmonic formant-synthesized vocal waveform.
    """
    if os.name == "nt":
        tmp_wav = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                tmp_wav = tf.name
            sapi_rate = int(np.clip(round(rate_percent / 12.0), -5, 5))
            sapi_gender = "Female" if gender == "female" else "Male"
            phonetic_text = text.translate(_CYR_TO_LAT_SAPI)
            safe_text = phonetic_text.replace("'", " ").replace('"', " ")
            ps_script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::{sapi_gender}); "
                f"$s.Rate = {sapi_rate}; "
                f"$s.SetOutputToWaveFile('{tmp_wav}'); "
                f"$s.Speak('{safe_text}'); "
                "$s.Dispose();"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                timeout=12,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            if os.path.isfile(tmp_wav) and os.path.getsize(tmp_wav) > 1000:
                with open(tmp_wav, "rb") as f:
                    samples = decode_audio_bytes(f.read(), target_sr)
                if samples.size > target_sr // 4:
                    return samples
        except Exception:
            pass
        finally:
            if tmp_wav and os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass

    # Pure DSP formant vocal fallback (guaranteed zero external dependencies)
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    dur_s = float(np.clip(len(words) * 0.38, 1.2, 12.0))
    n_samples = int(target_sr * dur_s)
    t = np.linspace(0.0, dur_s, n_samples, endpoint=False)
    base_f0 = (195.0 if gender == "female" else 115.0) + float(pitch_hz)
    f0_curve = base_f0 * (1.0 + 0.04 * np.sin(2.0 * math.pi * 2.2 * t) - 0.06 * (t / dur_s))
    phase = 2.0 * math.pi * np.cumsum(f0_curve) / target_sr
    glottal = np.zeros_like(t)
    for h in range(1, 16):
        glottal += (1.0 / (h ** 1.35)) * np.sin(h * phase)
    syl_env = 0.65 + 0.35 * np.sin(2.0 * math.pi * 3.8 * t)
    sig = (glottal * syl_env).astype(np.float32)
    return normalize_audio_np(sig, -3.0)
