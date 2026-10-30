"""
Unit tests for Stage 4:
- Local Voice Profile Management & Consent Validation
- Acoustic Timbre Transfer & Model Feasibility Status
- Karaoke ASS (Advanced SubStation Alpha) Generation & Aegisub standard
- AI Vocal & Instrumental Separation (STFT Spectral Pan)
- FastAPI Stage 4 Endpoints
"""

import io
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

import audio_separator
import karaoke_ass
import tts_server
import voice_cloning


def make_test_wav_bytes(duration_s: float = 3.5, sr: int = 16000, freq: float = 440.0) -> bytes:
    """Generate a clean sine wave in WAV format."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    samples = 0.5 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


class TestKaraokeASS(unittest.TestCase):
    def test_format_ass_timestamp(self):
        # 0s -> 0:00:00.00
        self.assertEqual(karaoke_ass.format_ass_timestamp(0.0), "0:00:00.00")
        # 1.25s -> 0:00:01.25
        self.assertEqual(karaoke_ass.format_ass_timestamp(1.25), "0:00:01.25")
        # 65.432s -> 0:01:05.43
        self.assertEqual(karaoke_ass.format_ass_timestamp(65.432), "0:01:05.43")
        # 3661.05s -> 1:01:01.05
        self.assertEqual(karaoke_ass.format_ass_timestamp(3661.05), "1:01:01.05")

    def test_seconds_to_centiseconds(self):
        self.assertEqual(karaoke_ass.seconds_to_centiseconds(0.12), 12)
        self.assertEqual(karaoke_ass.seconds_to_centiseconds(1.5), 150)
        self.assertEqual(karaoke_ass.seconds_to_centiseconds(0.0), 1)

    def test_generate_karaoke_ass_word_level(self):
        segments = [
            {
                "start": 1.0,
                "end": 3.0,
                "text": "Сайн байна уу",
                "words": [
                    {"word": "Сайн", "start": 1.0, "end": 1.5},
                    {"word": "байна", "start": 1.6, "end": 2.2},
                    {"word": "уу", "start": 2.3, "end": 2.9},
                ],
            }
        ]
        ass = karaoke_ass.generate_karaoke_ass(segments, title="Монгол Караоке")
        self.assertIn("[Script Info]", ass)
        self.assertIn("Title: Монгол Караоке", ass)
        self.assertIn("[V4+ Styles]", ass)
        self.assertIn("[Events]", ass)
        self.assertIn("Style: Karaoke", ass)
        self.assertIn(r"{\kf50}Сайн", ass)
        self.assertIn(r"{\kf60}байна", ass)
        self.assertIn(r"{\kf60}уу", ass)

    def test_generate_karaoke_ass_segment_fallback(self):
        segments = [
            {
                "start": 0.5,
                "end": 2.5,
                "text": "Энэ бол дууны үг",
            }
        ]
        ass = karaoke_ass.generate_karaoke_ass(segments, title="Fallback Test")
        self.assertIn("Dialogue: 0,0:00:00.50,0:00:02.50,Default", ass)
        self.assertIn(r"{\kf200}Энэ бол дууны үг", ass)

    def test_ffmpeg_availability(self):
        # We copied ffmpeg into tools/ffmpeg
        self.assertTrue(karaoke_ass.is_ffmpeg_available())
        path = karaoke_ass.find_system_or_bundled_ffmpeg()
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))


class TestVoiceCloningEngine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.orig_clones_dir = voice_cloning.CLONES_DIR
        self.orig_db_path = voice_cloning.VOICES_DB_PATH
        voice_cloning.CLONES_DIR = self.tmp_dir
        voice_cloning.VOICES_DB_PATH = os.path.join(self.tmp_dir, "voices.json")

    def tearDown(self):
        voice_cloning.CLONES_DIR = self.orig_clones_dir
        voice_cloning.VOICES_DB_PATH = self.orig_db_path
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_sanitize_profile_id(self):
        self.assertEqual(voice_cloning.sanitize_profile_id("valid_id-123"), "valid_id-123")
        self.assertEqual(voice_cloning.sanitize_profile_id("../../etc/passwd"), "etcpasswd")
        with self.assertRaises(ValueError):
            voice_cloning.sanitize_profile_id("...///")

    def test_validate_reference_audio(self):
        wav = make_test_wav_bytes(duration_s=4.0)
        samples, sr, dur = voice_cloning.validate_reference_audio(wav)
        self.assertEqual(sr, 16000)
        self.assertAlmostEqual(dur, 4.0, delta=0.1)

        # Too short (< 3.0s)
        short_wav = make_test_wav_bytes(duration_s=1.5)
        with self.assertRaises(ValueError):
            voice_cloning.validate_reference_audio(short_wav)

    def test_create_voice_profile_requires_consent(self):
        wav = make_test_wav_bytes(duration_s=4.0)
        # Without consent -> raises PermissionError
        with self.assertRaises(PermissionError):
            voice_cloning.create_voice_profile(name="Test Voice", audio_bytes=wav, consent=False)

        # With consent -> succeeds
        profile = voice_cloning.create_voice_profile(
            name="Батын хоолой",
            audio_bytes=wav,
            consent=True,
            ref_transcript="Сайн байна уу",
        )
        self.assertEqual(profile["name"], "Батын хоолой")
        self.assertTrue(profile["consent_given"])
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, f"{profile['id']}.wav")))

    def test_delete_voice_profile(self):
        wav = make_test_wav_bytes(duration_s=4.0)
        profile = voice_cloning.create_voice_profile(name="Устгах хоолой", audio_bytes=wav, consent=True)
        vid = profile["id"]
        wav_path = os.path.join(self.tmp_dir, f"{vid}.wav")
        self.assertTrue(os.path.isfile(wav_path))

        ok = voice_cloning.delete_voice_profile(vid)
        self.assertTrue(ok)
        self.assertFalse(os.path.isfile(wav_path))
        self.assertNotIn(vid, voice_cloning.load_voice_profiles_db())

    def test_voice_cloning_system_status(self):
        st = voice_cloning.get_voice_cloning_system_status()
        self.assertIn("active_engine", st)
        self.assertIn("models", st)
        self.assertIn("oron_tts", st["models"])
        self.assertIn("xtts_v2", st["models"])
        # License details
        self.assertEqual(st["models"]["oron_tts"]["license_weights"], "CC-BY-NC-4.0 (Non-Commercial)")
        self.assertFalse(st["models"]["xtts_v2"]["current_host_compatible"])


class TestAudioSeparator(unittest.TestCase):
    def test_separate_audio_stems(self):
        # Generate stereo sine wave: left=440Hz, right=880Hz
        sr = 22050
        duration_s = 2.0
        t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
        right = 0.5 * np.sin(2 * np.pi * 880.0 * t).astype(np.float32)
        stereo = np.stack([left, right], axis=-1)

        buf = io.BytesIO()
        sf.write(buf, stereo, sr, format="WAV")
        raw_bytes = buf.getvalue()

        vocals, instrumental, out_sr = audio_separator.separate_audio_stems(raw_bytes)
        self.assertEqual(out_sr, sr)
        self.assertEqual(len(vocals), len(stereo))
        self.assertEqual(len(instrumental), len(stereo))

    def test_process_separation_job(self):
        wav = make_test_wav_bytes(duration_s=2.5)
        job = audio_separator.process_separation_job(wav, original_filename="test_song.wav")
        self.assertEqual(job["status"], "success")
        self.assertIn("job_id", job)
        self.assertIn("vocals_url", job)
        self.assertIn("instrumental_url", job)

        # Cleanup
        cleaned = audio_separator.cleanup_stems(job["job_id"])
        self.assertTrue(cleaned)


class TestStage4Api(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(tts_server.app)

    def test_voice_profiles_crud(self):
        wav = make_test_wav_bytes(duration_s=4.0)

        # 1. Missing consent -> 400
        res = self.client.post(
            "/api/voice-profiles",
            data={"name": "Тест", "consent": "false"},
            files={"audio": ("test.wav", wav, "audio/wav")},
        )
        self.assertEqual(res.status_code, 400)

        # 2. With consent -> 200
        res = self.client.post(
            "/api/voice-profiles",
            data={"name": "Тест Хоолой", "consent": "true", "transcript": "Сайн байна уу"},
            files={"audio": ("test.wav", wav, "audio/wav")},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        profile = data["profile"]
        profile_id = profile["id"]

        # 3. List
        list_res = self.client.get("/api/voice-profiles")
        self.assertEqual(list_res.status_code, 200)
        profiles = list_res.json().get("profiles", [])
        self.assertTrue(any(p["id"] == profile_id for p in profiles))

        # 4. Stream audio
        audio_res = self.client.get(f"/api/voice-profiles/{profile_id}/audio")
        self.assertEqual(audio_res.status_code, 200)
        self.assertEqual(audio_res.headers.get("content-type"), "audio/wav")

        # 5. Delete
        del_res = self.client.delete(f"/api/voice-profiles/{profile_id}")
        self.assertEqual(del_res.status_code, 200)

    def test_voice_cloning_status_endpoint(self):
        res = self.client.get("/api/voice-cloning/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("active_engine", data)
        self.assertIn("models", data)

    def test_lyrics_export_ass_endpoint(self):
        payload = {
            "title": "Монгол Дуу",
            "segments": [
                {
                    "start": 0.5,
                    "end": 2.0,
                    "text": "Эх орон",
                    "words": [
                        {"word": "Эх", "start": 0.5, "end": 1.0},
                        {"word": "орон", "start": 1.1, "end": 2.0},
                    ],
                }
            ],
        }
        res = self.client.post("/api/lyrics/export-ass", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("[Script Info]", data["ass_content"])
        self.assertIn(r"{\kf50}Эх", data["ass_content"])
        self.assertIn(r"{\kf90}орон", data["ass_content"])

    def test_lyrics_ffmpeg_status_endpoint(self):
        res = self.client.get("/api/lyrics/ffmpeg-status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["available"])

    def test_audio_separation_api(self):
        wav = make_test_wav_bytes(duration_s=2.5)
        res = self.client.post(
            "/api/audio/separate",
            files={"audio": ("song.wav", wav, "audio/wav")},
            data={"vocal_strength": "1.2"},
        )
        self.assertEqual(res.status_code, 200)
        job = res.json()
        self.assertEqual(job["status"], "success")

        # Check vocal stream
        voc_res = self.client.get(job["vocals_url"])
        self.assertEqual(voc_res.status_code, 200)
        self.assertEqual(voc_res.headers.get("content-type"), "audio/wav")

        # Clean up
        audio_separator.cleanup_stems(job["job_id"])


if __name__ == "__main__":
    unittest.main()
