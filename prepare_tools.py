import os
import sys
import shutil
import zipfile
import hashlib
import subprocess
import urllib.request

WHISPER_URL = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-bin-x64.zip"
WHISPER_SHA256 = "49dcc16de826f20bd53d44f947a1ae49dfa81f86cad67a64d80820cb192d674a"

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_BACKUP_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

def download_file(url, dest_path):
    print(f"[*] Downloading {url} -> {dest_path}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest_path, "wb") as out_file:
        shutil.copyfileobj(resp, out_file)
    print(f"[+] Download complete: {os.path.getsize(dest_path):,} bytes")

def verify_sha256(file_path, expected_hash):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    actual = h.hexdigest().lower()
    if actual != expected_hash.lower():
        raise ValueError(f"Checksum mismatch for {file_path}: expected {expected_hash}, got {actual}")
    print(f"[+] Checksum verified: {actual}")

def prepare_whisper(base_dir):
    whisper_dir = os.path.join(base_dir, "tools", "whisper.cpp", "Release")
    whisper_bin = os.path.join(whisper_dir, "whisper-cli.exe")
    if os.path.isfile(whisper_bin):
        print(f"[+] whisper-cli.exe already present at {whisper_bin}")
    else:
        os.makedirs(whisper_dir, exist_ok=True)
        tmp_zip = os.path.join(base_dir, "whisper-temp.zip")
        download_file(WHISPER_URL, tmp_zip)
        verify_sha256(tmp_zip, WHISPER_SHA256)
        print(f"[*] Extracting {tmp_zip} to {whisper_dir}...")
        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extractall(whisper_dir)
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)
    
    # Test execution
    res = subprocess.run([whisper_bin, "--help"], capture_output=True, text=True, timeout=10)
    if res.returncode != 0:
        raise RuntimeError(f"whisper-cli.exe failed verification: {res.stderr}")
    print("[+] whisper-cli.exe verified successfully!")

def prepare_ffmpeg(base_dir):
    ffmpeg_dir = os.path.join(base_dir, "tools", "ffmpeg")
    ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    
    if os.path.isfile(ffmpeg_bin):
        print(f"[+] ffmpeg.exe already present at {ffmpeg_bin}")
    else:
        os.makedirs(ffmpeg_dir, exist_ok=True)
        # Check if system has a qualified ffmpeg
        sys_ffmpeg = shutil.which("ffmpeg")
        copied = False
        if sys_ffmpeg:
            try:
                res = subprocess.run([sys_ffmpeg, "-filters"], capture_output=True, text=True, timeout=10)
                if "subtitles" in res.stdout and "ass" in res.stdout:
                    print(f"[*] Found system FFmpeg with libass at {sys_ffmpeg}, copying...")
                    shutil.copy2(sys_ffmpeg, ffmpeg_bin)
                    copied = True
            except Exception as e:
                print(f"[!] System ffmpeg check failed: {e}")
        
        if not copied:
            tmp_zip = os.path.join(base_dir, "ffmpeg-temp.zip")
            try:
                download_file(FFMPEG_URL, tmp_zip)
            except Exception as e:
                print(f"[!] Primary FFmpeg download failed ({e}), trying backup...")
                download_file(FFMPEG_BACKUP_URL, tmp_zip)
            
            print(f"[*] Extracting ffmpeg from {tmp_zip}...")
            with zipfile.ZipFile(tmp_zip, "r") as z:
                for member in z.namelist():
                    if member.endswith("ffmpeg.exe"):
                        with z.open(member) as src, open(ffmpeg_bin, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        break
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)

    # Test execution
    res_ver = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=10)
    if res_ver.returncode != 0 or "ffmpeg version" not in res_ver.stdout.lower():
        raise RuntimeError(f"ffmpeg.exe version check failed: {res_ver.stderr}")
    
    res_filt = subprocess.run([ffmpeg_bin, "-filters"], capture_output=True, text=True, timeout=10)
    if "subtitles" not in res_filt.stdout or "ass" not in res_filt.stdout:
        raise RuntimeError("ffmpeg.exe is missing libass or subtitles filter")
    print("[+] ffmpeg.exe verified with libass and subtitles!")

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    print(f"[*] Preparing native AI tools in '{base_dir}'...")
    prepare_whisper(base_dir)
    prepare_ffmpeg(base_dir)
    print("[+] All native AI tools prepared and verified successfully!")
