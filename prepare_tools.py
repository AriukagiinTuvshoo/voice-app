import os
import sys
import shutil
import zipfile
import hashlib
import traceback
import subprocess
import urllib.request

WHISPER_URL = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-bin-x64.zip"
WHISPER_SHA256 = "49dcc16de826f20bd53d44f947a1ae49dfa81f86cad67a64d80820cb192d674a"

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_BACKUP_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

def download_file(url, dest_path):
    print(f"[*] Downloading {url} -> {dest_path}...", flush=True)
    curl_bin = shutil.which("curl.exe") or shutil.which("curl")
    if curl_bin:
        cmd = [curl_bin, "-L", "--fail", "--retry", "3", "--retry-delay", "2", "-o", dest_path, url]
        print(f"[*] Executing: {' '.join(cmd)}", flush=True)
        res = subprocess.run(cmd)
        if res.returncode == 0 and os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
            print(f"[+] Download complete via curl: {os.path.getsize(dest_path):,} bytes", flush=True)
            return
        print(f"[!] curl failed with exit code {res.returncode}, falling back to urllib...", flush=True)
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as resp, open(dest_path, "wb") as out_file:
        shutil.copyfileobj(resp, out_file)
    print(f"[+] Download complete via urllib: {os.path.getsize(dest_path):,} bytes", flush=True)

def verify_sha256(file_path, expected_hash):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    actual = h.hexdigest().lower()
    if actual != expected_hash.lower():
        raise ValueError(f"Checksum mismatch for {file_path}: expected {expected_hash}, got {actual}")
    print(f"[+] Checksum verified: {actual}", flush=True)

def prepare_whisper(base_dir):
    whisper_cpp_dir = os.path.join(base_dir, "tools", "whisper.cpp")
    whisper_release_dir = os.path.join(whisper_cpp_dir, "Release")
    whisper_bin = os.path.join(whisper_release_dir, "whisper-cli.exe")
    
    if os.path.isfile(whisper_bin):
        print(f"[+] whisper-cli.exe already present at {whisper_bin}", flush=True)
    else:
        os.makedirs(whisper_cpp_dir, exist_ok=True)
        tmp_zip = os.path.join(base_dir, "whisper-temp.zip")
        download_file(WHISPER_URL, tmp_zip)
        verify_sha256(tmp_zip, WHISPER_SHA256)
        print(f"[*] Extracting {tmp_zip} to {whisper_cpp_dir}...", flush=True)
        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extractall(whisper_cpp_dir)
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)
        
        # In case the zip extracts flat or nested, locate whisper-cli.exe
        if not os.path.isfile(whisper_bin):
            found_dir = None
            for root, dirs, files in os.walk(whisper_cpp_dir):
                if "whisper-cli.exe" in files:
                    found_dir = root
                    break
            if found_dir and found_dir != whisper_release_dir:
                os.makedirs(whisper_release_dir, exist_ok=True)
                for item in os.listdir(found_dir):
                    src_item = os.path.join(found_dir, item)
                    dst_item = os.path.join(whisper_release_dir, item)
                    if not os.path.exists(dst_item):
                        shutil.move(src_item, dst_item)
    
    # Test execution
    res = subprocess.run([whisper_bin, "--help"], capture_output=True, text=True, timeout=10)
    if res.returncode != 0:
        raise RuntimeError(f"whisper-cli.exe failed verification: {res.stderr}")
    print("[+] whisper-cli.exe verified successfully!", flush=True)

def prepare_ffmpeg(base_dir):
    ffmpeg_dir = os.path.join(base_dir, "tools", "ffmpeg")
    ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    
    if os.path.isfile(ffmpeg_bin):
        print(f"[+] ffmpeg.exe already present at {ffmpeg_bin}", flush=True)
    else:
        os.makedirs(ffmpeg_dir, exist_ok=True)
        copied = False
        
        # Check standard chocolatey real bin path (avoiding shims)
        choco_ffmpeg = r"C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe"
        if os.path.isfile(choco_ffmpeg) and os.path.getsize(choco_ffmpeg) > 30 * 1024 * 1024:
            print(f"[*] Found pre-installed chocolatey static FFmpeg at {choco_ffmpeg}", flush=True)
            shutil.copy2(choco_ffmpeg, ffmpeg_bin)
            copied = True
        
        if not copied:
            tmp_zip = os.path.join(base_dir, "ffmpeg-temp.zip")
            try:
                download_file(FFMPEG_URL, tmp_zip)
            except Exception as e:
                print(f"[!] Primary FFmpeg download failed ({e}), trying backup...", flush=True)
                download_file(FFMPEG_BACKUP_URL, tmp_zip)
            
            print(f"[*] Extracting ffmpeg from {tmp_zip}...", flush=True)
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
    print("[+] ffmpeg.exe verified with libass and subtitles!", flush=True)

if __name__ == "__main__":
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        print(f"[*] Preparing native AI tools in '{base_dir}'...", flush=True)
        prepare_whisper(base_dir)
        prepare_ffmpeg(base_dir)
        print("[+] All native AI tools prepared and verified successfully!", flush=True)
    except Exception as e:
        print(f"[FATAL ERROR in prepare_tools.py]: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        sys.exit(1)
