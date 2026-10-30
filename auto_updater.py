"""
VOICE Auto-updater & GitHub Releases Integration.

Provides semantic version comparison, GitHub release checking,
SHA256 checksum verification, safe URL validation, and secure session installer execution.
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
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("voice.updater")

MAX_INSTALLER_BYTES = 250 * 1024 * 1024  # 250 MB
ALLOWED_DOWNLOAD_PREFIXES = (
    "https://github.com/AriukagiinTuvshoo/voice-app/releases/download/",
    "https://objects.githubusercontent.com/",
    "https://github-releases.githubusercontent.com/",
)

# In-memory verified updater sessions: token -> {installer_path, version, created_at}
_VERIFIED_SESSIONS: Dict[str, Dict[str, Any]] = {}


def parse_semver(version_str: str) -> Tuple[int, int, int]:
    """
    Parse a semantic version string into (major, minor, patch).
    Build metadata (+...) and pre-release suffix (-...) are stripped per semver 2.0.0 specification.
    """
    cleaned = (version_str or "").strip()
    cleaned = re.sub(r"^[vV]", "", cleaned)
    cleaned = cleaned.split("+")[0]
    cleaned = cleaned.split("-")[0]
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", cleaned)
    if not m:
        return (0, 0, 0)
    major = int(m.group(1) or 0)
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return (major, minor, patch)


def parse_semver_extended(version_str: str) -> Tuple[int, int, int, int, str]:
    """
    Parse a semantic version string into (major, minor, patch, is_prerelease, prerelease_tag).
    Properly handles pre-releases: 1.4.1-rc1 is strictly less than 1.4.1.
    """
    cleaned = (version_str or "").strip()
    cleaned = re.sub(r"^[vV]", "", cleaned)
    cleaned = cleaned.split("+")[0]

    prerelease = ""
    is_prerelease = 1  # 1 means final release, 0 means prerelease
    if "-" in cleaned:
        parts = cleaned.split("-", 1)
        cleaned = parts[0]
        prerelease = parts[1]
        is_prerelease = 0

    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", cleaned)
    if not m:
        return (0, 0, 0, 0, "")

    major = int(m.group(1) or 0)
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return (major, minor, patch, is_prerelease, prerelease)


def is_newer_version(latest: str, current: str) -> bool:
    """
    Return True only if latest semver is strictly greater than current semver.
    Example: 1.4.1 > 1.4.0 (True), 1.4.0 > 1.4.0 (False), 1.4.1-rc1 < 1.4.1 (True).
    """
    lat_sem = parse_semver_extended(latest)
    cur_sem = parse_semver_extended(current)
    if (lat_sem[0], lat_sem[1], lat_sem[2]) > (cur_sem[0], cur_sem[1], cur_sem[2]):
        return True
    if (lat_sem[0], lat_sem[1], lat_sem[2]) == (cur_sem[0], cur_sem[1], cur_sem[2]):
        # Same major.minor.patch: final release is newer than prerelease
        return lat_sem[3] > cur_sem[3]
    return False


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
    clean_expected = expected_sha256.strip().lower()
    if len(clean_expected) != 64 or not re.match(r"^[0-9a-f]{64}$", clean_expected):
        return False
    actual = calculate_file_sha256(filepath)
    return actual == clean_expected


def is_allowed_download_url(url: str) -> bool:
    """Validate that download URL strictly belongs to official release hosts."""
    if not url or not url.startswith("https://"):
        return False
    return any(url.startswith(pfx) for pfx in ALLOWED_DOWNLOAD_PREFIXES)


# Safe URL alias
is_safe_download_url = is_allowed_download_url


def parse_checksums_content(text: str) -> Dict[str, str]:
    """Parse SHA256SUMS.txt formatted text into filename -> sha256 lowercase mapping."""
    mapping = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 64:
            sha = parts[0].lower()
            fname = parts[1].lstrip("*")
            mapping[fname] = sha
    return mapping


def fetch_checksums_map(checksums_url: str, timeout_sec: float = 4.0) -> Dict[str, str]:
    """Fetch and parse SHA256SUMS.txt into filename -> sha256 lowercase mapping."""
    if not is_allowed_download_url(checksums_url):
        return {}
    try:
        req = urllib.request.Request(checksums_url, headers={"User-Agent": "VOICE-Updater"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        return parse_checksums_content(text)
    except Exception as e:
        logger.info("[Updater] Checksums fetch failed: %s", e)
        return {}


def check_github_release(
    repo: str = "AriukagiinTuvshoo/voice-app",
    current_version: str = "1.4.1",
    timeout_sec: float = 4.0,
) -> Dict[str, Any]:
    """
    Query GitHub API for latest release metadata.
    Extracts assets, parses SHA256SUMS.txt, and sets expected_sha256.
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

        installer_url = ""
        zip_url = ""
        checksums_url = ""
        installer_name = ""

        assets = data.get("assets", [])
        for a in assets:
            name = a.get("name", "")
            d_url = a.get("browser_download_url", "")
            if name.endswith(".exe") and ("setup" in name.lower() or "voice" in name.lower()):
                installer_url = d_url
                installer_name = name
            elif name.endswith(".zip"):
                zip_url = d_url
            elif "sha256" in name.lower():
                checksums_url = d_url

        expected_installer_sha256 = ""
        if checksums_url:
            c_map = fetch_checksums_map(checksums_url, timeout_sec=3.0)
            if installer_name and installer_name in c_map:
                expected_installer_sha256 = c_map[installer_name]
            else:
                for k, v in c_map.items():
                    if k.endswith(".exe"):
                        expected_installer_sha256 = v
                        break

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
        logger.info("[Updater] Network notice: %s", ue)
        return {
            "has_update": False,
            "current_version": current_version,
            "latest_version": current_version,
            "error": "Интернэт холболтгүй эсвэл GitHub API хариу өгсөнгүй.",
        }
    except Exception as e:
        logger.warning("[Updater] Release check error: %s", e)
        return {
            "has_update": False,
            "current_version": current_version,
            "latest_version": current_version,
            "error": str(e),
        }


