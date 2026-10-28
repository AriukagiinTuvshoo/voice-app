@echo off
chcp 65001 >nul
title VOICE — Системээс устгах
cd /d "%~dp0"

del /f /q "%USERPROFILE%\Desktop\VOICE - Шууд Ярьж Бичих.lnk" 2>nul
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VOICE-Autostart.vbs" 2>nul
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VOICE-Helper-Autostart.vbs" 2>nul
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VOICE-Local-Helper.vbs" 2>nul

echo [OK] Дэлгэцийн товчлол болон автомат асах тохиргоог устгалаа.
pause
