#define MyAppName "TikTok Auto Publisher"
#define MyAppVersion "1.0.0"
#define MyAppExeName "TikTokAutoPublisher.exe"
[Setup]
AppId={{5D736B72-DC4A-4D48-8A5B-5F1D4B11B73C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\TikTok Auto Publisher
DefaultGroupName={#MyAppName}
OutputDir=..\release
OutputBaseFilename=TikTokAutoPublisher-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
MinVersion=10.0
[Tasks]
Name: "desktopicon"; Description: "Create Desktop Shortcut"; Flags: checkedonce
[Files]
Source: "..\dist\TikTokAutoPublisher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
