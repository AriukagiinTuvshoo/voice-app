@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PYW="
if exist "%~dp0runtime\pythonw.exe" (
    set "PYW=%~dp0runtime\pythonw.exe"
) else if exist "%~dp0.venv\Scripts\pythonw.exe" (
    set "PYW=%~dp0.venv\Scripts\pythonw.exe"
) else if exist "%LOCALAPPDATA%\Programs\VOICE\runtime\pythonw.exe" (
    set "PYW=%LOCALAPPDATA%\Programs\VOICE\runtime\pythonw.exe"
) else if exist "%LOCALAPPDATA%\Programs\VOICE\.venv\Scripts\pythonw.exe" (
    set "PYW=%LOCALAPPDATA%\Programs\VOICE\.venv\Scripts\pythonw.exe"
)
if "%PYW%"=="" goto not_installed

rem ---- Check if background daemon requested (autostart) ---
if "%~1"=="--background" (
    rem If server is already running, we do nothing and exit
    powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($h.status -eq 'ok') { exit 0 } } catch { }; exit 1" >nul 2>&1
    if not errorlevel 1 exit /b 0

    rem Start server with --background flag so it doesn't open browser
    set "VOICE_NO_BROWSER=1"
    start "" "%PYW%" "%~dp0tts_server.py" --background
    exit /b 0
)

rem ---- Is OUR server already running on port 8000? --------------------------------
powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($h.status -eq 'ok') { if ($h.desktop -like '*exebox*') { try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/quit' -Method Post -TimeoutSec 2 } catch { }; exit 1 } else { exit 0 } } } catch { }; exit 1"
if not errorlevel 1 (
    powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/flowbar/action' -Method Post -ContentType 'application/json' -Body '{\"action\":\"show\"}' -TimeoutSec 1 } catch { }" >nul 2>&1
    goto open_window
)

rem ---- Port 8000 used by some other program? ---------------------------------------
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 goto port_busy

rem ---- Start the engine (hidden). It also starts the floating FlowBar. -----------
set "VOICE_NO_BROWSER=1"
start "" "%PYW%" "%~dp0tts_server.py"

rem ---- Wait up to ~20 s until it answers ---------------------------------------------
set /a TRIES=0
:wait_loop
powershell -NoProfile -Command "try { $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2; if ($h.status -eq 'ok') { if ($h.desktop -like '*exebox*') { try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/quit' -Method Post -TimeoutSec 2 } catch { }; exit 1 } else { exit 0 } } } catch { }; exit 1"
if not errorlevel 1 goto open_window
set /a TRIES+=1
if %TRIES% GEQ 20 goto start_failed
ping 127.0.0.1 -n 2 >nul
goto wait_loop

:open_window
set "APP_URL=http://127.0.0.1:8000/dashboard"
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=%APP_URL% --window-size=1280,820
    exit /b 0
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=%APP_URL% --window-size=1280,820
    exit /b 0
)
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=%APP_URL% --window-size=1280,820
    exit /b 0
)
start "" "%APP_URL%"
exit /b 0

:not_installed
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show('VOICE is not installed yet. Run Install-VOICE.bat first.','VOICE')"
exit /b 1

:port_busy
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show('Port 8000 is used by another program. Close it and start VOICE again.','VOICE')"
exit /b 1

:start_failed
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show('VOICE engine did not start. See voice-server.log in the VOICE folder.','VOICE')"
exit /b 1
