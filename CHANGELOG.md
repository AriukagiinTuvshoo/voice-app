# Changelog

## 1.2.7
Phase 1-4 Feature Enhancements & Chrome / Web Compatibility:
- **Chrome & Browser Input Focus Fix**: Resolved Chromium Omnibox / search input unfocusing caused by Windows Alt menu activation; implemented chorded _suppress_alt_menu_activation() and atomic 4-keystroke SendInput for Ctrl+V pasting.
- **Universal Hotkeys**: Ctrl+Alt and F8 now always work as universal dictation hotkeys regardless of custom hotkey choice in settings.
- **Audio Cues (FlowBar Sound Feedback)**: Added non-blocking audio cues (winsound.Beep) on recording start, success paste, and error.
- **Mongolian Number Normalization**: Added 
ormalize_mongolian_numbers() converting spoken Mongolian numbers to digits (e.g. 'хоёр мянга хорин зургаа' -> '2026', 'ерэн таван хувь' -> '95%').
- **Auto Punctuation & Capitalization**: Added ormat_speech_text() automatically capitalizing sentences and appending ? to questions or . to statements.
- **SSML Cadence Pauses**: Added enhance_ssml_cadence() for natural comma and period breath pauses in Edge-TTS.
- **Release Update Checker**: Added non-blocking GET /api/check-update checking GitHub Releases API.
- **Expanded Unit Tests**: Added 4 new unit tests in 	ests/test_logic.py (total 19 tests all passing).

## 1.2.6
Architecture, Reliability, Testing & FlowBar Enhancement:
- Core Separation & Unit Tests: Extracted pure logic functions into voice_core.py. Added 15 comprehensive unit tests in tests/test_logic.py covering settings sanitization, voice cloning safety, position clamping, Tkinter event loops, and FastAPI endpoints.
- Continuous Integration: Added multi-platform GitHub Actions workflow (.github/workflows/ci.yml) running compile and unittest suites across Windows & Ubuntu on Python 3.10 and 3.12.
- FlowBar Off-Screen Prevention: Added clamp_rect_to_screen on initial window load and in self-heal watchdog to prevent FlowBar from appearing off-screen on varied DPI/multi-monitor setups.
- System Tray Icon: Added optional background tray icon (pystray + Pillow) via requirements-tray.txt providing quick access to toggle FlowBar, check status, and exit.
- Windows Autostart Integration: Added GET /api/autostart and POST /api/autostart managing HKCU\Software\Microsoft\Windows\CurrentVersion\Run.
- Undo Last Insert & Clipboard Restore: Implemented Ctrl+Z undo buffer (valid for 8 seconds after insertion) and configurable restore_clipboard setting.
- Hotkey Health Monitoring: Added hotkey_ok and hotkey_error diagnostics in /health.
- Diagnostics & Log Rotation: Replaced custom logger with standard RotatingFileHandler (2 MB x 3 backups); extended diagnose_flowbar.py with port 8000 socket check, HKCU Run verification, and automatic voice-diagnose.txt generation.
- Installer Repair Mode: Added --repair / repair switch to Install-VOICE.bat to reconstruct virtual environment without touching clones/ or voice_settings.json.

## 1.2.5
FlowBar reliability fixes:
- The dashboard no longer says "FlowBar: Active" when the floating window is not running. Status now includes `ui_alive`, `ui_error`, `mic_ok`, `mic_error`.
- The FlowBar redraw loop can no longer die silently after one error (it always reschedules); failures are logged with a traceback.
- The window thread is supervised and restarted automatically (up to 3 times); "show" and "Reset position" start it again if it is dead.
- Tk is now only touched from its own thread ("Reset position"/"show" go through a command queue).
- Self-healing: every 2 s the bar is checked to be visible, topmost and on a real monitor; otherwise it is moved back to the bottom-right.
- Size mismatch fixed (reset used 340x46, window is 360x52, which clipped the close button).
- Removed colour-emoji glyphs and fractional pixel sizes from the Tk canvas; fonts use pixel sizes so text does not overflow on high-DPI screens; redraws only on change (less flicker/CPU).
- Microphone is reopened automatically every 5 s if missing; a clear error is shown on the bar.
- Fixed regression from 1.2.4: the settings whitelist rejected hotkeys `alt_shift`, `ctrl_space`, `f2`, `f4`.
- Installer now stops a running older engine before copying (otherwise the old code kept running), and installs `Diagnose-VOICE.bat` / `diagnose_flowbar.py`.

## 1.2.4
Security and reliability fixes (path traversal in clone endpoints, settings validation, upload limits, safer clipboard restore, no silent pip install, log rotation, README fixes).
