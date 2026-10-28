@echo off
cd /d "%~dp0"
title VOICE - Desktop Launcher

echo ============================================================
echo   VOICE - Desktop Voice Dictation Launcher
echo ============================================================
echo.

echo [1/2] Checking Python dependencies...
python -c "import uvicorn, fastapi, multipart" 2>nul
if %errorlevel% neq 0 (
    echo Installing required packages...
    pip install -q python-multipart uvicorn fastapi sounddevice soundfile speechrecognition edge-tts scipy numpy
)

echo [2/2] Starting VOICE AI Engine ^& Floating Pill...
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    if exist ".venv\Scripts\python.exe" (
        start "VOICE-AI" ".venv\Scripts\python.exe" -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    ) else (
        start "VOICE-AI" python -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    )
    timeout /t 3 /nobreak >nul
)

echo.
echo ============================================================
echo   [SUCCESS] VOICE FLOW floating pill is now on your screen!
echo.
echo   - Click the floating pill at bottom-right or press Ctrl+Alt / F8
echo   - Speak in Mongolian to type directly into any app!
echo ============================================================
timeout /t 4 >nul
exit /b 0
