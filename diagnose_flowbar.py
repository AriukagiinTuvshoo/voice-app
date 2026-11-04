"""VOICE System & FlowBar diagnostic. Run via Diagnose-VOICE.bat or python tts_server.py --diagnose."""
import ctypes
import json
import os
import platform
import socket
import struct
import sys
import time
import urllib.request
from typing import List, Optional

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("VOICE_PORT", "8000"))
OUT_FILE = os.path.join(BASE, "voice-diagnose.txt")

_output_lines: List[str] = []


def p(*args):
    text = " ".join(str(a) for a in args)
    print(text)
    _output_lines.append(text)


def line(title: str):
    p("\n=== " + title + " ===")


def get(path: str):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", headers={"Host": f"127.0.0.1:{PORT}"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def run_diagnostics(no_gui: Optional[bool] = None, output_file: Optional[str] = None) -> str:
    global _output_lines
    _output_lines = []

    target_out_file = output_file or OUT_FILE
    skip_gui = no_gui if no_gui is not None else (os.environ.get("VOICE_DIAGNOSE_NO_GUI") == "1")

    p("VOICE diagnostic", time.strftime("%Y-%m-%d %H:%M:%S"))

    # 1. Versions & OS
    line("Python & Operating System")
    p("version :", sys.version.replace("\n", " "))
    p("bits    :", struct.calcsize("P") * 8)
    p("platform:", platform.platform())
    p("folder  :", BASE)

    v_file = os.path.join(BASE, "VERSION")
    if os.path.isfile(v_file):
        try:
            with open(v_file, "r", encoding="utf-8") as vf:
                p("VOICE VERSION:", vf.read().strip())
        except Exception as e:
            p("VOICE VERSION read error:", e)

    # 2. Tkinter
    line("Tkinter (needed for the floating FlowBar)")
    tk = None
    try:
        import tkinter as tk
        p("tkinter import: OK  (Tk", tk.TkVersion, ")")
    except Exception as e:
        p("tkinter import: FAILED ->", e)
        p("FIX: reinstall Python and tick 'tcl/tk and IDLE', then run Install-VOICE.bat again.")

    user32 = None
    if os.name == "nt":
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

    # 3. Screens
    line("Screens")
    work = None
    if user32:
        r = wintypes.RECT()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        work = (r.left, r.top, r.right, r.bottom)
        p("primary work area:", work)
        p("virtual screen   : x=%d y=%d w=%d h=%d" % (
            user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
            user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)))
        p("monitor count    :", user32.GetSystemMetrics(80))
    else:
        p("(not Windows - skipped)")

    # 4. Saved FlowBar position
    line("Saved FlowBar position")
    pos_file = os.path.join(BASE, "flowbar_pos.txt")
    if os.path.isfile(pos_file):
        try:
            with open(pos_file, encoding="utf-8", errors="replace") as pf:
                pos_text = pf.read().strip()
            p("flowbar_pos.txt:", pos_text)
            parts = pos_text.split(",")
            if len(parts) == 2 and work:
                px, py = int(parts[0]), int(parts[1])
                if px < work[0] or px > work[2] or py < work[1] or py > work[3]:
                    p("-> WARNING: Position is outside work area bounds! Clamping is applied automatically.")
                else:
                    p("-> Position is inside screen work area bounds: OK")
        except Exception as e:
            p("failed reading flowbar_pos.txt:", e)
    else:
        p("no saved position (default bottom-right is used)")

    # 5. Network & Port Checks
    line(f"Network & Port {PORT} Checks")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", PORT))
        s.close()
        p(f"port {PORT} bind : OK (port is free)")
    except OSError as err:
        p(f"port {PORT} bind : IN USE (Code: {getattr(err, 'winerror', err.errno)})")
        p(f"-> Port {PORT} is currently listening.")

    # 6. Running Engine Health
    line("Running VOICE engine")
    h = get("/health")
    p("/health        :", json.dumps(h, ensure_ascii=False))
    f = get("/flowbar/status")
    p("/flowbar/status:", json.dumps(f, ensure_ascii=False))
    if "_error" in h:
        p("-> Engine is NOT running or not responding. Start VOICE from the desktop shortcut and run this again.")
    else:
        if h.get("version") is None:
            p("-> This engine is an OLD version (no 'version' field). Run Install-VOICE.bat again.")
        if h.get("flowbar_ui_alive") is False:
            p("-> FlowBar window is NOT alive. Reason:", h.get("flowbar_error") or "(none recorded, see log below)")
        if h.get("mic_ok") is False:
            p("-> Microphone problem:", h.get("mic_error"))
        if h.get("hotkey_ok") is False:
            p("-> Hotkey problem:", h.get("hotkey_error"))

    # 7. GPU & AI Acceleration
    line("Hardware Acceleration (GPU / CUDA / CPU)")
    try:
        import voice_core
        gpu_info = voice_core.detect_gpu_hardware()
        p("has_gpu              :", gpu_info.get("has_gpu"))
        p("gpu_name             :", gpu_info.get("gpu_name") or "(none)")
        p("vram_mb              :", gpu_info.get("vram_mb"))
        p("cuda_version         :", gpu_info.get("cuda_version") or "(none)")
        p("cuda_binary_available:", gpu_info.get("cuda_binary_available"))
        p("backend_status       :", gpu_info.get("backend_status"))
        p("status_message       :", gpu_info.get("status_message"))
    except Exception as e:
        p("GPU check error      :", e)

    # 8. Local Models
    line("Local Whisper Models Availability")
    try:
        import voice_core
        models = voice_core.list_available_local_models()
        for m in models:
            status = "DOWNLOADED" if m.get("is_downloaded") else "MISSING"
            p(f"  [{status:10}] {m.get('id'):12} size: {m.get('size_mb', 0)}MB | path: {m.get('local_path') or '-'}")
    except Exception as e:
        p("Model availability check error:", e)

    # 9. Autostart Registry
    line("Windows Registry Autostart (HKCU Run)")
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "VOICE")
                p("HKCU Run entry :", val)
        except FileNotFoundError:
            p("HKCU Run entry : (not registered - autostart is OFF)")
        except Exception as e:
            p("HKCU Run check error:", e)
    else:
        p("(not Windows - skipped)")

    # 10. System Tray Libraries
    line("System Tray Libraries")
    try:
        import pystray
        from PIL import Image
        p("tray libraries : OK (pystray and Pillow available)")
    except ImportError as err:
        p("tray libraries : NOT INSTALLED ->", err)
        p("NOTE: Tray is optional. To enable: .venv\\Scripts\\python.exe -m pip install -r requirements-tray.txt")

    # 11. Microphone & Audio Devices
    line("Microphone & Audio Input Devices")
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        default_in = sd.query_devices(kind="input")
        p("default input device :", default_in.get("name"))
        p("all input devices:")
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                p(f"  [{idx}] {dev.get('name')} (inputs: {dev.get('max_input_channels')}, default_samplerate: {dev.get('default_samplerate')})")
    except Exception as e:
        p("microphone check FAILED ->", e)
        p("FIX: Windows Settings > Privacy > Microphone: allow desktop apps; choose a default input device.")

    # 12. Visual FlowBar Test
    if not skip_gui and tk is not None and user32 is not None and work:
        line("Visual test: a small purple bar appears for 6 seconds")
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            w, h2 = 360, 52
            x, y = max(work[0] + 20, work[2] - w - 24), max(work[1] + 20, work[3] - h2 - 24)
            root.geometry(f"{w}x{h2}+{x}+{y}")
            c = tk.Canvas(root, width=w, height=h2, bg="#1e1b4b", highlightthickness=2, highlightbackground="#6366f1")
            c.pack()
            c.create_text(180, 26, text="VOICE FlowBar TEST", fill="white", font=("Segoe UI", -14, "bold"))
            root.after(6000, root.destroy)
            p(f"Created test window at ({x},{y}). Look at the bottom-right corner of your screen now...")
            root.mainloop()
            p("Test window closed normally.")
            p("-> If you SAW the bar: Tk works; the problem is only the VOICE engine (see section above).")
            p("-> If you did NOT see it: something is hiding it (full-screen app, remote desktop, graphics driver).")
        except Exception as e:
            p("Test window FAILED ->", type(e).__name__, e)
    else:
        line("Visual test: (skipped or disabled via VOICE_DIAGNOSE_NO_GUI)")

    # 13. Log tail
    line("Last 100 lines of voice-server.log")
    log = os.path.join(BASE, "voice-server.log")
    if os.path.isfile(log):
        try:
            with open(log, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
                for ln in lines[-100:]:
                    p(ln.rstrip())
        except Exception as e:
            p("Failed reading log:", e)
    else:
        p("(no log file yet)")

    p("\nDone. Saving report to:", target_out_file)
    try:
        with open(target_out_file, "w", encoding="utf-8") as out_f:
            out_f.write("\n".join(_output_lines) + "\n")
    except Exception as e:
        print("Warning saving diagnose file:", e)

    return "\n".join(_output_lines)


if __name__ == "__main__":
    out_arg = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            out_arg = sys.argv[idx + 1]
    no_gui_arg = "--no-gui" in sys.argv or os.environ.get("VOICE_DIAGNOSE_NO_GUI") == "1"
    run_diagnostics(no_gui=no_gui_arg, output_file=out_arg)
