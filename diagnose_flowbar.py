"""VOICE FlowBar diagnostic. Run via Diagnose-VOICE.bat. Uses only the standard library."""
import ctypes, json, os, platform, socket, struct, sys, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("VOICE_PORT", "8000"))
OUT_FILE = os.path.join(BASE, "voice-diagnose.txt")

_output_lines = []


def p(*args):
    text = " ".join(str(a) for a in args)
    print(text)
    _output_lines.append(text)


def line(title):
    p("\n=== " + title + " ===")


def get(path):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", headers={"Host": f"127.0.0.1:{PORT}"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


p("VOICE diagnostic", time.strftime("%Y-%m-%d %H:%M:%S"))
line("Python")
p("version :", sys.version.replace("\n", " "))
p("bits    :", struct.calcsize("P") * 8)
p("platform:", platform.platform())
p("folder  :", BASE)

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

line("Network & Port 8000 Checks")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", PORT))
    s.close()
    p(f"port {PORT} bind : OK (port is free)")
except OSError as err:
    p(f"port {PORT} bind : IN USE (Code: {getattr(err, 'winerror', err.errno)})")
    p(f"-> Port {PORT} is currently listening.")

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

line("System Tray Libraries")
try:
    import pystray
    from PIL import Image
    p("tray libraries : OK (pystray and Pillow available)")
except ImportError as err:
    p("tray libraries : NOT INSTALLED ->", err)
    p("NOTE: Tray is optional. To enable: .venv\\Scripts\\python.exe -m pip install -r requirements-tray.txt")

line("Microphone")
try:
    import sounddevice as sd
    p("default input:", sd.query_devices(kind="input")["name"])
except Exception as e:
    p("microphone check FAILED ->", e)
    p("FIX: Windows Settings > Privacy > Microphone: allow desktop apps; choose a default input device.")

# In non-interactive test mode (VOICE_DIAGNOSE_NO_GUI=1), skip the 6s modal test window
if os.environ.get("VOICE_DIAGNOSE_NO_GUI") != "1" and tk is not None and user32 is not None and work:
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

p("\nDone. Saving report to:", OUT_FILE)
try:
    with open(OUT_FILE, "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(_output_lines) + "\n")
except Exception as e:
    print("Warning saving diagnose file:", e)
