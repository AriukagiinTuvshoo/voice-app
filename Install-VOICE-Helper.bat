@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

> "%STARTUP%\VOICE-Helper-Autostart.vbs" (
    echo Set s = CreateObject^("WScript.Shell"^)
    echo s.Run chr^(34^) ^& "%~dp0VOICE-Helper.vbs" ^& chr^(34^), 0, False
)

wscript "%~dp0VOICE-Helper.vbs"

echo.
echo  [OK] VOICE Helper суулгалаа. Windows асах бүрт автоматаар ажиллана.
echo       Chrome, Word, Facebook дээр курсороо байрлуулаад Ctrl+Alt (эсвэл F8) дарж ярина уу.
echo.
echo  Устгах бол: Uninstall-VOICE-Helper.bat
pause
