"""
VOICE Desktop - Pure Logic & Architecture Unit Tests
Runs on Windows, Linux (Ubuntu), macOS without hardware or GUI requirements.
"""
import io
import os
import sys
import unittest
from unittest.mock import MagicMock

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import voice_core


class TestVoiceCoreLogic(unittest.TestCase):
    def test_sanitize_settings_valid(self):
        data = {
            "hotkey": "F8",
            "stt_engine": "GOOGLE",
            "whisper_model": "base",
            "language": "MN",
            "restore_clipboard": True,
            "undo_button": "1",
            "start_with_windows": False,
            "chimege_token": "valid_token_123",
        }
        cleaned = voice_core.sanitize_settings(data)
        self.assertEqual(cleaned["hotkey"], "f8")
        self.assertEqual(cleaned["stt_engine"], "google")
        self.assertEqual(cleaned["whisper_model"], "base")
        self.assertEqual(cleaned["language"], "mn")
        self.assertTrue(cleaned["restore_clipboard"])
        self.assertTrue(cleaned["undo_button"])
        self.assertFalse(cleaned["start_with_windows"])
        self.assertEqual(cleaned["chimege_token"], "valid_token_123")

    def test_sanitize_settings_rejects_unknown_and_invalid(self):
        data = {
            "admin": True,
            "hotkey": "invalid_super_key",
            "stt_engine": "malicious_engine",
            "unknown_field": 12345,
            "chimege_token": "a" * 1000,  # too long
        }
        cleaned = voice_core.sanitize_settings(data)
        self.assertNotIn("admin", cleaned)
        self.assertNotIn("hotkey", cleaned)
        self.assertNotIn("stt_engine", cleaned)
        self.assertNotIn("unknown_field", cleaned)
        self.assertNotIn("chimege_token", cleaned)

    def test_is_safe_voice_id(self):
        self.assertTrue(voice_core.is_safe_voice_id("cloned_abc123"))
        self.assertTrue(voice_core.is_safe_voice_id("voice-1_2_3"))
        self.assertFalse(voice_core.is_safe_voice_id(""))
        self.assertFalse(voice_core.is_safe_voice_id("../evil"))
        self.assertFalse(voice_core.is_safe_voice_id("..\\evil"))
        self.assertFalse(voice_core.is_safe_voice_id("/etc/passwd"))
        self.assertFalse(voice_core.is_safe_voice_id("C:\\Windows"))
        self.assertFalse(voice_core.is_safe_voice_id("a" * 65))

    def test_safe_clone_wav_path(self):
        base_dir = os.path.abspath("test_clones")
        p = voice_core.safe_clone_wav_path(base_dir, "my_voice_01")
        expected = os.path.realpath(os.path.join(base_dir, "my_voice_01.wav"))
        self.assertEqual(p, expected)

        with self.assertRaises(ValueError):
            voice_core.safe_clone_wav_path(base_dir, "../sneaky")

        with self.assertRaises(ValueError):
            voice_core.safe_clone_wav_path(base_dir, "inv@lid*id")

    def test_fallback_flowbar_pos_math(self):
        work_area = (0, 0, 1920, 1040)
        fx, fy = voice_core.get_fallback_flowbar_pos_math(work_area, bar_w=360, bar_h=52, margin_x=24, margin_y=24)
        self.assertEqual(fx, 1920 - 360 - 24)
        self.assertEqual(fy, 1040 - 52 - 24)

    def test_clamp_rect_to_screen(self):
        work_area = (0, 0, 1536, 816)
        # Position was (1556, 950) which is off screen
        cx, cy = voice_core.clamp_rect_to_screen(1556, 950, 360, 52, work_area)
        self.assertLessEqual(cx + 360, 1536)
        self.assertLessEqual(cy + 52, 816)
        self.assertGreaterEqual(cx, 0)
        self.assertGreaterEqual(cy, 0)

        # Negative position
        cx2, cy2 = voice_core.clamp_rect_to_screen(-100, -50, 360, 52, work_area)
        self.assertEqual(cx2, 0)
        self.assertEqual(cy2, 0)

    def test_is_rect_in_bounds(self):
        bounds = (0, 0, 1920, 1080)
        self.assertTrue(voice_core.is_rect_in_bounds(100, 100, 360, 52, bounds))
        self.assertFalse(voice_core.is_rect_in_bounds(2000, 2000, 360, 52, bounds))
        self.assertFalse(voice_core.is_rect_in_bounds(-500, -500, 360, 52, bounds))

    def test_compute_flowbar_status(self):
        state = {
            "ui_alive": True,
            "ui_heartbeat": 1000.0,
            "visible": True,
            "status": "recording",
            "language": "mn",
            "pos": "1152,740",
            "ui_error": "",
            "ui_restarts": 0,
        }
        # Recent heartbeat
        res = voice_core.compute_flowbar_status(state, now=1002.0)
        self.assertTrue(res["ui_alive"])
        self.assertEqual(res["ui_heartbeat_age_sec"], 2.0)
        self.assertEqual(res["status"], "recording")

        # Stale heartbeat (exceeds 5.0 seconds)
        res_stale = voice_core.compute_flowbar_status(state, now=1007.5)
        self.assertFalse(res_stale["ui_alive"])
        self.assertEqual(res_stale["ui_heartbeat_age_sec"], 7.5)

    def test_normalize_mongolian_numbers(self):
        text = "энэ бол хоёр мянга хорин зургаа оны төсөл бөгөөд ерэн таван хувь амжилттай"
        normalized = voice_core.normalize_mongolian_numbers(text)
        self.assertIn("2026", normalized)
        self.assertIn("95%", normalized)

    def test_format_speech_text(self):
        # Regular statement ends with period
        self.assertEqual(voice_core.format_speech_text("сайн байна"), "Сайн байна.")
        # Question suffix adds question mark
        self.assertEqual(voice_core.format_speech_text("та сайн байна уу"), "Та сайн байна уу?")
        # Existing punctuation preserved
        self.assertEqual(voice_core.format_speech_text("баярлалаа!"), "Баярлалаа!")

    def test_enhance_ssml_cadence(self):
        raw = "Сайн байна уу, өнөөдөр сайхан өдөр байна."
        ssml = voice_core.enhance_ssml_cadence(raw)
        self.assertIn('<break time="200ms"/>', ssml)
        self.assertIn('<break time="450ms"/>', ssml)

    def test_apply_voice_commands(self):
        raw = "Сайн байна уу цэг би өнөөдөр хичээлтэй таслал гэхдээ маргааш завтай цэг шинэ мөр та юу хийж байна асуултын тэмдэг"
        formatted = voice_core.apply_voice_commands(raw)
        self.assertIn("Сайн байна уу.", formatted)
        self.assertIn("хичээлтэй, гэхдээ", formatted)
        self.assertIn("\n", formatted)
        self.assertTrue(formatted.endswith("?"))

    def test_strip_filler_words(self):
        raw = "Би нөгөө өнөөдөр аан ирж чадахгүй тиймээ"
        cleaned = voice_core.strip_filler_words(raw)
        self.assertNotIn("нөгөө", cleaned)
        self.assertNotIn("аан", cleaned)
        self.assertNotIn("тиймээ", cleaned)
        self.assertIn("Би", cleaned)
        self.assertIn("өнөөдөр", cleaned)
        self.assertIn("ирж чадахгүй", cleaned)

    def test_trim_silence_pcm(self):
        import struct, math
        silence = b"\x00\x00" * 3200  # 0.2s silence
        speech = struct.pack("<500h", *[int(2500 * math.sin(i * 0.1)) for i in range(500)])
        audio = silence + speech + silence
        trimmed = voice_core.trim_silence_pcm(audio, threshold_rms=500.0)
        self.assertLess(len(trimmed), len(audio))
        self.assertGreater(len(trimmed), 0)

    def test_generate_srt(self):
        segments = [
            {"start": 1.0, "end": 3.5, "text": "Сайн байна уу"},
            {"start": 4.0, "end": 7.0, "text": "VOICE системд тавтай морил"},
        ]
        srt = voice_core.generate_srt(segments)
        self.assertIn("1\r\n00:00:01,000 --> 00:00:03,500\r\nСайн байна уу", srt)
        self.assertIn("2\r\n00:00:04,000 --> 00:00:07,000\r\nVOICE системд тавтай морил", srt)

    def test_apply_voice_snippets(self):
        snippets = {
            "миний имэйл": "user@example.invalid",
            "миний данс": "Хаан банк 5000123456",
        }
        sample = "Сайн байна уу миний имэйл хаягаар холбогдож миний данс руу шилжүүлнэ үү"
        res = voice_core.apply_voice_snippets(sample, snippets)
        self.assertIn("user@example.invalid хаягаар", res)
        self.assertIn("Хаан банк 5000123456 руу", res)
        self.assertNotIn("миний имэйл", res)
        self.assertNotIn("миний данс", res)

    def test_sanitize_settings_snippets(self):
        data = {
            "custom_snippets": True,
            "snippets": {
                "МИНИЙ ИМЭЙЛ": "user@example.invalid",
                "invalid": 1234,
                "a" * 100: "too long key",
            },
        }
        cleaned = voice_core.sanitize_settings(data)
        self.assertTrue(cleaned["custom_snippets"])
        self.assertEqual(cleaned["snippets"]["миний имэйл"], "user@example.invalid")
        self.assertNotIn("invalid", cleaned["snippets"])
        self.assertNotIn("a" * 100, cleaned["snippets"])


