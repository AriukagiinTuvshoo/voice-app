<# :
@echo off
chcp 65001 >nul
title VOICE Windows Local Helper
cd /d "%~dp0"

echo ============================================================
echo   🎤 VOICE Windows Global Dictation Helper (Local)
echo   Word, Excel, Chrome, Facebook дээр F8 / Ctrl+Alt дарж шууд бичих
echo ============================================================
echo.

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

> "%STARTUP%\VOICE-Local-Helper.vbs" (
    echo Set s = CreateObject^("WScript.Shell"^)
    echo s.Run "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -Command ""Invoke-Expression ([System.IO.File]::ReadAllText('%~f0'))""", 0, False
)

start "" /b powershell -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Invoke-Expression ([System.IO.File]::ReadAllText('%~f0'))"

echo  [АМЖИЛТТАЙ] VOICE Local Helper далд аслаа!
echo.
echo  Одоо Chrome, Word, Facebook, Excel дээр курсороо тавиад:
echo  1. Гар дээрээ F8 (эсвэл Ctrl + Alt) дараад ярина.
echo  2. Дахин товчоо дарахад ярьсан үг тань курсор дээр автоматаар бичигдэнэ!
echo.
echo  (Windows асах бүрт цаанаа автоматаар ажиллахаар тохируулагдлаа)
timeout /t 5
exit /b 0
#>

Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;

public class WinAPI {
    [DllImport("user32.dll")]
    public static extern short GetAsyncKeyState(int vKey);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

Add-Type @"
using System;
using System.Runtime.InteropServices;

public class SoundRecorder {
    [DllImport("winmm.dll", EntryPoint = "mciSendStringA", CharSet = CharSet.Ansi, SetLastError = true, ExactSpelling = true)]
    public static extern int mciSendString(string lpstrCommand, string lpstrReturnString, int uReturnLength, int hwndCallback);

    public static void StartRecording() {
        mciSendString("close recsound", null, 0, 0);
        mciSendString("open new type waveaudio alias recsound", null, 0, 0);
        mciSendString("set recsound bitspersample 16 channels 1 samplespersec 16000", null, 0, 0);
        mciSendString("record recsound", null, 0, 0);
    }

    public static void SaveRecording(string filePath) {
        mciSendString("stop recsound", null, 0, 0);
        mciSendString("save recsound " + filePath, null, 0, 0);
        mciSendString("close recsound", null, 0, 0);
    }
}
"@

$SERVER_URL = "http://localhost:3000"
$LOCAL_BACKEND = "http://127.0.0.1:8000"
$VK_CONTROL = 0x11
$VK_MENU = 0x12
$VK_F8 = 0x77

$isRecording = $false
$targetHwnd = [IntPtr]::Zero
$tempWav = "$env:TEMP\voice_dictation.wav"
$wasDown = $false

while ($true) {
    Start-Sleep -Milliseconds 40

    $ctrl = ([WinAPI]::GetAsyncKeyState($VK_CONTROL) -band 0x8000) -ne 0
    $alt  = ([WinAPI]::GetAsyncKeyState($VK_MENU) -band 0x8000) -ne 0
    $f8   = ([WinAPI]::GetAsyncKeyState($VK_F8) -band 0x8000) -ne 0

    $isHotkeyDown = ($ctrl -and $alt) -or $f8

    if ($isHotkeyDown -and -not $wasDown) {
        $wasDown = $true
        if (-not $isRecording) {
            $isRecording = $true
            $targetHwnd = [WinAPI]::GetForegroundWindow()
            [SoundRecorder]::StartRecording()
        } else {
            $isRecording = $false
            [SoundRecorder]::SaveRecording($tempWav)

            if (Test-Path $tempWav) {
                $text = ""
                try {
                    $form = @{
                        audio = Get-Item $tempWav
                        language = "mn"
                    }
                    $response = Invoke-RestMethod -Uri "$SERVER_URL/api/chimege/transcribe" -Method Post -Form $form -TimeoutSec 15
                    $text = $response.text
                } catch {
                    try {
                        $form = @{
                            audio = Get-Item $tempWav
                            language = "mn"
                        }
                        $pyRes = Invoke-RestMethod -Uri "$LOCAL_BACKEND/transcribe" -Method Post -Form $form -TimeoutSec 15
                        $text = $pyRes.text
                    } catch {}
                }

                if ($text) {
                    if ($targetHwnd -ne [IntPtr]::Zero) {
                        [WinAPI]::SetForegroundWindow($targetHwnd)
                        Start-Sleep -Milliseconds 60
                    }
                    [System.Windows.Forms.SendKeys]::SendWait($text + " ")
                }
                Remove-Item $tempWav -Force -ErrorAction SilentlyContinue
            }
        }
    } elseif (-not $isHotkeyDown -and $wasDown) {
        $wasDown = $false
    }
}
