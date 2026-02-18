; OpenBoard Inno Setup Installer Script
; Creates a professional Windows installer for OpenBoard chess GUI

#define AppName "OpenBoard"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppPublisher "OpenBoard Project"
#define AppURL "https://github.com/openboard/openboard"
#define AppExeName "OpenBoard.exe"

[Setup]
; Application information
AppId={{B8F3C4E5-9A2D-4F1B-8C6E-7D3A5B9F2E1C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Installation directories
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Privileges and architecture
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Icons
SetupIconFile=..\..\..\assets\icons\openboard.ico

; Uninstaller
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

; Compression
Compression=lzma2/max
SolidCompression=yes

; Output configuration
OutputDir=..\..\dist\installers
OutputBaseFilename={#AppName}-v{#AppVersion}-windows-x64-setup

; License file
LicenseFile=..\..\..\LICENSE

; UI settings
DisableWelcomePage=no
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "pgnassociation"; Description: "Associate .PGN files with {#AppName}"; GroupDescription: "File Associations:"; Flags: unchecked

[Files]
Source: "..\..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.pgn"; ValueType: string; ValueName: ""; ValueData: "OpenBoardPGN"; Flags: uninsdeletevalue; Tasks: pgnassociation
Root: HKA; Subkey: "Software\Classes\OpenBoardPGN"; ValueType: string; ValueName: ""; ValueData: "OpenBoard Chess Game"; Flags: uninsdeletekey; Tasks: pgnassociation
Root: HKA; Subkey: "Software\Classes\OpenBoardPGN\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: pgnassociation
Root: HKA; Subkey: "Software\Classes\OpenBoardPGN\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: pgnassociation

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