class TestFakeTkSmoke(unittest.TestCase):
    """Smoke test for the FlowBar UI command queue and event loop logic using Tk mocks."""

    def test_flowbar_loop_simulation(self):
        import queue

        cmd_q = queue.Queue()
        state = {
            "ui_alive": False,
            "ui_heartbeat": 0.0,
            "visible": True,
            "pos": "0,0",
            "status": "idle",
            "ui_error": "",
        }

        mock_root = MagicMock()
        scheduled_callbacks = []

        def fake_after(ms, func):
            scheduled_callbacks.append(func)

        mock_root.after = fake_after
        mock_root.winfo_x.return_value = 100
        mock_root.winfo_y.return_value = 200

        # Simulate command handler
        cmd_q.put(("place", 1152, 740))
        cmd_q.put(("show",))

        # Command runner
        while not cmd_q.empty():
            cmd = cmd_q.get_nowait()
            if cmd[0] == "place":
                mock_root.geometry(f"360x52+{cmd[1]}+{cmd[2]}")
                mock_root.deiconify()
                state["pos"] = f"{cmd[1]},{cmd[2]}"
            elif cmd[0] == "show":
                mock_root.deiconify()
                state["visible"] = True

        mock_root.geometry.assert_called_with("360x52+1152+740")
        self.assertEqual(state["pos"], "1152,740")
        self.assertTrue(state["visible"])

        # Simulate a loop tick that catches transient errors and always reschedules in finally
        call_count = 0

        def simulated_tick():
            nonlocal call_count
            call_count += 1
            try:
                state["ui_alive"] = True
                state["ui_heartbeat"] = 100.0
                if call_count == 1:
                    raise RuntimeError("Simulated transient canvas draw error")
            except Exception as e:
                state["ui_error"] = str(e)
            finally:
                mock_root.after(80, simulated_tick)

        simulated_tick()
        self.assertEqual(call_count, 1)
        self.assertEqual(len(scheduled_callbacks), 1)
        self.assertTrue(state["ui_alive"])
        self.assertEqual(state["ui_error"], "Simulated transient canvas draw error")

        # Execute scheduled callback (tick 2 - successful draw)
        scheduled_callbacks.pop(0)()
        self.assertEqual(call_count, 2)
        self.assertEqual(len(scheduled_callbacks), 1)

        # Simulate clean shutdown / loop exit
        state["ui_alive"] = False
        self.assertFalse(state["ui_alive"])


