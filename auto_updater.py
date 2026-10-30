"""
VOICE Auto-updater & GitHub Releases Integration.

Provides semantic version comparison, GitHub release checking,
SHA256 checksum verification, and safe installer download/launch.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("voice.updater")


def parse_semver(version_str: str) -> Tuple[int, int, int]:
    """
    Parse a semantic version string (e.g. 'v1.4.0', '1.3.2', 'v1.4.0-beta') into (major, minor, patch).
    Non-numeric suffixes are stripped for comparison.
    """
    cleaned = re.sub(r"^[vV]", "", (version_str or "").strip())
    # Match major.minor.patch
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", cleaned)
    if not m:
        return (0, 0, 0)
    major = int(m.group(1) or 0)
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return (major, minor, patch)


def is_newer_version(latest: str, current: str) -> bool:
    """Return True only if latest semver is strictly greater than current semver."""
    return parse_semver(latest) > parse_semver(current)


def calculate_file_sha256(filepath: str) -> str:
    """Calculate SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def verify_file_sha256(filepath: str, expected_sha256: str) -> bool:
    """Verify that a file matches the expected SHA256 checksum (case-insensitive)."""
    if not os.path.isfile(filepath) or not expected_sha256:
        return False
    actual = calculate_file_sha256(filepath)
    return actual == expected_sha256.strip().lower()


def check_github_release(
    repo: str = "AriukagiinTuvshoo/voice-app",
    current_version: str = "1.4.0",
    timeout_sec: float = 4.0,
) -> Dict[str, Any]:
    """
    Query GitHub API for latest release metadata.
    Does NOT throw unhandled exceptions; returns informative dictionary.
    """
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": f"VOICE-Desktop-App/{current_version}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            if resp.status != 200:
                return {
                    "has_update": False,
                    "current_version": current_version,
                    "latest_version": current_version,
                    "error": f"GitHub API returned HTTP {resp.status}",
                }
            data = json.loads(resp.read().decode("utf-8"))

        tag_name = data.get("tag_name", "").lstrip("v")
        has_update = is_newer_version(tag_name, current_version)

        # Extract assets
        installer_url = ""
        zip_url = ""
        checksums_url = ""
        expected_installer_sha256 = ""

        assets = data.get("assets", [])
        for a in assets:
            name = a.get("name", "")
            d_url = a.get("browser_download_url", "")
            if name.endswith(".exe") and ("setup" in name.lower() or "voice" in name.lower()):
                installer_url = d_url
            elif name.endswith(".zip"):
                zip_url = d_url
            elif "sha256" in name.lower():
                checksums_url = d_url

        return {
            "has_update": has_update,
            "current_version": current_version,
            "latest_version": tag_name or current_version,
            "release_name": data.get("name", f"VOICE v{tag_name}"),
            "release_notes": data.get("body", ""),
            "html_url": data.get("html_url", ""),
            "published_at": data.get("published_at", ""),
            "installer_url": installer_url,
            "zip_url": zip_url,
            "checksums_url": checksums_url,
            "expected_sha256": expected_installer_sha256,
        }
    except urllib.error.URLError as ue:
        logger.info(f"[Updater] Network notice while checking release: {ue}")
        return {
            "has_update": False,
            "current_version": current_version,
            "latest_version": current_version,
            "error": "Интернэт холболтгүй эсвэл GitHub API хариу өгсөнгүй.",
        }
    except Exception as e:
        logger.warning(f"[Updater] Failed to check release: {e}")
        return {
            "has_update": False,
            "current_version": current_version,
            "latest_version": current_version,
            "error": str(e),
        }


def download_and_verify_installer(
    download_url: str,
    expected_sha256: Optional[str] = None,
    progress_callback: Optional[Any] = None,
) -> str:
    """
    Download installer .exe to a secure temp directory and optionally verify its SHA256.
    Returns path to the downloaded installer.
    """
    if not download_url or not download_url.startswith("https://"):
        raise ValueError("Зөвхөн аюулгүй HTTPS татах хаяг дэмжигдэнэ.")

    tmp_dir = tempfile.mkdtemp(prefix="voice_update_")
    installer_path = os.path.join(tmp_dir, "VOICE-Setup-Latest.exe")

    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": "VOICE-Desktop-Updater"},
    )

    with urllib.request.urlopen(req, timeout=30) as resp, open(installer_path, "wb") as out_f:
        total_len = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        while chunk := resp.read(65536):
            downloaded += len(chunk)
            out_f.write(chunk)
            if progress_callback and total_len > 0:
                progress_callback(downloaded, total_len)

    if expected_sha256:
        if not verify_file_sha256(installer_path, expected_sha256):
            os.remove(installer_path)
            raise ValueError("Татаж авсан installer-ийн SHA256 шалгалт амжилтгүй боллоо!")

    return installer_path


def launch_installer_and_exit(installer_path: str) -> None:
    """
    Launch the downloaded installer and cleanly terminate the current VOICE process.
    """
    if not os.path.isfile(installer_path):
        raise FileNotFoundError(f"Installer not found: {installer_path}")

    # Launch detached installer
    subprocess.Popen([installer_path], close_fds=True)
    # Give it a moment to spawn, then exit cleanly
    time.sleep(0.5)
    sys.exit(0)
