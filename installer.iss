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
#define MyAppVersion "0.12.0-beta.1"
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
SetupIconFile=assets\rockforge.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; MIT licence shown before installing; LICENSE, THIRD_PARTY_NOTICES.md and
; LEGAL.md are also copied into {app} by build_exe.py (they are in dist\rockforge).
LicenseFile=LICENSE

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
portuguese.ComponentsGroup=Componentes extra:
english.ComponentsGroup=Extra components:
portuguese.ComponentsTask=Instalá-los no primeiro arranque: análise de áudio, deteção de tom e de letra, PDF e YouTube (descarrega cerca de 1 GB, ou 3 GB com GPU NVIDIA)
english.ComponentsTask=Install them on first start: audio analysis, tone and lyric detection, PDF and YouTube (downloads about 1 GB, or 3 GB with an NVIDIA GPU)

[Messages]
portuguese.FinishedLabel=O [name] foi instalado.%n%nPara o .psarc ter som no jogo é também preciso o Wwise, da Audiokinetic (gratuito, com conta). A licença não permite incluí-lo: instala o Wwise 2023.1 pelo Audiokinetic Launcher (o 2024/2025 não serve) — o RockForge encontra-o sozinho. Em Definições → Software vês o que falta.
english.FinishedLabel=[name] has been installed.%n%nFor the .psarc to have sound in game you also need Wwise, by Audiokinetic (free, with an account). Its licence does not allow bundling it: install Wwise 2023.1 with the Audiokinetic Launcher (2024/2025 will not do) — RockForge finds it by itself. Settings → Software shows what is missing.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "components"; Description: "{cm:ComponentsTask}"; GroupDescription: "{cm:ComponentsGroup}"

[Files]
Source: "dist\rockforge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[UninstallDelete]
; The extra components (a private Python with the ML packages, Deno) are
; downloaded by the app into the user's local app data — gigabytes that must
; not outlive the program. The user's projects (Downloads\RockForge) stay.
Type: filesandordirs; Name: "{localappdata}\RockForge\components"

[Run]
; With the «extra components» task the first start installs them by itself
; (start_standalone.components_flag → the Settings → Software page).
Filename: "{app}\{#MyAppExeName}"; Parameters: "--install-components"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent; Tasks: components
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent; Tasks: not components