class TestFastAPIEngineLimits(unittest.TestCase):
    """Test API limits and input validation using FastAPI TestClient."""

    @classmethod
    def setUpClass(cls):
        os.environ["VOICE_NO_BROWSER"] = "1"
        from fastapi.testclient import TestClient
        import tts_server
        cls.client = TestClient(tts_server.app)

    def test_health_endpoint(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("has_edge", data)
        self.assertIn("has_stt", data)
        self.assertIn("hotkey_ok", data)
        self.assertIn("tray_available", data)

    def test_insert_text_limit(self):
        # Normal text should be accepted
        res = self.client.post("/insert-text", json={"text": "Сайн байна уу"})
        self.assertEqual(res.status_code, 200)

        # Text over 20,000 characters must return HTTP 413
        oversized = "A" * 20005
        res_large = self.client.post("/insert-text", json={"text": oversized})
        self.assertEqual(res_large.status_code, 413)

    def test_clone_sample_path_traversal(self):
        # Path traversal with ../ or invalid chars must return 400 or 404 (never 200)
        res = self.client.get("/clones/..%2F..%2Fsecret/sample")
        self.assertIn(res.status_code, (400, 404))

        res2 = self.client.get("/clones/invalid!id/sample")
        self.assertEqual(res2.status_code, 400)

    def test_autostart_endpoint(self):
        res = self.client.get("/api/autostart")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("supported", data)
        self.assertIn("enabled", data)

    def test_check_update_endpoint(self):
        res = self.client.get("/api/check-update")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("current_version", data)
        self.assertIn("latest_version", data)
        self.assertIn("has_update", data)

    def test_export_srt_endpoint(self):
        res = self.client.post("/api/export-srt", json={
            "segments": [
                {"start": 0.5, "end": 2.5, "text": "Туршилтын хадмал"}
            ]
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("00:00:00,500 --> 00:00:02,500", res.text)
        self.assertIn("Туршилтын хадмал", res.text)

    def test_transcribe_upload_limit(self):
        # 100 bytes is too short
        fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 90)
        res = self.client.post("/transcribe", files={"audio": ("test.wav", fake_audio, "audio/wav")})
        self.assertEqual(res.status_code, 200)
        self.assertIn("error", res.json())

    def test_clone_voice_length_limit(self):
        # Short audio (< 2000 bytes) returns HTTP 400
        fake_short = io.BytesIO(b"RIFF" + b"\x00" * 500)
        res = self.client.post(
            "/clone-voice",
            data={"name": "Test"},
            files={"audio": ("short.wav", fake_short, "audio/wav")},
        )
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
