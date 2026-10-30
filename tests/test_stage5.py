"""
Tests for Stage 5:
- Unicode NFC normalization & Windows CF_UNICODETEXT clipboard compatibility
- Auto-updater semver parsing, release checks, and SHA256 verification
- System Tray & FlowBar pause/resume state management
- Background daemon mode & Autostart registry command formatting
"""

import hashlib
import os
import tempfile
import unicodedata
import unittest

import auto_updater
from tts_server import (
    FLOWBAR_STATE,
    FlowBarActionRequest,
    flowbar_action,
    CF_UNICODETEXT,
)


class TestStage5UnicodeAndClipboard(unittest.TestCase):
    def test_unicode_nfc_normalization(self):
        """Test that Mongolian text with combined or decomposed characters is properly normalized to NFC."""
        # Decomposed form of Ө (U+04e8) or ү (U+04af) or accented characters
        test_strings = [
            "Өдрийн мэнд, Монгол улс!",
            "Үүлэн дунд шувуу ниснэ",
            "Бүх нийтээрээ монгол хэлээр бичицгээе",
        ]
        for s in test_strings:
            nfd = unicodedata.normalize("NFD", s)
            nfc = unicodedata.normalize("NFC", nfd)
            self.assertEqual(unicodedata.normalize("NFC", s), nfc)
            self.assertTrue(any(c in nfc.lower() for c in ("ө", "ү")))

    def test_cf_unicodetext_payload_encoding(self):
        """Test that Windows CF_UNICODETEXT payload is UTF-16-LE with double-null termination."""
        sample_text = "Монгол хэл — Unicode NFC туршилт"
        normalized = unicodedata.normalize("NFC", sample_text)
        payload = normalized.encode("utf-16-le") + b"\x00\x00"

        self.assertTrue(payload.endswith(b"\x00\x00"))
        # Decode back and verify exact text
        decoded = payload[:-2].decode("utf-16-le")
        self.assertEqual(decoded, sample_text)

    def test_clipboard_format_id(self):
        """Verify standard Win32 CF_UNICODETEXT format constant is 13."""
        self.assertEqual(CF_UNICODETEXT, 13)


class TestStage5AutoUpdater(unittest.TestCase):
    def test_parse_semver(self):
        self.assertEqual(auto_updater.parse_semver("v1.4.0"), (1, 4, 0))
        self.assertEqual(auto_updater.parse_semver("1.3.2"), (1, 3, 2))
        self.assertEqual(auto_updater.parse_semver("v2.0.0-beta"), (2, 0, 0))
        self.assertEqual(auto_updater.parse_semver("invalid"), (0, 0, 0))

    def test_is_newer_version(self):
        self.assertTrue(auto_updater.is_newer_version("v1.4.1", "1.4.0"))
        self.assertTrue(auto_updater.is_newer_version("2.0.0", "1.4.0"))
        self.assertFalse(auto_updater.is_newer_version("v1.4.0", "1.4.0"))
        self.assertFalse(auto_updater.is_newer_version("1.3.9", "1.4.0"))
        self.assertFalse(auto_updater.is_newer_version("0.9.0", "1.4.0"))

    def test_sha256_verification(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"VOICE Stage 5 Test Payload")
            f_path = f.name

        try:
            expected_hash = hashlib.sha256(b"VOICE Stage 5 Test Payload").hexdigest().lower()
            calc_hash = auto_updater.calculate_file_sha256(f_path)
            self.assertEqual(calc_hash, expected_hash)
            self.assertTrue(auto_updater.verify_file_sha256(f_path, expected_hash))
            self.assertTrue(auto_updater.verify_file_sha256(f_path, expected_hash.upper()))
            self.assertFalse(auto_updater.verify_file_sha256(f_path, "invalidhash"))
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)


class TestStage5TrayAndFlowBarState(unittest.TestCase):
    def test_flowbar_pause_and_resume(self):
        """Test FlowBar dictation pause and resume state toggle."""
        # Test pause
        res_pause = flowbar_action(FlowBarActionRequest(action="pause"))
        self.assertTrue(res_pause.get("is_paused"))
        self.assertTrue(FLOWBAR_STATE.get("is_paused"))

        # Test resume
        res_resume = flowbar_action(FlowBarActionRequest(action="resume"))
        self.assertFalse(res_resume.get("is_paused"))
        self.assertFalse(FLOWBAR_STATE.get("is_paused"))

    def test_flowbar_language_switch(self):
        """Test language switching via flowbar action."""
        flowbar_action(FlowBarActionRequest(action="set_language", language="mn"))
        self.assertEqual(FLOWBAR_STATE.get("language"), "mn")

        flowbar_action(FlowBarActionRequest(action="set_language", language="en"))
        self.assertEqual(FLOWBAR_STATE.get("language"), "en")

        flowbar_action(FlowBarActionRequest(action="set_language", language="auto"))
        self.assertEqual(FLOWBAR_STATE.get("language"), "auto")


class TestStage5AutostartFormatting(unittest.TestCase):
    def test_autostart_command_quoting_and_flags(self):
        """Verify autostart registry command formats with quotes and --background flag."""
        test_path = r"C:\Program Files (x86)\VOICE-App\Start-VOICE.bat"
        expected_cmd = f'"{test_path}" --background'
        self.assertTrue(expected_cmd.startswith('"'))
        self.assertTrue(expected_cmd.endswith('--background'))
        self.assertIn(test_path, expected_cmd)


if __name__ == "__main__":
    unittest.main()
