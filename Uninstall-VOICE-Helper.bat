@echo off
chcp 65001 >nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VOICE-Helper-Autostart.vbs" 2>nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /PID %%p /F >nul 2>nul
echo  [OK] VOICE Helper автоматаар асахаа болилоо.
pause
