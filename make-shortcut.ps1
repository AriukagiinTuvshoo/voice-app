param([string]$AppDir = $PSScriptRoot)

$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = $ws.CreateShortcut((Join-Path $desktop 'VOICE.lnk'))
$lnk.TargetPath = 'wscript.exe'
$lnk.Arguments = '"' + (Join-Path $AppDir 'VOICE-Silent.vbs') + '"'
$lnk.WorkingDirectory = $AppDir
$ico = Join-Path $AppDir 'public\voice.ico'
if (Test-Path $ico) { $lnk.IconLocation = $ico }
$lnk.Description = 'VOICE - Speak. Clean. Write.'
$lnk.Save()
Write-Host 'Desktop shortcut created.'
