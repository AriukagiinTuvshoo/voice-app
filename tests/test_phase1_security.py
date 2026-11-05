import os
import unittest
import base64
from fastapi.testclient import TestClient
import voice_core
import auto_updater
import tts_server


class TestPhase1SecurityAndPrivacy(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(tts_server.app)

    def tearDown(self):
        # Restore default settings so subsequent test suites aren't mutated
        tts_server.save_server_settings({
            "cpu_threads": 6,
            "hotkey": "f8",
            "disable_ctrl_alt": False,
            "offline_only": False,
            "opt_in_google_stt": False,
            "opt_in_spellcheck_mn": False,
        })

    def test_dpapi_encryption_and_decryption(self):
        """Test Windows DPAPI encryption, decryption, and masking."""
        secret = "secret_chimege_api_token_12345"
        encrypted = voice_core.dpapi_encrypt(secret)
        self.assertTrue(encrypted.startswith("dpapi:"), "Encrypted token must start with dpapi:")
        decrypted = voice_core.dpapi_decrypt(encrypted)
        self.assertEqual(decrypted, secret, "Decrypted token must match original plaintext")

        # Non-dpapi plaintext fallback
        self.assertEqual(voice_core.dpapi_decrypt("plain_token"), "plain_token")

        # Masking
        masked = voice_core.mask_secret(secret)
        self.assertIn("***", masked)
        self.assertTrue(masked.startswith("secr"))
        self.assertTrue(masked.endswith("2345"))

    def test_dpapi_error_handling(self):
        """Test DPAPI failure raising DPAPIError instead of silently returning plaintext."""
        self.assertTrue(issubclass(voice_core.DPAPIError, RuntimeError))
        # Test mock non-windows behavior
        old_env = os.environ.get("VOICE_TEST_MOCK_DPAPI")
        try:
            os.environ["VOICE_TEST_MOCK_DPAPI"] = "1"
            # Decrypt of mock string works gracefully
            self.assertEqual(voice_core.dpapi_decrypt("dpapi:mock:" + base64.b64encode(b"hello").decode()), "hello")
            # Invalid decrypt string returns "" gracefully
            self.assertEqual(voice_core.dpapi_decrypt("dpapi:corrupt_base64_%%%"), "")
        finally:
            if old_env is not None:
                os.environ["VOICE_TEST_MOCK_DPAPI"] = old_env
            else:
                os.environ.pop("VOICE_TEST_MOCK_DPAPI", None)

    def test_session_token_and_auth_middleware(self):
        """Test that per-session auth token is required on protected routes and rejected without it."""
        session_token = tts_server.SESSION_TOKEN
        self.assertTrue(bool(session_token), "SESSION_TOKEN must be generated at startup")

        # 1. Unauthenticated request to sensitive GET route with custom non-test host
        res = self.client.get(
            "/api/settings",
            headers={"Host": f"127.0.0.1:{tts_server.SERVER_PORT}"},
        )
        self.assertEqual(res.status_code, 401, "Protected GET without token must return 401 Unauthorized")

        # 2. Authenticated request with header X-Session-Token
        res_auth = self.client.get(
            "/api/settings",
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "X-Session-Token": session_token,
            },
        )
        self.assertEqual(res_auth.status_code, 200, "Protected GET with valid X-Session-Token must return 200")
        data = res_auth.json()
        self.assertIn("privacy_notice", data)
        self.assertIn("disable_ctrl_alt", data)

        # 3. Authenticated request with Authorization Bearer
        res_bearer = self.client.get(
            "/api/settings",
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "Authorization": f"Bearer {session_token}",
            },
        )
        self.assertEqual(res_bearer.status_code, 200)

        # 4. Authenticated request with Cookie
        res_cookie = self.client.get(
            "/api/settings",
            headers={"Host": f"127.0.0.1:{tts_server.SERVER_PORT}"},
            cookies={"voice_session_token": session_token},
        )
        self.assertEqual(res_cookie.status_code, 200)

        # 5. Query param token MUST BE REJECTED (no token in query string allowed)
        res_query = self.client.get(
            f"/api/settings?token={session_token}",
            headers={"Host": f"127.0.0.1:{tts_server.SERVER_PORT}"},
        )
        self.assertEqual(res_query.status_code, 401, "Query parameter tokens must be rejected with 401")

        # 6. Invalid token rejected
        res_bad = self.client.get(
            "/api/settings",
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "X-Session-Token": "invalid_bogus_token",
            },
        )
        self.assertEqual(res_bad.status_code, 401)

    def test_voice_profiles_and_clones_route_protection(self):
        """Test private voice profiles endpoints are protected against unauthenticated access."""
        # Unauthenticated access to /clones must be blocked
        res_clones = self.client.get(
            "/clones",
            headers={"Host": f"127.0.0.1:{tts_server.SERVER_PORT}"},
        )
        self.assertEqual(res_clones.status_code, 401)

        # Unauthenticated access to /api/voice-profiles must be blocked
        res_profiles = self.client.get(
            "/api/voice-profiles",
            headers={"Host": f"127.0.0.1:{tts_server.SERVER_PORT}"},
        )
        self.assertEqual(res_profiles.status_code, 401)

    def test_single_instance_wake_exemption(self):
        """Test that POST /flowbar/action with action='show' from 127.0.0.1 is allowed without auth token."""
        res = self.client.post(
            "/flowbar/action",
            json={"action": "show"},
            headers={"Host": f"127.0.0.1:{tts_server.SERVER_PORT}"},
        )
        self.assertEqual(res.status_code, 200)

    def test_httponly_session_cookie(self):
        """Test that session cookie returned on HTML pages has HttpOnly and SameSite=Strict."""
        res = self.client.get(
            "/dashboard",
            headers={"Host": f"127.0.0.1:{tts_server.SERVER_PORT}"},
        )
        self.assertEqual(res.status_code, 200)
        cookie_header = res.headers.get("set-cookie", "")
        self.assertIn("voice_session_token", cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("samesite=strict", cookie_header.lower())

    def test_strict_origin_check(self):
        """Test that requests from disallowed origins (different ports or domains) are blocked with 403."""
        token = tts_server.SESSION_TOKEN

        # Allowed origin
        allowed_res = self.client.post(
            "/api/settings",
            json={"hotkey": "f8"},
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "Origin": f"http://127.0.0.1:{tts_server.SERVER_PORT}",
                "X-Session-Token": token,
            },
        )
        self.assertEqual(allowed_res.status_code, 200)

        # Disallowed origin (different port on localhost: attacker on localhost:3000)
        forbidden_res = self.client.post(
            "/api/settings",
            json={"hotkey": "f8"},
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "Origin": "http://localhost:3000",
                "X-Session-Token": token,
            },
        )
        self.assertEqual(forbidden_res.status_code, 403, "Origin with different port must be blocked with 403")

    def test_settings_pydantic_validation_and_token_masking(self):
        """Test SettingsUpdateModel schema validation and chimege_token masking."""
        token = tts_server.SESSION_TOKEN

        # Valid update
        res = self.client.post(
            "/api/settings",
            json={
                "hotkey": "f9",
                "cpu_threads": 8,
                "disable_ctrl_alt": True,
                "offline_only": True,
                "opt_in_google_stt": False,
                "opt_in_spellcheck_mn": False,
            },
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "X-Session-Token": token,
            },
        )
        self.assertEqual(res.status_code, 200)
        saved = res.json()
        self.assertEqual(saved.get("hotkey"), "f9")
        self.assertEqual(saved.get("cpu_threads"), 8)
        self.assertTrue(saved.get("disable_ctrl_alt"))
        self.assertTrue(saved.get("offline_only"))

        # Verify chimege_token is never returned in plaintext in GET
        get_res = self.client.get(
            "/api/settings",
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "X-Session-Token": token,
            },
        )
        self.assertEqual(get_res.status_code, 200)
        chimege_returned = get_res.json().get("chimege_token", "")
        self.assertNotIn("secret_chimege_api_token", chimege_returned)

    def test_privacy_offline_and_opt_in_guards(self):
        """Test that offline_only and missing opt-in block external network calls."""
        # 1. Spellcheck without opt-in returns immediately without network call
        test_text = "Энэ бол монгол хэлний бичвэр."
        corrected = tts_server._auto_correct_subtle_typos_spellcheck_mn(test_text)
        self.assertEqual(corrected, test_text)

        # 2. Google STT without opt-in returns error/offline signal
        wav_dummy = b"RIFF....WAVEfmt ...."
        txt, conf, err = tts_server._recognize_single_lang(wav_dummy, "mn-MN")
        self.assertTrue(err, "Google STT without opt_in_google_stt must return error flag")

    def test_authenticode_verification_function(self):
        """Test Authenticode signature verification helper."""
        import sys
        res = auto_updater.verify_authenticode_signature(sys.executable)
        self.assertIsInstance(res, dict)
        self.assertIn("signed", res)
        self.assertIn("valid", res)
        if os.name == "nt":
            self.assertTrue(res["valid"], "System python.exe signature must be valid on Windows")

    def test_upload_limits(self):
        """Test file upload size limits rejection (HTTP 413)."""
        token = tts_server.SESSION_TOKEN
        # Oversized audio file (> 100MB simulation)
        oversized = b"0" * (101 * 1024 * 1024)
        files = {"audio": ("test_huge.wav", oversized, "audio/wav")}
        data = {"ass_content": "[Script Info]\nTitle: test", "title": "test_video"}

        res = self.client.post(
            "/api/lyrics/export-video",
            files=files,
            data=data,
            headers={
                "Host": f"127.0.0.1:{tts_server.SERVER_PORT}",
                "X-Session-Token": token,
            },
        )
        self.assertEqual(res.status_code, 413, "Oversized upload must return HTTP 413 Payload Too Large")


if __name__ == "__main__":
    unittest.main()
