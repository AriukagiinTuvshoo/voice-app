@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title VOICE Diagnostic

echo ========================================================
echo             VOICE System Diagnostic Utility
echo ========================================================
echo.

rem Determine installation directory:
rem 1. Local workspace / portable directory if tts_server.py exists next to batch
rem 2. Installed directory %LOCALAPPDATA%\Programs\VOICE
rem 3. Legacy directory %LOCALAPPDATA%\VOICE-App

set "APP_DIR="
if exist "%~dp0tts_server.py" (
    set "APP_DIR=%~dp0"
) else if exist "%LOCALAPPDATA%\Programs\VOICE\tts_server.py" (
    set "APP_DIR=%LOCALAPPDATA%\Programs\VOICE"
) else if exist "%LOCALAPPDATA%\VOICE-App\tts_server.py" (
    set "APP_DIR=%LOCALAPPDATA%\VOICE-App"
)

if "%APP_DIR%"=="" (
    echo [!] VOICE installation was not found.
    echo Please run Install-VOICE.bat or run the installer first.
    echo.
    pause
    exit /b 1
)

rem Locate Python executable:
rem 1. Bundled standalone runtime: runtime\python.exe
rem 2. Virtual environment: .venv\Scripts\python.exe
rem 3. System python: python.exe
set "PY_EXE="
if exist "%APP_DIR%\runtime\python.exe" (
    set "PY_EXE=%APP_DIR%\runtime\python.exe"
) else if exist "%APP_DIR%\.venv\Scripts\python.exe" (
    set "PY_EXE=%APP_DIR%\.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    echo [!] Python executable not found in:
    echo     - %APP_DIR%\runtime\python.exe
    echo     - %APP_DIR%\.venv\Scripts\python.exe
    echo     - System PATH
    echo Please run Install-VOICE.bat to setup the Python environment.
    echo.
    pause
    exit /b 1
)

set "USER_DATA=%APPDATA%\VOICE"
if not exist "%USER_DATA%" mkdir "%USER_DATA%" >nul 2>&1
set "DIAG_OUT=%USER_DATA%\voice-diagnose.txt"

echo Located VOICE at: %APP_DIR%
echo Using Python at : %PY_EXE%
echo.
echo Running diagnostic suite (visual FlowBar test will appear briefly)...
echo.

if exist "%APP_DIR%\diagnose_flowbar.py" (
    "%PY_EXE%" "%APP_DIR%\diagnose_flowbar.py" --output "%DIAG_OUT%"
) else (
    "%PY_EXE%" "%APP_DIR%\tts_server.py" --diagnose --output "%DIAG_OUT%"
)

echo.
echo ========================================================
echo Diagnostic complete. Report saved to:
echo %DIAG_OUT%
echo ========================================================
echo.
pause
