@echo off
chcp 65001 >nul
title VOICE Desktop Launcher
cd /d "%~dp0"

echo =======================================================
echo   VOICE - Speak. Clean. Write. (v1.2.0)
echo   Монгол, Англи, Япон яриа таних ба Windows шууд бичигч
echo =======================================================
echo.

:: 1. Unblock files for Windows Smart App Control
powershell -NoProfile -Command "Get-ChildItem -Path '%~dp0' -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1

:: 2. Check if port 8000 is responding properly
set "NEED_START=1"
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    powershell -NoProfile -Command "(Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue).StatusCode" 2>nul | findstr "200" >nul
    if %errorlevel% equ 0 (
        set "NEED_START=0"
        echo [1/2] VOICE Engine аль хэдийн бэлэн ажиллаж байна.
    ) else (
        echo [1/2] Порт 8000 гацсан байсан тул шинэчилж байна...
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
            taskkill /F /PID %%a >nul 2>&1
        )
        timeout /t 1 /nobreak >nul
    )
)

:: 3. Start Python tts_server.py (preferred for hardware mic, Ctrl+Alt & native FlowBar) or node server.cjs
if "%NEED_START%"=="1" (
    echo [1/2] VOICE Engine эхлүүлж байна (Port 8000)...
    set "PYTHON_EXE="
    if exist "%~dp0.venv\Scripts\pythonw.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\pythonw.exe"
    if not defined PYTHON_EXE if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    if not defined PYTHON_EXE if exist "C:\Users\enhtv\.gemini\antigravity\scratch\voice-main\.venv\Scripts\pythonw.exe" set "PYTHON_EXE=C:\Users\enhtv\.gemini\antigravity\scratch\voice-main\.venv\Scripts\pythonw.exe"
    if not defined PYTHON_EXE if exist "C:\Users\enhtv\.gemini\antigravity\scratch\voice-main\.venv\Scripts\python.exe" set "PYTHON_EXE=C:\Users\enhtv\.gemini\antigravity\scratch\voice-main\.venv\Scripts\python.exe"

    if defined PYTHON_EXE if exist "%~dp0tts_server.py" (
        start "" "%PYTHON_EXE%" "%~dp0tts_server.py"
    ) else (
        start /b "" node "%~dp0server.cjs" 8000
    )
    timeout /t 2 /nobreak >nul
)

:: 4. Launch Main App Window in Microsoft Edge / Chrome App Mode (1-second instant start)
echo [2/2] VOICE ажлын талбарыг нээж байна...
set "APP_URL=http://127.0.0.1:8000/dashboard"

if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=%APP_URL% --window-size=1280,820
    exit /b 0
)

if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=%APP_URL% --window-size=1280,820
    exit /b 0
)

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=%APP_URL% --window-size=1280,820
    exit /b 0
)

start "" "%APP_URL%"
exit /b 0
