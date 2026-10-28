@echo off
chcp 65001 >nul
title VOICE — Компьютерын Шууд Яриа Танигч
cd /d "%~dp0"

echo ============================================================
echo   🎤 VOICE — Компьютерын Local Яриа Танигч & VoiceStudio
echo   Дэлгэц дээр VOICE FLOW хөвөгч товч автоматаар гарч ирнэ.
echo ============================================================
echo.

echo [1/3] Хиймэл оюуны серверийг шалгаж байна (Port 8000)...
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo       AI Серверийг асааж байна...
    if exist ".venv\Scripts\python.exe" (
        start "" /b ".venv\Scripts\python.exe" -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    ) else (
        start "" /b python -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    )
    timeout /t 3 /nobreak >nul
) else (
    echo       [OK] AI Сервер аль хэдийн ажиллаж байна.
)

echo [2/3] Вэб интерфэйсийг шалгаж байна (Port 3000)...
netstat -ano | findstr ":3000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo       Вэб серверийг асааж байна...
    start "" /b cmd /c "npm run dev"
    timeout /t 4 /nobreak >nul
) else (
    echo       [OK] Вэб сервер аль хэдийн ажиллаж байна.
)

echo.
echo ============================================================
echo   [АМЖИЛТТАЙ] VOICE FLOW дэлгэц дээр бэлэн боллоо!
echo   
echo   - Дэлгэцийн доод хэсэгт байрлах "VOICE FLOW" хөвөгч товч 
echo     дээр хулганаараа дарах эсвэл гар дээрээ [Ctrl+Alt] / [F8] 
echo     дараад ярихад ямар ч програм руу шууд бичигдэнэ!
echo ============================================================
echo.

echo [3/3] VoiceStudio хянах цонхыг нээж байна...
where msedge >nul 2>nul
if %errorlevel% equ 0 (
    start "" msedge --app=http://localhost:3000 --window-size=1280,820
    exit /b 0
)

where chrome >nul 2>nul
if %errorlevel% equ 0 (
    start "" chrome --app=http://localhost:3000 --window-size=1280,820
    exit /b 0
)

start "" "http://localhost:3000"
exit /b 0
