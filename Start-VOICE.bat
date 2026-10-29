@echo off
setlocal
cd /d "%~dp0"

set "PYW=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYW%" goto not_installed

rem ---- Is OUR server already running on port 8000? --------------------------------
powershell -NoProfile -Command "try { if ((Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2).voice_cloning) { exit 0 } } catch { }; exit 1"
if not errorlevel 1 goto open_window

rem ---- Port 8000 used by some other program? ---------------------------------------
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 goto port_busy

rem ---- Start the engine (hidden). It also starts the floating FlowBar. -----------
start "" "%PYW%" "%~dp0tts_server.py"

rem ---- Wait up to ~20 s until it answers ---------------------------------------------
set /a TRIES=0
:wait_loop
powershell -NoProfile -Command "try { if ((Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2).voice_cloning) { exit 0 } } catch { }; exit 1"
if not errorlevel 1 goto open_window
set /a TRIES+=1
if %TRIES% GEQ 20 goto start_failed
timeout /t 1 /nobreak >nul
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
