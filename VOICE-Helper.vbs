' VOICE Desktop Helper - runs silently in the background (no console window).
' Press Ctrl+Alt (or F8) in ANY app (Chrome, Word, Facebook, Telegram...) and speak:
' the recognized text is typed directly at your cursor.
Set WshShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath
WshShell.Run chr(34) & strPath & "\run-helper.bat" & chr(34), 0, False
Set WshShell = Nothing
