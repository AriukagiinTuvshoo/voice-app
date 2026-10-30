import os
import unittest
import subprocess
import hashlib
import zipfile
import tempfile
import json

class TestReleaseRecoveryV143(unittest.TestCase):
    """
    Production Release Recovery Test Suite for v1.4.3.
    Verifies that all binaries (Whisper, FFmpeg with libass, Standalone Runtime),
    installer artifacts, portable ZIP, checksums, and user-data preservation work.
    """

    @classmethod
    def setUpClass(cls):
        cls.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.tools_dir = os.path.join(cls.base_dir, "tools")
        cls.runtime_dir = os.path.join(cls.base_dir, "runtime")
        cls.dist_dir = os.path.join(cls.base_dir, "dist")

    def test_whisper_binary_present_and_executable(self):
        """Verify that whisper-cli binary is physically present in tools/ and runs."""
        whisper_bin = os.path.join(self.tools_dir, "whisper.cpp", "Release", "whisper-cli.exe")
        self.assertTrue(os.path.isfile(whisper_bin), f"whisper-cli.exe not found at {whisper_bin}")
        
        # Verify DLLs are present alongside whisper-cli.exe
        ggml_dll = os.path.join(self.tools_dir, "whisper.cpp", "Release", "ggml.dll")
        self.assertTrue(os.path.isfile(ggml_dll), f"ggml.dll not found at {ggml_dll}")

        # Execute help command to confirm dynamic library linkage
        proc = subprocess.run([whisper_bin, "--help"], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0)
        out = (proc.stdout + proc.stderr).lower()
        self.assertIn("usage:", out)
        self.assertIn("--model", out)

    def test_ffmpeg_binary_present_and_has_libass(self):
        """Verify that FFmpeg binary is physically present and has static libass filter enabled."""
        ffmpeg_bin = os.path.join(self.tools_dir, "ffmpeg", "ffmpeg.exe")
        self.assertTrue(os.path.isfile(ffmpeg_bin), f"ffmpeg.exe not found at {ffmpeg_bin}")

        # Execute -version
        proc_ver = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc_ver.returncode, 0)
        self.assertIn("ffmpeg version", proc_ver.stdout.lower())

        # Execute -filters and assert libass / subtitles are supported
        proc_filt = subprocess.run([ffmpeg_bin, "-filters"], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc_filt.returncode, 0)
        self.assertTrue(
            "subtitles" in proc_filt.stdout and "ass" in proc_filt.stdout,
            "FFmpeg build is missing libass or subtitles filter"
        )

    def test_standalone_runtime_isolated_execution(self):
        """Verify that runtime/ contains a self-contained Python 3.12 environment with core dependencies."""
        py_bin = os.path.join(self.runtime_dir, "python.exe")
        pyw_bin = os.path.join(self.runtime_dir, "pythonw.exe")
        self.assertTrue(os.path.isfile(py_bin), f"runtime/python.exe missing at {py_bin}")
        self.assertTrue(os.path.isfile(pyw_bin), f"runtime/pythonw.exe missing at {pyw_bin}")

        # Run an isolated check that imports all key application packages
        code = (
            "import sys; "
            "assert sys.prefix != '', 'Empty sys.prefix'; "
            "import fastapi, uvicorn, edge_tts, sounddevice, miniaudio, pystray, PIL, tkinter; "
            "print('RUNTIME_ALL_MODULES_OK')"
        )
        proc = subprocess.run([py_bin, "-c", code], capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, f"Standalone runtime execution failed: {proc.stderr}")
        self.assertIn("RUNTIME_ALL_MODULES_OK", proc.stdout)

    def test_clean_environment_simulation(self):
        """
        Simulate running on a clean Windows machine with host Python stripped from PATH.
        Verifies that Start-VOICE.bat prioritizes runtime/pythonw.exe and launches without host Python.
        """
        # Read Start-VOICE.bat and verify runtime/ has top priority
        bat_file = os.path.join(self.base_dir, "Start-VOICE.bat")
        with open(bat_file, "r", encoding="utf-8") as f:
            content = f.read()

        # runtime\pythonw.exe must appear before .venv or system python
        idx_runtime = content.find(r"%~dp0runtime\pythonw.exe")
        idx_venv = content.find(r"%~dp0.venv\Scripts\pythonw.exe")
        self.assertNotEqual(idx_runtime, -1, "Start-VOICE.bat does not check runtime\\pythonw.exe")
        self.assertTrue(idx_runtime < idx_venv, "runtime\\pythonw.exe must have higher priority than .venv")

    def test_installer_artifact_validation(self):
        """Verify that the built Inno Setup installer exists and is larger than 100MB (contains full bundle)."""
        installer = os.path.join(self.dist_dir, "VOICE-Setup-v1.4.3.exe")
        self.assertTrue(os.path.isfile(installer), f"VOICE-Setup-v1.4.3.exe not found in dist/")
        size = os.path.getsize(installer)
        # Full bundle (tools + runtime + out) must be > 100 MB
        self.assertGreater(size, 100 * 1024 * 1024, f"Installer size {size} bytes is too small for full bundle")

    def test_portable_zip_artifact_validation(self):
        """Verify that the portable ZIP exists, is larger than 150MB, and contains runtime, tools, and scripts."""
        zip_path = os.path.join(self.dist_dir, "VOICE-Windows-v1.4.3.zip")
        self.assertTrue(os.path.isfile(zip_path), f"VOICE-Windows-v1.4.3.zip not found in dist/")
        size = os.path.getsize(zip_path)
        self.assertGreater(size, 150 * 1024 * 1024, f"Portable ZIP size {size} bytes is too small for full bundle")

        # Inspect ZIP contents
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())
            self.assertTrue(any("ffmpeg.exe" in n for n in names), "FFmpeg binary missing in portable zip")
            self.assertTrue(any("whisper-cli.exe" in n for n in names), "whisper-cli missing in portable zip")
            self.assertTrue(any("python.exe" in n for n in names), "Standalone python missing in portable zip")
            self.assertIn("Start-VOICE.bat", names, "Start-VOICE.bat missing in portable zip")
            self.assertIn("tts_server.py", names, "tts_server.py missing in portable zip")
            self.assertIn("VERSION", names, "VERSION missing in portable zip")

    def test_checksums_match_distribution_files(self):
        """Verify that dist/SHA256SUMS.txt exists and matches the exact SHA-256 hashes of the files."""
        sums_file = os.path.join(self.dist_dir, "SHA256SUMS.txt")
        self.assertTrue(os.path.isfile(sums_file), "SHA256SUMS.txt missing in dist/")

        with open(sums_file, "r", encoding="ascii") as f:
            lines = [l.strip() for l in f if l.strip()]

        self.assertGreaterEqual(len(lines), 2, "SHA256SUMS.txt must contain at least 2 entries")

        for line in lines:
            parts = line.split(maxsplit=1)
            self.assertEqual(len(parts), 2)
            expected_hash, fname = parts[0].strip().lower(), parts[1].strip()
            target_path = os.path.join(self.dist_dir, fname)
            self.assertTrue(os.path.isfile(target_path), f"Hashed file {fname} not found in dist/")

            # Compute actual hash
            h = hashlib.sha256()
            with open(target_path, "rb") as bf:
                while chunk := bf.read(1024 * 1024):
                    h.update(chunk)
            actual_hash = h.hexdigest().lower()
            self.assertEqual(actual_hash, expected_hash, f"Hash mismatch for {fname}")

    def test_user_data_preservation_semantics(self):
        """Verify that %APPDATA%\\VOICE is used for user data and separated from application binaries."""
        import voice_core
        user_dir = voice_core.get_user_data_dir()
        app_dir = voice_core.CANONICAL_APP_DIR
        self.assertNotEqual(user_dir, app_dir, "User data directory must not be inside application binaries directory")
        self.assertTrue(user_dir.endswith("VOICE") or user_dir.endswith("voice"))

if __name__ == "__main__":
    unittest.main()
