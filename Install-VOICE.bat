@echo off
cd /d "%~dp0"
title VOICE - Desktop Installer

echo ============================================================
echo   VOICE - Desktop Shortcut and Autostart Setup
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo 1. Creating Desktop shortcut...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\VOICE.lnk'); $s.TargetPath = '%SCRIPT_DIR%Start-VOICE.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.WindowStyle = 1; $s.Description = 'VOICE Voice Dictation'; $s.Save()"

echo 2. Setting up autostart...
> "%STARTUP%\VOICE-Autostart.vbs" (
    echo Set s = CreateObject^("WScript.Shell"^)
    echo s.Run chr^(34^) ^& "%SCRIPT_DIR%Start-VOICE.bat" ^& chr^(34^), 0, False
)

echo.
echo ============================================================
echo   [SUCCESS] VOICE installed successfully!
echo   
echo   - Desktop shortcut 'VOICE' created on your desktop.
echo   - Double-click 'VOICE' anytime to start the floating pill!
echo ============================================================
echo.
pause
