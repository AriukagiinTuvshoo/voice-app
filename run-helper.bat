@echo off
rem VOICE Desktop Helper: system-wide Ctrl+Alt / F8 dictation into any window (Chrome, Word, Facebook...)
cd /d "%~dp0"

netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% equ 0 exit /b 0

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
) else (
    start "" pythonw -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
)
exit /b 0
