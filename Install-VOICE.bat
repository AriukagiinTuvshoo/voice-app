@echo off
setlocal
title VOICE Installer
cd /d "%~dp0"

echo ============================================================
echo   VOICE - Speak. Clean. Write.   (Installer v1.2.0)
echo ============================================================
echo.

set "TARGET=%LOCALAPPDATA%\VOICE-App"

rem ---- 1. Find Python 3.10+ -------------------------------------------
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto have_python
python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto have_python

echo [!] Python 3.10 or newer was not found.
echo     Install it from https://www.python.org/downloads/
echo     (tick "Add python.exe to PATH" and keep "tcl/tk" selected),
echo     or run:  winget install Python.Python.3.12
echo     Then run Install-VOICE.bat again.
echo.
pause
exit /b 1

:have_python
echo [1/4] Python found: %PY%

rem ---- 2. Copy app files ------------------------------------------------
echo [2/4] Copying files to %TARGET% ...
if not exist "%TARGET%" mkdir "%TARGET%"
xcopy /E /I /Y /Q "%~dp0out" "%TARGET%\out" >nul
xcopy /E /I /Y /Q "%~dp0public" "%TARGET%\public" >nul
for %%F in (tts_server.py requirements.txt Start-VOICE.bat VOICE-Silent.vbs make-shortcut.ps1 README.md LICENSE) do (
    if exist "%~dp0%%F" copy /Y "%~dp0%%F" "%TARGET%\" >nul
)

rem ---- 3. Private virtual environment + dependencies ------------------------
echo [3/4] Installing Python packages (first time only, needs internet) ...
if not exist "%TARGET%\.venv\Scripts\pythonw.exe" (
    %PY% -m venv "%TARGET%\.venv"
    if errorlevel 1 goto fail
)
"%TARGET%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet --upgrade pip
"%TARGET%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%TARGET%\requirements.txt"
if errorlevel 1 goto fail

rem tkinter is needed for the floating FlowBar
"%TARGET%\.venv\Scripts\python.exe" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo [!] Python was installed without Tcl/Tk: the floating FlowBar will not appear.
    echo     Re-run the Python installer and keep "tcl/tk and IDLE" selected.
)

rem ---- 4. Desktop shortcut + start ------------------------------------------
echo [4/4] Creating Desktop shortcut ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%TARGET%\make-shortcut.ps1" -AppDir "%TARGET%"

echo.
echo Done! Starting VOICE ...
start "" wscript.exe "%TARGET%\VOICE-Silent.vbs"
timeout /t 3 /nobreak >nul
exit /b 0

:fail
echo.
echo [!] Installation failed. Check your internet connection and try again.
pause
exit /b 1
