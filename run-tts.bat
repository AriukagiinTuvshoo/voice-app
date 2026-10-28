@echo off
title VOICE - AI Voice Server (Edge Neural & MMS)
cd /d "%~dp0"

echo ========================================================
echo   VOICE - Mongolian AI Voice Server
echo   Voices: mn-MN-YesuiNeural (Есүй), mn-MN-BataaNeural (Батаа)
echo   Host:   http://localhost:8000
echo ========================================================
echo.

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [*] Virtual environment (.venv) uusgej baina...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Python 3.10+ oldsongui. Python suulgasan esehee shalgana uu.
        pause
        exit /b 1
    )
    echo [*] Heregtseet sanduudiig suulgaж baina (edge-tts, fastapi, uvicorn)...
    "%~dp0.venv\Scripts\pip.exe" install -r requirements.txt
)

echo [*] AI Voice Server-iig port 8000 deer ehluulj baina...
echo.
"%VENV_PY%" -m uvicorn tts_server:app --host 0.0.0.0 --port 8000 --reload

pause
