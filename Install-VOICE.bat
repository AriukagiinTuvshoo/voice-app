@echo off
setlocal
chcp 65001 >nul
title VOICE Installer
cd /d "%~dp0"

rem ---- 0. Unblock downloaded files (Windows Smart App Control MOTW) ---
powershell -NoProfile -Command "Get-ChildItem -Path '%~dp0*' -Recurse | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1

echo ============================================================
set "APP_VER=1.2.5"
if exist "%~dp0VERSION" set /p APP_VER=<"%~dp0VERSION"
echo   VOICE - Speak. Clean. Write.   (Installer v%APP_VER%)
echo ============================================================
echo.

set "TARGET=%LOCALAPPDATA%\VOICE-App"

if "%~1"=="--repair" (
    echo [*] Running in REPAIR mode: rebuilding virtual environment...
    if exist "%TARGET%\.venv" rd /s /q "%TARGET%\.venv" >nul 2>&1
)
if "%~1"=="repair" (
    echo [*] Running in REPAIR mode: rebuilding virtual environment...
    if exist "%TARGET%\.venv" rd /s /q "%TARGET%\.venv" >nul 2>&1
)

rem ---- 1. Find Python 3.10+ -------------------------------------------
set "PY="

rem Check py -3 launcher
py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
    goto have_python
)

rem Check python command in PATH
python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY=python"
    goto have_python
)

rem Check python3 command in PATH
python3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PY=python3"
    goto have_python
)

rem Check WindowsApps Microsoft Store Python
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" (
    "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PY=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
        goto have_python
    )
)

echo [!] Python 3.10 or newer was not detected.
echo [*] Attempting automatic install via Windows Package Manager (winget)...
winget --version >nul 2>&1
if not errorlevel 1 (
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    rem Re-check after winget install
    py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -3"
        goto have_python
    )
    python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PY=python"
        goto have_python
    )
)

echo.
echo [!] Python 3.10+ installation is required to run VOICE.
echo     Please download and install Python from:
echo     https://www.python.org/downloads/
echo.
echo     IMPORTANT: During Python setup, make sure to check:
echo       1. [x] Add python.exe to PATH
echo       2. [x] tcl/tk and IDLE (required for floating FlowBar)
echo.
echo     After installing Python, run Install-VOICE.bat again.
echo.
pause
exit /b 1

:have_python
echo [1/4] Python found: %PY%

rem ---- 1b. Stop an older VOICE engine so the NEW code is the one that runs ------
echo [*] Stopping any running VOICE engine ...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/quit' -Method Post -TimeoutSec 2 } catch { }" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*VOICE-App*tts_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
ping 127.0.0.1 -n 3 >nul

rem ---- 2. Copy app files ------------------------------------------------
echo [2/4] Copying files to %TARGET% ...
if not exist "%TARGET%" mkdir "%TARGET%"
if exist "%~dp0out" xcopy /E /I /Y /Q "%~dp0out" "%TARGET%\out" >nul
if exist "%~dp0public" xcopy /E /I /Y /Q "%~dp0public" "%TARGET%\public" >nul
for %%F in (tts_server.py voice_core.py requirements.txt requirements-tray.txt requirements-offline.txt VERSION Start-VOICE.bat Uninstall-VOICE.bat make-shortcut.ps1 README.md LICENSE Diagnose-VOICE.bat diagnose_flowbar.py) do (
    if exist "%~dp0%%F" copy /Y "%~dp0%%F" "%TARGET%\" >nul
)

rem Clean up any blocked legacy files if present
if exist "%TARGET%\VOICE-Silent.vbs" del /f /q "%TARGET%\VOICE-Silent.vbs" >nul 2>&1
if exist "%TARGET%\VOICE.exe" del /f /q "%TARGET%\VOICE.exe" >nul 2>&1
powershell -NoProfile -Command "Get-ChildItem -Path '%TARGET%\*' -Recurse | Unblock-File -ErrorAction SilentlyContinue" >nul 2>&1

rem ---- 3. Private virtual environment + dependencies ------------------------
echo [3/4] Setting up private Python environment (first time only) ...
if not exist "%TARGET%\.venv\Scripts\pythonw.exe" (
    %PY% -m venv "%TARGET%\.venv"
    if errorlevel 1 goto fail
)
"%TARGET%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet --upgrade pip
if errorlevel 1 echo [!] pip upgrade skipped ^(not fatal^).
"%TARGET%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%TARGET%\requirements.txt"
if errorlevel 1 goto fail

rem Verify tkinter is available for floating FlowBar
"%TARGET%\.venv\Scripts\python.exe" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] WARNING: Python was installed without Tcl/Tk.
    echo     The floating FlowBar will not appear until Python is reinstalled
    echo     with "tcl/tk and IDLE" checked.
    echo.
)

rem ---- 4. Desktop shortcut + start ------------------------------------------
echo [4/4] Creating Desktop shortcut ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%TARGET%\make-shortcut.ps1" -AppDir "%TARGET%"

echo.
echo ============================================================
echo   Installation complete! Starting VOICE ...
echo ============================================================
echo.
start "" "%TARGET%\Start-VOICE.bat"
exit /b 0

:fail
echo.
echo [!] Installation failed. Check your internet connection and try again.
pause
exit /b 1
