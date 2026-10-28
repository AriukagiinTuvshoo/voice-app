@echo off
chcp 65001 >nul
title VOICE — Суулгагч (Desktop Shortcut & Autostart)
cd /d "%~dp0"

echo ============================================================
echo   🎤 VOICE — Компьютерт суулгах (Desktop Shortcut)
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo 1. Компьютерын дэлгэц (Desktop) дээр товчлол үүсгэж байна...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\VOICE - Шууд Ярьж Бичих.lnk'); $s.TargetPath = '%SCRIPT_DIR%Start-VOICE.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.WindowStyle = 1; $s.Description = 'VOICE — Шууд ярьж бичих систем'; $s.Save()"

echo 2. Windows асах бүрт цаанаа автоматаар ажиллахаар тохируулж байна...
> "%STARTUP%\VOICE-Autostart.vbs" (
    echo Set s = CreateObject^("WScript.Shell"^)
    echo s.Run chr^(34^) ^& "%SCRIPT_DIR%Start-VOICE.bat" ^& chr^(34^), 0, False
)

echo.
echo ============================================================
echo   [АМЖИЛТТАЙ] VOICE амжилттай суулаа!
echo   
echo   - Таны дэлгэц (Desktop) дээр "VOICE - Шууд Ярьж Бичих"
echo     товчлол үүсгэгдлээ.
echo   - Windows асах бүрт "VOICE FLOW" хөвөгч товч автоматаар
echo     дэлгэц дээр бэлэн байна.
echo ============================================================
echo.
pause
