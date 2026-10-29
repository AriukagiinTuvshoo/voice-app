@echo off
chcp 65001 >nul
title VOICE Desktop Installer
cd /d "%~dp0"

echo ========================================================
echo   VOICE - Speak. Clean. Write. (v1.2.0 Суулгагч)
echo ========================================================
echo.

set "TARGET_DIR=%LOCALAPPDATA%\VOICE-App"
echo [1/3] Файлуудыг хуулж байна: %TARGET_DIR%...
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
xcopy /E /I /Y /Q "%~dp0*" "%TARGET_DIR%\" >nul 2>&1

:: Remove broken legacy VOICE.exe if present
if exist "%TARGET_DIR%\VOICE.exe" del /f /q "%TARGET_DIR%\VOICE.exe" >nul 2>&1

echo [2/3] Windows хамгаалалтыг зөвшөөрч (Unblock), Desktop товчлол үүсгэж байна...
powershell -NoProfile -Command ^
  "Get-ChildItem -Path '%TARGET_DIR%' -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue; " ^
  "$WshShell = New-Object -ComObject WScript.Shell; " ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
  "$shortcut = $WshShell.CreateShortcut(\"$desktop\VOICE.lnk\"); " ^
  "$shortcut.TargetPath = 'wscript.exe'; " ^
  "$shortcut.Arguments = \"\"\"%TARGET_DIR%\VOICE-Silent.vbs\"\"\"; " ^
  "$shortcut.WorkingDirectory = '%TARGET_DIR%'; " ^
  "$ico = '%TARGET_DIR%\public\voice.ico'; " ^
  "if (Test-Path $ico) { $shortcut.IconLocation = $ico; } " ^
  "$shortcut.Description = 'VOICE — Speak. Clean. Write.'; " ^
  "$shortcut.Save()"

echo [3/3] VOICE программыг эхлүүлж байна...
start "" wscript.exe "%TARGET_DIR%\VOICE-Silent.vbs"

echo.
echo Амжилттай суулгаж дууслаа! Таны Desktop дээр VOICE товчлол үүссэн.
timeout /t 2 /nobreak >nul
exit /b 0
