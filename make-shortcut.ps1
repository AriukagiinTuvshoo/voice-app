param([string]$AppDir = "$env:LOCALAPPDATA\VOICE-App")

$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop 'VOICE.lnk'
$lnk = $ws.CreateShortcut($lnkPath)

$startBat = Join-Path $AppDir 'Start-VOICE.bat'
$lnk.TargetPath = $startBat
$lnk.WorkingDirectory = $AppDir
$lnk.WindowStyle = 7

$ico = Join-Path $AppDir 'public\voice.ico'
if (Test-Path $ico) {
    $lnk.IconLocation = $ico
}
$lnk.Description = 'VOICE - Speak. Clean. Write.'
$lnk.Save()

Write-Host "Desktop shortcut created: $lnkPath"
