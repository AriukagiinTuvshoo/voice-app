@echo off
chcp 65001 >nul
title VOICE Desktop Launcher
cd /d "%~dp0"

echo =======================================================
echo   VOICE - Speak. Clean. Write. (v1.2.0)
echo   Монгол, Англи, Япон яриа таних ба Windows шууд бичигч
echo =======================================================
echo.

:: 1. Windows Smart App Control unblock
powershell -NoProfile -Command "Get-ChildItem -Path '%~dp0' -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1

:: 2. Check and start VOICE Node.js Desktop Engine on Port 8000
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo [1/2] VOICE Engine сервер эхлүүлж байна (Port 8000)...
    start /b "" node "%~dp0server.cjs" 8000
    timeout /t 1 /nobreak >nul
) else (
    echo [1/2] VOICE Engine сервер аль хэдийн ажиллаж байна.
)

:: 3. Launch App Window in Microsoft Edge / Chrome App Mode (1-second instant start)
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

:: Fallback to default browser
start "" "%APP_URL%"
exit /b 0
