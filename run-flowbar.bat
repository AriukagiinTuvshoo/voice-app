@echo off
chcp 65001 >nul
title VOICE FlowBar Widget
cd /d "%~dp0"

:: 1. Ensure server is active on Port 8000
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    start /b "" node "%~dp0server.cjs" 8000
    timeout /t 1 /nobreak >nul
)

:: 2. Launch FlowBar in minimal App Mode
set "FLOWBAR_URL=http://127.0.0.1:8000/flowbar"

if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=%FLOWBAR_URL% --window-size=320,62
    exit /b 0
)

if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=%FLOWBAR_URL% --window-size=320,62
    exit /b 0
)

start "" "%FLOWBAR_URL%"
exit /b 0