def download_and_verify_installer(
    download_url: str,
    expected_sha256: str,
    progress_callback: Optional[Any] = None,
) -> str:
    """
    Download installer .exe to a secure temp directory with strict URL and SHA256 verification.
    Raises ValueError on security failure or hash mismatch. Returns path on success.
    """
    if not is_allowed_download_url(download_url):
        raise ValueError("Хүчингүй татах хаяг: Зөвхөн албан ёсны GitHub Releases хаягаас татна.")

    clean_sha = (expected_sha256 or "").strip().lower()
    if len(clean_sha) != 64 or not re.match(r"^[0-9a-f]{64}$", clean_sha):
        raise ValueError("Шалгах SHA-256 хэш байхгүй эсвэл буруу байна.")

    tmp_dir = tempfile.mkdtemp(prefix="voice_upd_")
    installer_path = os.path.join(tmp_dir, "VOICE-Setup-Update.exe")

    req = urllib.request.Request(download_url, headers={"User-Agent": "VOICE-Desktop-Updater"})

    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(installer_path, "wb") as out_f:
            total_len = int(resp.headers.get("Content-Length", 0))
            if total_len > MAX_INSTALLER_BYTES:
                raise ValueError(f"Файлын хэмжээ хэтэрсэн байна: {total_len} bytes")

            downloaded = 0
            while chunk := resp.read(65536):
                downloaded += len(chunk)
                if downloaded > MAX_INSTALLER_BYTES:
                    raise ValueError("Татаж авсан хэмжээ зөвшөөрөгдөх дээд хязгаараас хэтэрлээ.")
                out_f.write(chunk)
                if progress_callback and total_len > 0:
                    progress_callback(downloaded, total_len)

        # Mandatory SHA-256 validation
        if not verify_file_sha256(installer_path, clean_sha):
            if os.path.exists(installer_path):
                os.remove(installer_path)
            raise ValueError("Татаж авсан installer-ийн SHA256 шалгалт зөрүүтэй байна!")

        return installer_path
    except Exception:
        # Secure cleanup on any failure
        if os.path.exists(installer_path):
            try:
                os.remove(installer_path)
            except Exception:
                pass
        raise


def create_update_session(installer_path: str, version: str) -> str:
    """Store verified installer path in secure session mapping and return session token."""
    token = str(uuid.uuid4())
    _VERIFIED_SESSIONS[token] = {
        "installer_path": installer_path,
        "version": version,
        "created_at": time.time(),
    }
    return token


def get_verified_session_installer(session_token: str) -> Optional[str]:
    """Retrieve verified installer path for given session token."""
    sess = _VERIFIED_SESSIONS.get(session_token)
    if not sess:
        return None
    path = sess.get("installer_path")
    if path and os.path.isfile(path):
        return path
    return None


def invalidate_update_session(session_token: str) -> None:
    """Invalidate and remove session token."""
    _VERIFIED_SESSIONS.pop(session_token, None)


def launch_installer_and_exit(installer_path: str) -> None:
    """
    Launch verified installer as a detached process and terminate current VOICE server
    cleanly so file locks are released for in-place upgrade.
    """
    if not os.path.isfile(installer_path):
        raise FileNotFoundError(f"Installer not found: {installer_path}")

    # Launch detached installer in Windows
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen([installer_path], close_fds=True, creationflags=creationflags)
    # Allow 0.3s for spawn, then hard exit to release file locks
    time.sleep(0.3)
    os._exit(0)
