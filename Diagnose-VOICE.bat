@echo off
setlocal
chcp 65001 >nul
title VOICE Diagnostic
set "TARGET=%LOCALAPPDATA%\VOICE-App"
if not exist "%TARGET%\.venv\Scripts\python.exe" (
    echo VOICE is not installed. Run Install-VOICE.bat first.
    pause
    exit /b 1
)
echo Running VOICE diagnostic ... a small test bar will appear for 6 seconds.
"%TARGET%\.venv\Scripts\python.exe" "%TARGET%\diagnose_flowbar.py" > "%TARGET%\voice-diagnose.txt" 2>&1
type "%TARGET%\voice-diagnose.txt"
echo.
echo Saved to: %TARGET%\voice-diagnose.txt
pause
