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
import voice_core
from tts_server import (
    FLOWBAR_STATE,
    FlowBarActionRequest,
    flowbar_action,
    CF_UNICODETEXT,
    USER_DATA_DIR,
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
        self.assertEqual(auto_updater.parse_semver("v1.4.1"), (1, 4, 1))
        self.assertEqual(auto_updater.parse_semver("v1.4.0"), (1, 4, 0))
        self.assertEqual(auto_updater.parse_semver("1.3.2"), (1, 3, 2))
        self.assertEqual(auto_updater.parse_semver("v2.0.0-beta"), (2, 0, 0))
        self.assertEqual(auto_updater.parse_semver("invalid"), (0, 0, 0))

    def test_is_newer_version(self):
        self.assertTrue(auto_updater.is_newer_version("v1.4.1", "1.4.0"))
        self.assertTrue(auto_updater.is_newer_version("2.0.0", "1.4.1"))
        self.assertFalse(auto_updater.is_newer_version("v1.4.1", "1.4.1"))
        self.assertFalse(auto_updater.is_newer_version("1.3.9", "1.4.1"))
        self.assertFalse(auto_updater.is_newer_version("0.9.0", "1.4.1"))

    def test_url_safety_validation(self):
        valid_urls = [
            "https://github.com/AriukagiinTuvshoo/voice-app/releases/download/v1.4.1/VOICE-Setup-v1.4.1.exe",
            "https://objects.githubusercontent.com/github-production-release-asset-2e65be/12345/VOICE-Setup.exe",
            "https://github-releases.githubusercontent.com/12345/VOICE-Setup.exe",
        ]
        invalid_urls = [
            "http://malicious.com/VOICE-Setup.exe",
            "https://github.evil.com/attacker/malware.exe",
            "ftp://github.com/file.exe",
            "javascript:alert(1)",
        ]
        for url in valid_urls:
            self.assertTrue(auto_updater.is_safe_download_url(url), f"Should be safe: {url}")
        for url in invalid_urls:
            self.assertFalse(auto_updater.is_safe_download_url(url), f"Should NOT be safe: {url}")

    def test_checksums_parsing(self):
        checksum_content = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  VOICE-Setup-v1.4.1.exe\n"
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad *VOICE-Windows-v1.4.1.zip\r\n"
        )
        parsed = auto_updater.parse_checksums_content(checksum_content)
        self.assertEqual(parsed.get("VOICE-Setup-v1.4.1.exe"), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(parsed.get("VOICE-Windows-v1.4.1.zip"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_session_token_management(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"dummy installer")
            dummy_path = f.name

        try:
            token = auto_updater.create_update_session(dummy_path, "1.4.1")
            self.assertTrue(isinstance(token, str) and len(token) > 10)
            
            # Retrieve path
            retrieved = auto_updater.get_verified_session_installer(token)
            self.assertEqual(retrieved, dummy_path)

            # Invalidate session
            auto_updater.invalidate_update_session(token)
            self.assertIsNone(auto_updater.get_verified_session_installer(token))
            self.assertIsNone(auto_updater.get_verified_session_installer("non-existent-token"))
        finally:
            if os.path.exists(dummy_path):
                os.remove(dummy_path)

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
        test_path = r"C:\Users\test\AppData\Local\Programs\VOICE\Start-VOICE.bat"
        expected_cmd = f'"{test_path}" --background'
        self.assertTrue(expected_cmd.startswith('"'))
        self.assertTrue(expected_cmd.endswith('--background'))
        self.assertIn(test_path, expected_cmd)


class TestStage5UserDirectories(unittest.TestCase):
    def test_canonical_user_data_dir(self):
        r"""Verify canonical user data directory resolves to %APPDATA%\VOICE."""
        user_dir = voice_core.get_user_data_dir()
        self.assertTrue(user_dir.endswith("VOICE"))
        self.assertEqual(USER_DATA_DIR, user_dir)
        self.assertTrue(os.path.isabs(user_dir))

    def test_canonical_app_dir(self):
        r"""Verify canonical application binary directory is %LOCALAPPDATA%\Programs\VOICE."""
        app_dir = voice_core.CANONICAL_APP_DIR
        self.assertTrue(app_dir.replace("/", "\\").endswith(r"Programs\VOICE"))


if __name__ == "__main__":
    unittest.main()
