param([string]$AppDir = $PSScriptRoot)

$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = $ws.CreateShortcut((Join-Path $desktop 'VOICE.lnk'))

$pyw = Join-Path $AppDir '.venv\Scripts\pythonw.exe'
if (Test-Path $pyw) {
    $lnk.TargetPath = $pyw
    $lnk.Arguments = 'tts_server.py'
} else {
    $lnk.TargetPath = Join-Path $AppDir 'Start-VOICE.bat'
    $lnk.WindowStyle = 7
}

$lnk.WorkingDirectory = $AppDir
$ico = Join-Path $AppDir 'public\voice.ico'
if (Test-Path $ico) { $lnk.IconLocation = $ico }
$lnk.Description = 'VOICE - Speak. Clean. Write.'
$lnk.Save()
Write-Host 'Desktop shortcut created.'
