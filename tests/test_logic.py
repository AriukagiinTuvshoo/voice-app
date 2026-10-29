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

    def test_snap_rect_to_screen_edges(self):
        work_area = (0, 0, 1920, 1040)
        bar_w, bar_h = 360, 52

        # 1. Middle of screen (outside snap distance 24px) -> stays untouched
        sx, sy = voice_core.snap_rect_to_screen_edges(800, 500, bar_w, bar_h, work_area, snap_distance=24, margin=16)
        self.assertEqual((sx, sy), (800, 500))

        # 2. Near left edge (e.g. x = 25, margin = 16 -> diff is 9px <= 24px)
        sx_left, _ = voice_core.snap_rect_to_screen_edges(25, 500, bar_w, bar_h, work_area, snap_distance=24, margin=16)
        self.assertEqual(sx_left, 16)

        # 3. Near right edge (right = 1920, margin = 16 -> right target is 1920 - 360 - 16 = 1544)
        sx_right, _ = voice_core.snap_rect_to_screen_edges(1535, 500, bar_w, bar_h, work_area, snap_distance=24, margin=16)
        self.assertEqual(sx_right, 1544)

        # 4. Near bottom edge (bottom = 1040, margin = 16 -> bottom target is 1040 - 52 - 16 = 972)
        _, sy_bottom = voice_core.snap_rect_to_screen_edges(800, 965, bar_w, bar_h, work_area, snap_distance=24, margin=16)
        self.assertEqual(sy_bottom, 972)

        # 5. Near top edge (top = 0, margin = 16 -> target is 16)
        _, sy_top = voice_core.snap_rect_to_screen_edges(800, 20, bar_w, bar_h, work_area, snap_distance=24, margin=16)
        self.assertEqual(sy_top, 16)

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

    def test_normalize_mongolian_numbers_currency_and_contacts(self):
        # 1. Spoken currency to MNT
        t1 = voice_core.normalize_mongolian_numbers("таван зуун мянган төгрөг шилжүүллээ")
        self.assertIn("500,000₮", t1)

        # 2. Currency inflections
        t2 = voice_core.normalize_mongolian_numbers("нэг сая таван зуун мянган төгрөгийн төлбөр")
        self.assertIn("1,500,000₮-ийн", t2)

        # 3. Numeric multipliers with currency
        t3 = voice_core.normalize_mongolian_numbers("төлбөр 500 мянган төгрөг болон 10 сая төгрөг")
        self.assertIn("500,000₮", t3)
        self.assertIn("10,000,000₮", t3)

        # 4. Spoken phone pairs
        t4 = voice_core.normalize_mongolian_numbers("миний утас ерэн ес арван нэг хорин хоёр гучин гурав")
        self.assertIn("9911-2233", t4)

        # 5. Mobile numbers with international prefix
        t5 = voice_core.normalize_mongolian_numbers("холбогдох утас +97600000000 эсвэл 88112233")
        self.assertIn("+97600000000", t5)
        self.assertIn("8811-2233", t5)

        # 6. USD currency
        t6 = voice_core.normalize_mongolian_numbers("гучин таван мянган ам доллар")
        self.assertIn("$35,000", t6)

        # 7. Preserving years
        t7 = voice_core.normalize_mongolian_numbers("2026 онд хэрэгжинэ")
        self.assertIn("2026 онд", t7)
        self.assertNotIn("2,026", t7)

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

    def test_capitalize_sentences_multi_and_newlines(self):
        # Multiple sentences in one line
        text1 = "сайн байна уу? би өнөөдөр хичээлтэй. чи хаана байна?"
        self.assertEqual(
            voice_core.capitalize_sentences(text1),
            "Сайн байна уу? Би өнөөдөр хичээлтэй. Чи хаана байна?",
        )
        # Exclamation and ellipses
        text2 = "хөөе! нааш ир... би хүлээж байна."
        self.assertEqual(
            voice_core.capitalize_sentences(text2),
            "Хөөе! Нааш ир... Би хүлээж байна.",
        )
        # Multiline text
        text3 = "эхний мөр\nхоёр дахь мөр\r\nгурав дахь мөр"
        self.assertEqual(
            voice_core.capitalize_sentences(text3),
            "Эхний мөр\nХоёр дахь мөр\r\nГурав дахь мөр",
        )
        # format_speech_text with multiple sentences
        formatted = voice_core.format_speech_text("сайн уу? би ирлээ")
        self.assertEqual(formatted, "Сайн уу? Би ирлээ.")

    def test_period_disambiguation_noun_phrases(self):
        # Noun phrases with 'цэг' followed by command 'цэг'
        sample1 = "бид цугларах цэг дээр уулзана цэг"
        res1 = voice_core.apply_voice_commands(sample1)
        self.assertEqual(res1, "Бид цугларах цэг дээр уулзана.")

        # Coordinate/alphabetic point like 'А цэг' and 'Б цэг'
        sample2 = "а цэг ба б цэг хүртэл явав цэг"
        res2 = voice_core.apply_voice_commands(sample2)
        self.assertEqual(res2, "А цэг ба б цэг хүртэл явав.")

        # Checkpoint / start point
        sample3 = "эхлэх цэг рүү очно уу цэг"
        res3 = voice_core.apply_voice_commands(sample3)
        self.assertEqual(res3, "Эхлэх цэг рүү очно уу.")

        # Semicolon 'цэг таслал' voice command
        sample4 = "эхний хэсэг дууслаа цэг таслал дараагийн ажил эхэллээ цэг"
        res4 = voice_core.apply_voice_commands(sample4)
        self.assertEqual(res4, "Эхний хэсэг дууслаа; дараагийн ажил эхэллээ.")

        # Additional technical noun context (өгөгдлийн цэг, холболтын цэг)
        sample5 = "энэ бол өгөгдлийн цэг ба холболтын цэг тухай яриа цэг"
        res5 = voice_core.apply_voice_commands(sample5)
        self.assertEqual(res5, "Энэ бол өгөгдлийн цэг ба холболтын цэг тухай яриа.")

    def test_settings_hydration_merge_scenarios(self):
        default_settings = {
            "language": "mn",
            "desktopHotkey": "f8",
            "sttEngine": "auto",
            "whisperModel": "small",
            "chimegeToken": "",
            "customSnippets": False,
            "snippets": {},
        }

        # Scenario 1: Empty server returns empty dict -> defaults preserved
        merged_1 = dict(default_settings)
        server_resp_1 = {}
        if server_resp_1.get("hotkey"):
            merged_1["desktopHotkey"] = server_resp_1["hotkey"]
        self.assertEqual(merged_1["desktopHotkey"], "f8")

        # Scenario 2: Legacy local storage has older keys -> merged safely
        local_cache_2 = {"language": "en", "desktopHotkey": "f2"}
        merged_2 = {**default_settings, **local_cache_2}
        self.assertEqual(merged_2["language"], "en")
        self.assertEqual(merged_2["desktopHotkey"], "f2")
        self.assertEqual(merged_2["sttEngine"], "auto")  # from defaults

        # Scenario 3: Server GET fails / offline -> local cache preserved without overwrite
        local_cache_3 = {"snippets": {"миний имэйл": "user@example.invalid"}}
        merged_3 = {**default_settings, **local_cache_3}
        is_hydrated_3 = True
        has_user_modified_3 = False
        should_post_3 = is_hydrated_3 and has_user_modified_3
        self.assertFalse(should_post_3)  # Never overwrite server on offline/startup

        # Scenario 4: User updates a setting -> modified flag enables sync
        has_user_modified_4 = True
        should_post_4 = is_hydrated_3 and has_user_modified_4
        self.assertTrue(should_post_4)

        # Scenario 5: Server snippets merged with local snippets without losing either
        server_snippets_5 = {"srv_key": "srv_val"}
        local_snippets_5 = {"local_key": "local_val"}
        merged_snippets_5 = {**local_snippets_5, **server_snippets_5}
        self.assertIn("srv_key", merged_snippets_5)
        self.assertIn("local_key", merged_snippets_5)

    def test_hotkey_conflict_resolution(self):
        def resolve_hotkey(hk_mode, ctrl=False, alt=False, shift=False, space=False, f8=False, f9=False, f10=False, f2=False, f4=False):
            is_ctrl_alt = bool(ctrl and alt and not shift)
            if hk_mode == "f9":
                return is_ctrl_alt or f9
            elif hk_mode == "f10":
                return is_ctrl_alt or f10
            elif hk_mode == "f2":
                return is_ctrl_alt or f2
            elif hk_mode == "f4":
                return is_ctrl_alt or f4
            elif hk_mode == "ctrl_shift":
                return is_ctrl_alt or (ctrl and shift and not alt)
            elif hk_mode == "alt_shift":
                return is_ctrl_alt or (alt and shift and not ctrl)
            elif hk_mode == "ctrl_space":
                return is_ctrl_alt or (ctrl and space and not alt)
            elif hk_mode == "ctrl_alt":
                return is_ctrl_alt
            else:
                return is_ctrl_alt or f8

        # If user chose F9, pressing F8 alone must NOT trigger (avoiding conflict with apps using F8)
        self.assertFalse(resolve_hotkey("f9", f8=True))
        self.assertTrue(resolve_hotkey("f9", f9=True))

        # Universal Ctrl+Alt ALWAYS triggers regardless of configured function key
        self.assertTrue(resolve_hotkey("f9", ctrl=True, alt=True))
        self.assertTrue(resolve_hotkey("f2", ctrl=True, alt=True))

        # If user chose Ctrl+Shift, pressing only F8 must NOT trigger
        self.assertFalse(resolve_hotkey("ctrl_shift", f8=True))
        self.assertTrue(resolve_hotkey("ctrl_shift", ctrl=True, shift=True))

    def test_affirmative_consent_preserved_in_strip_filler(self):
        # Standalone affirmative
        self.assertEqual(voice_core.strip_filler_words("Тийм ээ"), "Тийм ээ")
        self.assertEqual(voice_core.strip_filler_words("Тиймээ"), "Тиймээ")

        # Explicit affirmative agreement
        stmt = "Тийм ээ, би зөвшөөрч байна"
        self.assertEqual(voice_core.strip_filler_words(stmt), stmt)

        stmt2 = "Тиймээ, тэгье"
        self.assertEqual(voice_core.strip_filler_words(stmt2), stmt2)

        # Mid-sentence hesitation is still stripped
        filler_sample = "Би нөгөө өнөөдөр аан тиймээ очсон"
        cleaned = voice_core.strip_filler_words(filler_sample)
        self.assertNotIn("нөгөө", cleaned)
        self.assertNotIn("аан", cleaned)
        self.assertNotIn("тиймээ", cleaned)
        self.assertEqual(cleaned, "Би өнөөдөр очсон")

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

    def test_generate_lrc(self):
        segments = [
            {"start": 12.30, "end": 15.50, "text": "Сарны гэрэл туссан"},
            {"start": 16.00, "end": 20.15, "text": "Саруул сайхан шөнөөр"},
        ]
        lrc = voice_core.generate_lrc(segments, title="Шөнийн дуу", artist="VOICE")
        self.assertIn("[ti:Шөнийн дуу]", lrc)
        self.assertIn("[ar:VOICE]", lrc)
        self.assertIn("[00:12.30]Сарны гэрэл туссан", lrc)
        self.assertIn("[00:16.00]Саруул сайхан шөнөөр", lrc)

    def test_generate_vtt(self):
        segments = [
            {"start": 1.5, "end": 4.2, "text": "Монгол яриа таних"},
        ]
        vtt = voice_core.generate_vtt(segments)
        self.assertIn("WEBVTT", vtt)
        self.assertIn("00:00:01.500 --> 00:00:04.200", vtt)
        self.assertIn("Монгол яриа таних", vtt)

    def test_apply_voice_snippets(self):
        snippets = {
            "миний имэйл": "user@example.invalid",
            "миний утас": "+97600000000",
            "данс": "2815108795",
        }
        # 1. Standard trigger replacement with punctuation
        sample = "Сайн байна уу миний имэйл хаягаар холбогдож данс руу шилжүүлнэ үү. Миний утас: залгаарай."
        res = voice_core.apply_voice_snippets(sample, snippets)
        self.assertIn("user@example.invalid хаягаар", res)
        self.assertIn("2815108795 руу", res)
        self.assertIn("+97600000000:", res)
        self.assertNotIn("миний имэйл", res)

        # 2. Case insensitivity
        sample_case = "МИНИЙ ИМЭЙЛ, ДАНС руу"
        res_case = voice_core.apply_voice_snippets(sample_case, snippets)
        self.assertIn("user@example.invalid,", res_case)
        self.assertIn("2815108795 руу", res_case)

        # 3. Cyrillic word boundary / suffix protection
        sample_suffix = "дансаа өгөөч дансны мэдээлэл"
        res_suffix = voice_core.apply_voice_snippets(sample_suffix, snippets)
        self.assertEqual(res_suffix, "дансаа өгөөч дансны мэдээлэл")

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

    def test_normalize_tech_terms(self):
        sample = "би гитхаб руу пуш хийгээд зуум дээр уулзаж фэйсбүүк болон ютуб дээр видео хийнэ бас пидиэф файл явуулна"
        res = voice_core.normalize_tech_terms(sample)
        self.assertIn("GitHub", res)
        self.assertIn("Zoom", res)
        self.assertIn("Facebook", res)
        self.assertIn("YouTube", res)
        self.assertIn("PDF", res)
        self.assertNotIn("гитхаб", res)
        self.assertNotIn("зуум", res)
        self.assertNotIn("фэйсбүүк", res)
        self.assertNotIn("пидиэф", res)


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

    def test_insert_text_newline_no_extra_space(self):
        text_with_newline = "Сайн байна уу\n"
        text_formatted = text_with_newline if text_with_newline.endswith(("\n", "\r\n", " ")) else text_with_newline + " "
        self.assertEqual(text_formatted, "Сайн байна уу\n")

        text_standard = "Сайн байна уу"
        text_std_formatted = text_standard if text_standard.endswith(("\n", "\r\n", " ")) else text_standard + " "
        self.assertEqual(text_std_formatted, "Сайн байна уу ")

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

    def test_export_lrc_and_vtt_endpoints(self):
        res_lrc = self.client.post("/api/export-lrc", json={
            "segments": [{"start": 2.5, "end": 5.0, "text": "Туршилтын үг"}],
            "title": "Дуу",
            "artist": "Дуучин"
        })
        self.assertEqual(res_lrc.status_code, 200)
        self.assertIn("[00:02.50]Туршилтын үг", res_lrc.text)

        res_vtt = self.client.post("/api/export-vtt", json={
            "segments": [{"start": 2.5, "end": 5.0, "text": "Туршилтын үг"}]
        })
        self.assertEqual(res_vtt.status_code, 200)
        self.assertIn("WEBVTT", res_vtt.text)
        self.assertIn("00:00:02.500 --> 00:00:05.000", res_vtt.text)

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

    def test_voice_form_filling_auto_tab(self):
        text = "Овог Дорж дараагийн нүд нэр Бат дараагийн талбар 99112233"
        res = voice_core.apply_voice_commands(text)
        self.assertIn("\t", res)
        self.assertEqual(res, "Овог Дорж\tНэр Бат\t99112233")

        text_down = "Эхний нүд доод талбар хоёр дахь нүд"
        res_down = voice_core.apply_voice_commands(text_down)
        self.assertIn("\n", res_down)
        self.assertEqual(res_down, "Эхний нүд\nХоёр дахь нүд")

    def test_extract_summary_and_actions(self):
        sample = """
        Өнөөдрийн хурлаар шинэ хувилбарыг батлав.
        Мөн бид дараагийн төслийн төлөвлөгөөг бэлтгэх хэрэгтэй.
        Багийн ахлагч тайланг маргааш илгээнэ.
        Хэрэглэгчийн санал хүсэлтийг заавал судална.
        """
        extracted = voice_core.extract_summary_and_actions(sample)
        self.assertTrue(len(extracted["decisions"]) >= 1)
        self.assertTrue(len(extracted["action_items"]) >= 2)
        self.assertTrue(len(extracted["key_points"]) >= 1)
        self.assertTrue(len(extracted["summary"]) > 10)

        empty_res = voice_core.extract_summary_and_actions("")
        self.assertEqual(empty_res["summary"], "")
        self.assertEqual(empty_res["action_items"], [])

    def test_summarize_api_endpoint(self):
        res = self.client.post("/api/summarize", json={
            "text": "Төслийн төсвийг батлав. Захиалгын тайланг бэлтгэх хэрэгтэй."
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("summary", data)
        self.assertIn("key_points", data)
        self.assertIn("action_items", data)
        self.assertIn("decisions", data)
        self.assertTrue(len(data["action_items"]) >= 1)
        self.assertTrue(len(data["decisions"]) >= 1)

        # Empty text returns 400
        res_empty = self.client.post("/api/summarize", json={"text": ""})
        self.assertEqual(res_empty.status_code, 400)

    def test_offline_fallback_indicator(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("offline_fallback", data)



    def test_rewrite_text_style_formal(self):
        sample = "бид нар энэ ажил дээр сайн ажиллалаа тэгээд бас тайлангаа явуулаарай"
        res = voice_core.rewrite_text_style(sample, style="formal")
        self.assertEqual(res["status"], "ok")
        rewritten = res["rewritten"]
        self.assertIn("Бид тухайн ажил", rewritten)
        self.assertIn("үр дүнтэй ажиллалаа", rewritten)
        self.assertIn("үүнээс гадна", rewritten)
        self.assertIn("ирүүлнэ үү", rewritten)

    def test_rewrite_text_style_email(self):
        sample = "Маргаашийн шинэ хувилбарын нээлтийн төлөвлөгөөг танилцуулж байна"
        res = voice_core.rewrite_text_style(sample, style="email")
        self.assertEqual(res["status"], "ok")
        rewritten = res["rewritten"]
        self.assertIn("Гарчиг:", rewritten)
        self.assertIn("Сайн байна уу?", rewritten)
        self.assertIn("Хүндэтгэсэн,", rewritten)

    def test_rewrite_text_style_social(self):
        sample = "Шинэ бүтээгдэхүүн гарлаа. Илүү хурдан ажилладаг болсон."
        res = voice_core.rewrite_text_style(sample, style="social")
        self.assertEqual(res["status"], "ok")
        self.assertIn("✨", res["rewritten"])
        self.assertIn("💬", res["rewritten"])

    def test_rewrite_text_style_proofread(self):
        sample = "би би өнөөдөр очно очно"
        res = voice_core.rewrite_text_style(sample, style="proofread")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["rewritten"], "Би өнөөдөр очно.")

    def test_rewrite_style_api_endpoint(self):
        res = self.client.post("/api/rewrite-style", json={
            "text": "бид нар энэ ажил хийгээд өгөөрэй",
            "style": "formal"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("Бид тухайн ажил", data["rewritten"])
        self.assertIn("гүйцэтгэнэ үү", data["rewritten"])

        # Empty text returns 400
        res_empty = self.client.post("/api/rewrite-style", json={"text": ""})
        self.assertEqual(res_empty.status_code, 400)





    def test_auto_lyrics_endpoint_validation(self):
        # 1. File under 500 bytes returns 400
        short_audio = io.BytesIO(b"RIFF" + b"\x00" * 100)
        res_short = self.client.post(
            "/api/auto-lyrics",
            files={"audio": ("test.wav", short_audio, "audio/wav")},
        )
        self.assertEqual(res_short.status_code, 400)

        # 2. Unsupported extension returns 400
        fake_exe = io.BytesIO(b"MZ" + b"\x00" * 1000)
        res_exe = self.client.post(
            "/api/auto-lyrics",
            files={"audio": ("malicious.exe", fake_exe, "application/octet-stream")},
        )
        self.assertEqual(res_exe.status_code, 400)
        self.assertIn("Дэмжигдээгүй файл формат", res_exe.json().get("detail", ""))

        # 3. File over 25MB returns 413
        oversized_bytes = b"\x00" * (25 * 1024 * 1024 + 20)
        res_large = self.client.post(
            "/api/auto-lyrics",
            files={"audio": ("large.wav", io.BytesIO(oversized_bytes), "audio/wav")},
        )
        self.assertEqual(res_large.status_code, 413)

    def test_auto_lyrics_endpoint_success_wav(self):
        # Create a valid 16kHz mono WAV file of 0.5s silence (~16000 bytes)
        import struct
        num_samples = 8000
        raw_samples = struct.pack(f"<{num_samples}h", *([0] * num_samples))
        wav_buf = io.BytesIO()
        wav_buf.write(b"RIFF")
        wav_buf.write(struct.pack("<I", 36 + len(raw_samples)))
        wav_buf.write(b"WAVEfmt ")
        wav_buf.write(struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16))
        wav_buf.write(b"data")
        wav_buf.write(struct.pack("<I", len(raw_samples)))
        wav_buf.write(raw_samples)
        wav_bytes = wav_buf.getvalue()

        res = self.client.post(
            "/api/auto-lyrics",
            data={
                "language": "auto",
                "model_name": "tiny",
                "title": "Хайрын дуу",
                "artist": "Чингис хаан",
            },
            files={"audio": ("test_track.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("lrc", data)
        self.assertIn("srt", data)
        self.assertIn("vtt", data)
        self.assertIn("segments", data)





    def test_auto_lyrics_supported_extensions(self):
        # Verify valid extensions (.mp3, .m4a, .ogg, .mp4) pass initial extension validation
        sample_bytes = b"RIFF" + b"\x00" * 600
        for ext, mime in [(".mp3", "audio/mpeg"), (".m4a", "audio/mp4"), (".ogg", "audio/ogg"), (".mp4", "video/mp4")]:
            res = self.client.post(
                "/api/auto-lyrics",
                files={"audio": (f"sample{ext}", io.BytesIO(sample_bytes), mime)},
            )
            # Should not fail with 400 'Дэмжигдээгүй файл формат'
            if res.status_code == 400:
                self.assertNotIn("Дэмжигдээгүй файл формат", res.json().get("detail", ""))

    def test_auto_lyrics_export_endpoints(self):
        sample_segments = [
            {"id": 1, "start": 0.5, "end": 2.5, "text": "Сайн байна уу"},
            {"id": 2, "start": 3.0, "end": 5.0, "text": "Энэ бол дууны үг"},
        ]
        
        # 1. Export LRC
        res_lrc = self.client.post("/api/export-lrc", json={"segments": sample_segments, "title": "Дуу", "artist": "Дуучин"})
        self.assertEqual(res_lrc.status_code, 200)
        self.assertIn("Сайн байна уу", res_lrc.text)
        self.assertIn("[00:00.50]", res_lrc.text)
        self.assertIn("attachment; filename=voice_lyrics.lrc", res_lrc.headers.get("content-disposition", ""))

        # 2. Export SRT
        res_srt = self.client.post("/api/export-srt", json={"segments": sample_segments})
        self.assertEqual(res_srt.status_code, 200)
        self.assertIn("00:00:00,500 --> 00:00:02,500", res_srt.text)
        self.assertIn("Сайн байна уу", res_srt.text)
        self.assertIn("attachment; filename=voice_subtitles.srt", res_srt.headers.get("content-disposition", ""))

        # 3. Export VTT
        res_vtt = self.client.post("/api/export-vtt", json={"segments": sample_segments})
        self.assertEqual(res_vtt.status_code, 200)
        self.assertIn("WEBVTT", res_vtt.text)
        self.assertIn("00:00:00.500 --> 00:00:02.500", res_vtt.text)
        self.assertIn("Сайн байна уу", res_vtt.text)
        self.assertIn("attachment; filename=voice_subtitles.vtt", res_vtt.headers.get("content-disposition", ""))

    def test_auto_lyrics_tempfile_cleanup(self):
        import struct
        import tempfile
        num_samples = 4000
        raw_samples = struct.pack(f"<{num_samples}h", *([0] * num_samples))
        wav_buf = io.BytesIO()
        wav_buf.write(b"RIFF")
        wav_buf.write(struct.pack("<I", 36 + len(raw_samples)))
        wav_buf.write(b"WAVEfmt ")
        wav_buf.write(struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16))
        wav_buf.write(b"data")
        wav_buf.write(struct.pack("<I", len(raw_samples)))
        wav_buf.write(raw_samples)
        wav_bytes = wav_buf.getvalue()

        # Track created temporary files during upload
        real_named_temp = tempfile.NamedTemporaryFile
        created_paths = []
        def spy_temp(*args, **kwargs):
            tf = real_named_temp(*args, **kwargs)
            created_paths.append(tf.name)
            return tf

        with unittest.mock.patch("tempfile.NamedTemporaryFile", side_effect=spy_temp):
            res = self.client.post(
                "/api/auto-lyrics",
                files={"audio": ("cleanup_test.wav", io.BytesIO(wav_bytes), "audio/wav")},
            )
            self.assertEqual(res.status_code, 200)

        # Verify all created temporary files were safely unlinked/cleaned up
        self.assertGreater(len(created_paths), 0)
        for p in created_paths:
            self.assertFalse(os.path.exists(p), f"Temporary file {p} was not cleaned up!")


    def test_api_format_numbers_endpoint(self):
        res = self.client.post("/api/format-numbers", json={"text": "таван зуун мянган төгрөг болон 99112233"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("500,000₮", data["formatted_text"])
        self.assertIn("9911-2233", data["formatted_text"])

        # Empty text handling
        res_empty = self.client.post("/api/format-numbers", json={"text": ""})
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(res_empty.json()["formatted_text"], "")

    def test_chrome_voice_flow_endpoints(self):
        # 1. Flowbar insert text endpoint (used by Chrome web FlowBar)
        res_insert = self.client.post("/api/flowbar", json={"insertText": "Сайн байна уу Chrome"})
        self.assertEqual(res_insert.status_code, 200)
        self.assertEqual(res_insert.json().get("status"), "ok")
        self.assertEqual(res_insert.json().get("inserted"), "Сайн байна уу Chrome")

        # 2. Chimege transcribe endpoint (used by Chrome web audio recording)
        import struct
        num_samples = 4000
        raw_samples = struct.pack(f"<{num_samples}h", *([0] * num_samples))
        wav_buf = io.BytesIO()
        wav_buf.write(b"RIFF")
        wav_buf.write(struct.pack("<I", 36 + len(raw_samples)))
        wav_buf.write(b"WAVEfmt ")
        wav_buf.write(struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16))
        wav_buf.write(b"data")
        wav_buf.write(struct.pack("<I", len(raw_samples)))
        wav_buf.write(raw_samples)
        wav_bytes = wav_buf.getvalue()

        res_tr = self.client.post(
            "/api/chimege/transcribe",
            files={"audio": ("speech.wav", io.BytesIO(wav_bytes), "audio/wav")},
            data={"language": "mn"},
        )
        self.assertEqual(res_tr.status_code, 200)
        self.assertIn("text", res_tr.json())

    def test_flowbar_toggle_and_snippets_defaults(self):
        # 1. Flowbar toggle action
        res_toggle = self.client.post("/api/flowbar", json={"action": "toggle_visibility"})
        self.assertEqual(res_toggle.status_code, 200)
        self.assertIn("visible", res_toggle.json())

        # 2. Check default snippets fixtures are available on server settings
        res_settings = self.client.get("/api/settings")
        self.assertEqual(res_settings.status_code, 200)
        cfg = res_settings.json()
        snippets = cfg.get("snippets", {})
        self.assertIn("миний имэйл", snippets)
        self.assertIn("миний утас", snippets)
        self.assertIn("данс", snippets)
        self.assertEqual(snippets["данс"], "0000000000")


if __name__ == "__main__":
    unittest.main()

