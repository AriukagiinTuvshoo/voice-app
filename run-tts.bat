@echo off
title VOICE - Local MMS-TTS Server (facebook/mms-tts-khk)
cd /d "%~dp0"

echo ========================================================
echo   VOICE - Mongolian MMS-TTS Local Neural Engine
echo   Model: facebook/mms-tts-khk (Khalkha Mongolian)
echo   Host:  http://localhost:8000
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.10+ oldsongui esvel PATH deer alga.
    echo https://www.python.org/downloads/ haygaar orj Python 3.10+ suulgana uu.
    echo "Add python.exe to PATH" songoltiig zaaval check hiigeerei!
    pause
    exit /b 1
)

echo [*] Python packages shalgaж baina...
python -c "import torch, transformers, scipy, fastapi, uvicorn" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Heregtee sanduudiig suulgaж baina (pip install)...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Packages suulgahad aldaa garlaa.
        pause
        exit /b 1
    )
)

echo.
echo [*] MMS-TTS Server-iig port 8000 deer ehluulj baina...
echo [*] Anh udaa ajilluulj baigaa bol model (~150MB) tatagdana.
echo [*] Daraa ni internetgui ajillana.
echo.
uvicorn tts_server:app --host 0.0.0.0 --port 8000 --reload

pause
