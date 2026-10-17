; LocalCast by Fagner Lemes. User data deliberately lives outside {app}.
#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif
#ifndef AppIdentity
  #define AppIdentity "{{345B76EF-5AD8-4DC5-9611-190A20447DB8}"
#endif
#ifndef AppMutexName
  #define AppMutexName "LocalCast.FagnerLemes.Desktop"
#endif
#ifndef SourceRoot
  #define SourceRoot "..\dist\LocalCast"
#endif
[Setup]
AppId={#AppIdentity}
AppName=LocalCast
AppVersion={#AppVersion}
AppVerName=LocalCast {#AppVersion}
AppPublisher=By Fagner Lemes
AppPublisherURL=https://github.com/fagnerlemes/LocalCast
DefaultDirName={localappdata}\Programs\LocalCast
DefaultGroupName=LocalCast
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=LocalCast-Setup-{#AppVersion}
SetupIconFile=..\assets\localcast.ico
UninstallDisplayIcon={app}\LocalCast.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex={#AppMutexName}
CloseApplications=no
RestartApplications=no
UninstallDisplayName=LocalCast {#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoCompany=By Fagner Lemes
VersionInfoDescription=Instalador do LocalCast

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LocalCast"; Filename: "{app}\LocalCast.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\LocalCast"; Filename: "{app}\LocalCast.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LocalCast.exe"; Description: "Abrir LocalCast"; Flags: nowait postinstall skipifsilent

; No [UninstallDelete] entries: retain history, API key and user-created files.
