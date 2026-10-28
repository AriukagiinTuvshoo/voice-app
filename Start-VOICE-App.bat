@echo off
chcp 65001 >nul
title VOICE — Studio Desktop App Launcher
cd /d "%~dp0"

echo [1/3] Checking VoiceStudio AI & Duudlaga Flow Server (Port 8000)...
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    if exist ".venv\Scripts\python.exe" (
        start "" /b ".venv\Scripts\python.exe" -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    ) else (
        start "" /b python -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    )
    timeout /t 2 /nobreak >nul
)

echo [2/3] Checking VOICE Web Interface (Port 3000)...
netstat -ano | findstr ":3000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    start "" /b cmd /c "npm run dev"
    timeout /t 4 /nobreak >nul
)

echo [3/3] Opening VOICE Standalone Desktop App Window...
where msedge >nul 2>nul
if %errorlevel% equ 0 (
    start "" msedge --app=http://localhost:3000 --window-size=1280,820
    exit /b 0
)

where chrome >nul 2>nul
if %errorlevel% equ 0 (
    start "" chrome --app=http://localhost:3000 --window-size=1280,820
    exit /b 0
)

start "" "http://localhost:3000"
