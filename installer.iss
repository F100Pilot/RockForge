; Inno Setup script for RockForge installer.
;
; Prerequisites:
;   1. Build the standalone exe first:  py -3.11 build_exe.py
;   2. Install Inno Setup 6+:  https://jrsoftware.org/isinfo.php
;   3. Compile this script:    ISCC installer.iss
;      (or open it in the Inno Setup GUI and click Build > Compile)
;
; Output: Output/RockForge_Setup.exe

#define MyAppName "RockForge"
#define MyAppVersion "1.0"
#define MyAppPublisher "RockForge"
#define MyAppURL "https://github.com/F100Pilot/RockForge"
#define MyAppExeName "rockforge.exe"

[Setup]
AppId={{B7A1D3E5-4F2C-4A8B-9C6D-1E3F5A7B9D2C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=RockForge_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\rockforge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
