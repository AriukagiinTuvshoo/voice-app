@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title VOICE Uninstaller

echo ============================================================
echo   VOICE - Speak. Clean. Write.   (Uninstaller)
echo ============================================================
echo.

set "TARGET=%LOCALAPPDATA%\Programs\VOICE"
set "LEGACY_TARGET=%LOCALAPPDATA%\VOICE-App"
set "USER_DATA=%APPDATA%\VOICE"

echo This will uninstall the VOICE application files from:
echo   %TARGET%
echo.
echo NOTE: Your personal settings and voice clone profiles in:
echo   %USER_DATA%
echo will be SAFELY PRESERVED by default.
echo.

if not "%~1"=="--silent" (
    set /p "CONFIRM=Type YES to proceed with uninstall: "
    if /i not "!CONFIRM!"=="YES" (
        echo Cancelled.
        pause
        exit /b 0
    )
)
echo.

echo [1/4] Stopping running VOICE background engine...
powershell -NoProfile -Command "$sf = Join-Path $env:APPDATA 'VOICE\session.json'; $tk = if (Test-Path $sf) { try { (Get-Content $sf | ConvertFrom-Json).token } catch { '' } } else { '' }; $qh = if ($tk) { @{ 'X-Session-Token' = $tk } } else { @{} }; try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/quit' -Method Post -Headers $qh -TimeoutSec 2 } catch { }" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*VOICE*tts_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [2/4] Removing Desktop and Start Menu shortcuts...
powershell -NoProfile -Command "try { $d = [Environment]::GetFolderPath('Desktop'); if ($d) { Remove-Item -Path (Join-Path $d 'VOICE.lnk') -Force -ErrorAction SilentlyContinue } } catch { }" >nul 2>&1
powershell -NoProfile -Command "try { $p = [Environment]::GetFolderPath('Programs'); if ($p) { Remove-Item -Path (Join-Path $p 'VOICE.lnk') -Force -ErrorAction SilentlyContinue } } catch { }" >nul 2>&1
if exist "%USERPROFILE%\Desktop\VOICE.lnk" del /f /q "%USERPROFILE%\Desktop\VOICE.lnk" >nul 2>&1
if exist "%USERPROFILE%\OneDrive\Desktop\VOICE.lnk" del /f /q "%USERPROFILE%\OneDrive\Desktop\VOICE.lnk" >nul 2>&1
if exist "%PUBLIC%\Desktop\VOICE.lnk" del /f /q "%PUBLIC%\Desktop\VOICE.lnk" >nul 2>&1

echo [3/4] Removing Autostart registry key...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "VOICE" /f >nul 2>&1

echo [4/4] Preserving legacy user settings and removing application binaries...
rem If not running --purge, migrate any remaining legacy user settings and voice clones to %APPDATA%\VOICE
if not "%~1"=="--purge" (
    if not exist "%USER_DATA%" mkdir "%USER_DATA%" >nul 2>&1
    if exist "%LEGACY_TARGET%\voice_settings.json" (
        if not exist "%USER_DATA%\voice_settings.json" (
            copy /Y "%LEGACY_TARGET%\voice_settings.json" "%USER_DATA%\" >nul 2>&1
        )
    )
    if exist "%LEGACY_TARGET%\clones" (
        if not exist "%USER_DATA%\clones" (
            xcopy /E /I /Y /Q "%LEGACY_TARGET%\clones" "%USER_DATA%\clones" >nul 2>&1
        )
    )
)

if exist "%TARGET%" rmdir /s /q "%TARGET%" >nul 2>&1
if exist "%LEGACY_TARGET%" rmdir /s /q "%LEGACY_TARGET%" >nul 2>&1

if "%~1"=="--purge" (
    echo [*] Purging personal user data as requested...
    if exist "%USER_DATA%" rmdir /s /q "%USER_DATA%" >nul 2>&1
)

echo.
echo ============================================================
echo   VOICE application has been successfully uninstalled.
if not "%~1"=="--purge" (
    echo   Your settings and voice clones were preserved in:
    echo     %USER_DATA%
)
echo ============================================================
echo.
if not "%~1"=="--silent" pause
exit /b 0
