; Inno Setup script — VetoPrix
; Ouvrir avec Inno Setup Compiler sur Windows après un build PyInstaller.
; Doc : https://jrsoftware.org/ishelp/

#define MyAppName "VetoPrix"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "VetoPrix"
#define MyAppURL "https://github.com/GGNatio/VetoPrix"
#define MyAppExeName "VetoPrix.exe"

[Setup]
AppId={{B7E2C4A1-9F3D-4E8A-A1C2-VETOPRIX0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=VetoPrixSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un icône sur le Bureau"; GroupDescription: "Icônes supplémentaires:"; Flags: unchecked

[Files]
; Après PyInstaller : dossier dist\VetoPrix\
Source: "..\dist\VetoPrix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer VetoPrix"; Flags: nowait postinstall skipifsilent
