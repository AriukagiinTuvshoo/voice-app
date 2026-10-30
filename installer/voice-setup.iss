; Inno Setup Script for VOICE Desktop
; Stage 5 Production Installer

#define MyAppName "VOICE"
#define MyAppVersion "1.4.3"
#define MyAppPublisher "AriukagiinTuvshoo"
#define MyAppURL "https://github.com/AriukagiinTuvshoo/voice-app"
#define MyAppExeName "Start-VOICE.bat"

[Setup]
AppId={{5A0E1A8B-2D53-4889-BAE8-9F9589CE0F64}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\VOICE
DisableProgramGroupPage=yes
OutputBaseFilename=VOICE-Setup-v{#MyAppVersion}
OutputDir=..\dist
SetupIconFile=..\public\voice.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\public\voice.ico
UninstallDisplayName={#MyAppName} Speech & Dictation Suite

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Start VOICE automatically on Windows startup (Background mode)"; GroupDescription: "System Integration"; Flags: unchecked

[Files]
; Next.js static build export
Source: "..\out\*"; DestDir: "{app}\out"; Flags: ignoreversion recursesubdirs createallsubdirs
; Static assets
Source: "..\public\*"; DestDir: "{app}\public"; Flags: ignoreversion recursesubdirs createallsubdirs
; Native AI audio binaries (FFmpeg with libass, whisper.cpp)
Source: "..\tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; Standalone embedded Python runtime (optional)
Source: "..\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; Application Core & Modules
Source: "..\tts_server.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\voice_core.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\mongolian_grammar.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\voice_cloning.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\audio_separator.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\karaoke_ass.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\auto_updater.py"; DestDir: "{app}"; Flags: ignoreversion
; Scripts & config
Source: "..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements-tray.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements-offline.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\VERSION"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Start-VOICE.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Install-VOICE.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Uninstall-VOICE.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Diagnose-VOICE.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\make-shortcut.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\public\voice.ico"; Comment: "VOICE Speech, VoiceStudio & Dictation Suite"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\public\voice.ico"; Comment: "VOICE Speech, VoiceStudio & Dictation Suite"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VOICE"; ValueData: """{app}\Start-VOICE.bat"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; First-time environment setup: installs private Python venv and requirements
Filename: "{app}\Install-VOICE.bat"; StatusMsg: "Configuring VOICE private Python environment and AI modules..."; Flags: runhidden
; Launch application after setup
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    UserDataDir := ExpandConstant('{userappdata}\VOICE');
    // User data in %APPDATA%\VOICE is preserved by default to protect custom clones, history & settings.
    if DirExists(UserDataDir) then
    begin
      if MsgBox('Do you want to delete your custom voice clones, settings, and audio history located in ' + UserDataDir + '?' + #13#10 + '(Selecting No will preserve your data for future installs)', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(UserDataDir, True, True, True);
      end;
    end;
  end;
end;
