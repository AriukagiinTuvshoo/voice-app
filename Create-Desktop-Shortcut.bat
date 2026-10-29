@echo off
chcp 65001 >nul
title Desktop Shortcut Creator
cd /d "%~dp0"

echo [1/1] Desktop дээр VOICE shortcut үүсгэж байна...

powershell -NoProfile -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell; " ^
  "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
  "$shortcut = $WshShell.CreateShortcut(\"$desktop\VOICE.lnk\"); " ^
  "$shortcut.TargetPath = 'wscript.exe'; " ^
  "$shortcut.Arguments = \"\"\"%~dp0VOICE-Silent.vbs\"\"\"; " ^
  "$shortcut.WorkingDirectory = '%~dp0'; " ^
  "$ico = '%~dp0public\voice.ico'; " ^
  "if (Test-Path $ico) { $shortcut.IconLocation = $ico; } " ^
  "$shortcut.Description = 'VOICE — Speak. Clean. Write.'; " ^
  "$shortcut.Save()"

echo.
echo Амжилттай! Таны Desktop (дэлгэц) дээр 'VOICE' товчлол үүслээ.
echo Одоо desktop дээрх VOICE дээр давхар товшоод шууд ашиглах боломжтой.
echo.
pause
