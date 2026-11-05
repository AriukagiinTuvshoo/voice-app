"""
AI Audio Vocal & Instrumental Separation Engine.

Implements high-fidelity STFT-based Center-Channel Mid/Side Pan Masking combined with
2D Harmonic-Percussive Source Separation (HPSS median filtering) and Vocal Formant Bandpass.
Designed for 100% local-first, low-memory operation without crashing on limited RAM
or triggering Windows Defender / Application Control policy blocks.
"""

from __future__ import annotations

import io
import os
import shutil
import uuid
from typing import Dict, Tuple

import numpy as np
import scipy.ndimage as ndimage
import scipy.signal as sps
import soundfile as sf


STEMS_DIR = os.path.join(os.path.dirname(__file__), "stems")
os.makedirs(STEMS_DIR, exist_ok=True)


def separate_audio_stems(
    audio_path_or_bytes: str | bytes,
    target_sr: int = 44100,
    vocal_isolation_strength: float = 1.3,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Separate an audio track into (vocals, instrumental, sample_rate) using:
    1. Stereo Mid/Side center-channel pan masking
    2. 2D Harmonic-Percussive Source Separation (HPSS) to suppress drums/hi-hats
    3. Smooth vocal frequency-band masking (95 Hz - 7600 Hz)
    """
    if isinstance(audio_path_or_bytes, bytes):
        data, sr = sf.read(io.BytesIO(audio_path_or_bytes), dtype="float32")
    else:
        data, sr = sf.read(audio_path_or_bytes, dtype="float32")

    if data.ndim == 1:
        is_mono = True
        stereo_data = np.stack([data, data], axis=-1)
    else:
        is_mono = False
        stereo_data = data[:, :2] if data.shape[1] >= 2 else np.stack([data[:, 0], data[:, 0]], axis=-1)

    left = stereo_data[:, 0]
    right = stereo_data[:, 1]
    n_samples = len(left)

    chunk_size = sr * 60
    hop_length = 512
    n_fft = 2048

    vocals_left_out = np.zeros(n_samples, dtype=np.float32)
    vocals_right_out = np.zeros(n_samples, dtype=np.float32)

    for start_idx in range(0, n_samples, chunk_size):
        end_idx = min(start_idx + chunk_size, n_samples)
        chunk_l = left[start_idx:end_idx]
        chunk_r = right[start_idx:end_idx]

        _, _, stft_l = sps.stft(chunk_l, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length)
        _, _, stft_r = sps.stft(chunk_r, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length)

        mid = (stft_l + stft_r) * 0.5
        side = (stft_l - stft_r) * 0.5

        mag_mid = np.abs(mid)
        mag_side = np.abs(side)
        eps = 1e-7

        # 1. Smooth vocal frequency band mask (95 Hz to 7600 Hz with cosine-like tapers)
        freqs = np.linspace(0, sr / 2, mag_mid.shape[0], dtype=np.float32)
        low_taper = np.clip((freqs - 75.0) / 55.0, 0.0, 1.0)
        high_taper = np.clip((8200.0 - freqs) / 900.0, 0.0, 1.0)
        freq_mask = (low_taper * high_taper)[:, None]

        # 2. 2D Harmonic-Percussive Source Separation (HPSS) on Mid channel magnitude
        if mag_mid.shape[1] >= 9:
            harm_mag = ndimage.median_filter(mag_mid, size=(1, 9))
            perc_mag = ndimage.median_filter(mag_mid, size=(9, 1))
            h2 = harm_mag ** 2
            p2 = perc_mag ** 2
            hpss_mask = (h2 + 0.25 * p2) / (h2 + p2 + eps)
        else:
            hpss_mask = np.ones_like(mag_mid)

        # 3. Center pan mask (higher when mid dominates side)
        pan_ratio = mag_mid / (mag_mid + mag_side + eps)
        pan_mask = np.power(np.clip(pan_ratio, 0.0, 1.0), vocal_isolation_strength)

        vocal_mask = pan_mask * hpss_mask * freq_mask + (pan_mask * 0.10) * (1.0 - freq_mask)
        vocal_mask = np.clip(vocal_mask, 0.0, 1.0)

        vocal_stft = mid * vocal_mask

        _, v_l = sps.istft(vocal_stft, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length)
        v_l = v_l[: len(chunk_l)]
        if len(v_l) < len(chunk_l):
            v_l = np.pad(v_l, (0, len(chunk_l) - len(v_l)))

        vocals_left_out[start_idx:end_idx] = v_l
        vocals_right_out[start_idx:end_idx] = v_l

    inst_left_out = left - vocals_left_out
    inst_right_out = right - vocals_right_out

    max_v = max(float(np.max(np.abs(vocals_left_out))), 1e-6)
    max_i = max(float(np.max(np.abs(inst_left_out))), 1e-6)
    if max_v > 0.98:
        vocals_left_out = (vocals_left_out / max_v) * 0.95
        vocals_right_out = (vocals_right_out / max_v) * 0.95
    if max_i > 0.98:
        inst_left_out = (inst_left_out / max_i) * 0.95
        inst_right_out = (inst_right_out / max_i) * 0.95

    if is_mono:
        vocals = vocals_left_out
        instrumental = inst_left_out
    else:
        vocals = np.stack([vocals_left_out, vocals_right_out], axis=-1)
        instrumental = np.stack([inst_left_out, inst_right_out], axis=-1)

    return vocals, instrumental, sr


def extract_vocals_for_lyrics(input_audio_path: str, output_wav_path: str, strength: float = 1.25) -> bool:
    """
    Pre-isolate vocals into a mono 16kHz WAV file to boost Auto-Lyrics STT accuracy
    on songs with loud drums, bass, or stereo accompaniment.
    """
    try:
        vocals, _, sr = separate_audio_stems(input_audio_path, vocal_isolation_strength=strength)
        if vocals.ndim > 1:
            vocals_mono = vocals.mean(axis=1)
        else:
            vocals_mono = vocals
        # Mix 78% isolated vocal + 22% original center so consonants stay crisp for Whisper
        orig, _ = sf.read(input_audio_path, dtype="float32")
        orig_mono = orig.mean(axis=1) if orig.ndim > 1 else orig
        min_len = min(len(vocals_mono), len(orig_mono))
        blended = 0.78 * vocals_mono[:min_len] + 0.22 * orig_mono[:min_len]
        peak = float(np.max(np.abs(blended)))
        if peak > 1e-5:
            blended = (blended / peak) * 0.92
        sf.write(output_wav_path, blended.astype(np.float32), sr, subtype="PCM_16")
        return os.path.isfile(output_wav_path) and os.path.getsize(output_wav_path) > 500
    except Exception:
        return False


def process_separation_job(
    audio_bytes: bytes,
    original_filename: str = "track.mp3",
    vocal_strength: float = 1.3,
) -> Dict[str, str | float | int]:
    """
    Run separation on uploaded audio and save to stems directory.
    Returns dictionary with job metadata and stem URLs.
    """
    job_id = f"sep_{uuid.uuid4().hex[:8]}"
    job_dir = os.path.join(STEMS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    vocals, instrumental, sr = separate_audio_stems(audio_bytes, vocal_isolation_strength=vocal_strength)

    vocals_path = os.path.join(job_dir, "vocals.wav")
    instrumental_path = os.path.join(job_dir, "instrumental.wav")

    sf.write(vocals_path, vocals, sr, subtype="PCM_16")
    sf.write(instrumental_path, instrumental, sr, subtype="PCM_16")

    duration_s = round(float(len(vocals)) / sr, 2)

    return {
        "job_id": job_id,
        "status": "success",
        "duration": duration_s,
        "sample_rate": sr,
        "vocals_url": f"/api/audio/stems/{job_id}/vocals",
        "instrumental_url": f"/api/audio/stems/{job_id}/instrumental",
    }


def cleanup_stems(job_id: str) -> bool:
    """Clean up temporary separated stem files."""
    if not job_id or not job_id.startswith("sep_"):
        return False
    clean_id = os.path.basename(job_id)
    job_dir = os.path.join(STEMS_DIR, clean_id)
    if os.path.isdir(job_dir):
        shutil.rmtree(job_dir, ignore_errors=True)
        return True
    return False
