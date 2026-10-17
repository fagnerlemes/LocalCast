; Small update for the original LocalCast 0.2.0. User data is never included.
#ifndef InstallKey
  #define InstallKey "Software\Microsoft\Windows\CurrentVersion\Uninstall\{345B76EF-5AD8-4DC5-9611-190A20447DB8}_is1"
#endif
#ifndef PatchMutex
  #define PatchMutex "LocalCast.FagnerLemes.Desktop"
#endif
#ifndef PatchNumber
  #define PatchNumber "02"
#endif
#ifndef PatchRevision
  #define PatchRevision 2
#endif
[Setup]
AppId=LocalCast-020-patch{#PatchNumber}
AppName=LocalCast
AppVersion=0.2.0
AppVerName=LocalCast 0.2.0 - Atualização {#PatchNumber}
AppPublisher=By Fagner Lemes
DefaultDirName={code:InstallationFolder}
UsePreviousAppDir=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CreateAppDir=yes
Uninstallable=no
CreateUninstallRegKey=no
CloseApplications=no
RestartApplications=no
AppMutex={#PatchMutex}
OutputDir=..\dist
OutputBaseFilename=LocalCast-Patch-0.2.0-{#PatchNumber}
SetupIconFile=..\assets\localcast.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion=0.2.0.{#PatchRevision}
VersionInfoCompany=By Fagner Lemes
VersionInfoDescription=Atualização {#PatchNumber} do LocalCast 0.2.0

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
#include "..\build\patch" + PatchNumber + "\files.iss"

[Code]
function InstallationFolder(Param: String): String;
begin
  if not RegQueryStringValue(HKCU64, '{#InstallKey}', 'InstallLocation', Result) then
    Result := ExpandConstant('{localappdata}\Programs\LocalCast');
end;

function CheckFile(Name, BeforeHash, AfterHash: String): Boolean;
var Actual: String;
begin
  Result := False;
  if not FileExists(ExpandConstant('{app}\') + Name) then begin
    Log('Arquivo ausente na instalação: ' + Name);
    Exit;
  end;
  try
    Actual := GetSHA256OfFile(ExpandConstant('{app}\') + Name);
    Result := (CompareText(Actual, BeforeHash) = 0) or (CompareText(Actual, AfterHash) = 0);
    if not Result then Log('Arquivo diferente da base esperada: ' + Name);
  except
    Log('Não foi possível conferir ' + Name);
  end;
end;

function CompatibleInstallation(): Boolean;
begin
  Result := False;
  if not FileExists(ExpandConstant('{app}\unins000.exe')) then Exit;
#include "..\build\patch" + PatchNumber + "\checks.iss"
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if CheckForMutexes('{#PatchMutex}') then
    Result := 'Feche o LocalCast antes de aplicar a atualização.'
  else if not CompatibleInstallation() then
    Result := 'Esta pasta não contém uma instalação compatível do LocalCast 0.2.0. ' +
              'Confira o destino ou use o instalador completo atualizado. Nenhum arquivo foi alterado.';
end;

procedure InitializeWizard();
begin
  WizardForm.SelectDirLabel.Caption := 'Selecione a pasta em que o LocalCast 0.2.0 está instalado. ' +
    'O patch substitui apenas os arquivos modificados e preserva histórico, configurações e desinstalador.';
  WizardForm.FinishedLabel.Caption := 'LocalCast 0.2.0 atualizado. Abra o programa pelo atalho habitual.';
end;
