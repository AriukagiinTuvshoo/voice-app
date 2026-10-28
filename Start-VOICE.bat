@echo off
chcp 65001 >nul
title VOICE — Компьютерын Шууд Яриа Танигч
cd /d "%~dp0"

echo ============================================================
echo   🎤 VOICE — Компьютерын Local Яриа Танигч
echo   Дэлгэц дээр "VOICE FLOW" хөвөгч товч гарч ирнэ.
echo ============================================================
echo.

echo [1/3] Хиймэл оюуны санг шалгаж байна...
python -c "import uvicorn, fastapi, multipart" 2>nul
if %errorlevel% neq 0 (
    echo       Анхны удаа хэрэгцээт сангуудыг бэлдэж байна (түр хүлээнэ үү)...
    pip install -q -r requirements.txt
    pip install -q python-multipart uvicorn fastapi
)

echo [2/3] VOICE FLOW серверийг асааж байна...
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    if exist ".venv\Scripts\python.exe" (
        start "" /b ".venv\Scripts\python.exe" -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    ) else (
        start "" /b python -m uvicorn tts_server:app --host 127.0.0.1 --port 8000
    )
    timeout /t 3 /nobreak >nul
) else (
    echo       [OK] Сервер аль хэдийн ажиллаж байна.
)

echo.
echo ============================================================
echo   [АМЖИЛТТАЙ] VOICE FLOW дэлгэц дээр гарч ирлээ!
echo.
echo   - Дэлгэцийн баруун доод буланд байрлах "VOICE FLOW" 
echo     хөвөгч капсул дээр хулганаараа дарах эсвэл 
echo     гар дээрээ [Ctrl + Alt] (эсвэл F8) дараад ярина.
echo   - Таны ярьсан үг курсор байрлаж буй програм руу 
echo     (Facebook, Chrome, Word, Excel...) шууд бичигдэнэ!
echo ============================================================
echo.

rem Хэрэв вэб интерфэйс шаардлагатай бол
if exist "node_modules" (
    netstat -ano | findstr ":3000 " | findstr "LISTENING" >nul
    if %errorlevel% neq 0 (
        start "" /b cmd /c "npm run dev"
    )
)

timeout /t 5 >nul
exit /b 0
