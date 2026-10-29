@echo off
setlocal
chcp 65001 >nul
title VOICE Uninstaller

echo ============================================================
echo   VOICE - Speak. Clean. Write.   (Uninstaller)
echo ============================================================
echo.

set "TARGET=%LOCALAPPDATA%\VOICE-App"

echo [1/3] Stopping running VOICE background engine...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/quit' -Method Post -TimeoutSec 2 } catch { }" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'tts_server.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [2/3] Removing Desktop shortcuts...
powershell -NoProfile -Command "try { $d = [Environment]::GetFolderPath('Desktop'); if ($d) { Remove-Item -Path (Join-Path $d 'VOICE.lnk') -Force -ErrorAction SilentlyContinue } } catch { }" >nul 2>&1
if exist "%USERPROFILE%\Desktop\VOICE.lnk" del /f /q "%USERPROFILE%\Desktop\VOICE.lnk" >nul 2>&1
if exist "%USERPROFILE%\OneDrive\Desktop\VOICE.lnk" del /f /q "%USERPROFILE%\OneDrive\Desktop\VOICE.lnk" >nul 2>&1
if exist "%PUBLIC%\Desktop\VOICE.lnk" del /f /q "%PUBLIC%\Desktop\VOICE.lnk" >nul 2>&1

echo [3/3] Removing app directory (%TARGET%)...
if exist "%TARGET%" (
    rmdir /s /q "%TARGET%" >nul 2>&1
)

echo.
echo ============================================================
echo   VOICE has been completely removed from your computer.
echo ============================================================
echo.
pause
exit /b 0
