param([switch]$SkipBuild, [switch]$Patch, [ValidateSet(1,2)][int]$PatchRevision = 2)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$compilerRoot = Join-Path $projectRoot '.installer-tools'
$compiler = Join-Path $compilerRoot 'ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    [System.IO.Directory]::CreateDirectory($compilerRoot) | Out-Null
    $download = Join-Path $compilerRoot 'innosetup-6.7.3.exe'
    Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $download
    $expected = '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732'
    if ((Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne $expected) { throw 'Checksum do Inno Setup não confere.' }
    $signature = Get-AuthenticodeSignature -LiteralPath $download
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notlike '*Pyrsys B.V.*') { throw 'Assinatura do compilador não confirmada.' }
    $arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CURRENTUSER','/PORTABLE=1','/NOICONS','/TASKS=',('/DIR="' + $compilerRoot + '"'))
    $process = Start-Process -FilePath $download -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw 'Falha ao preparar o compilador portátil.' }
}
if (-not $SkipBuild) { & (Join-Path $PSScriptRoot 'build.ps1') -IncludeFFmpeg }
$versionLine = Get-Content -LiteralPath (Join-Path $projectRoot 'pyproject.toml') | Where-Object { $_ -match '^version = "' } | Select-Object -First 1
$version = $versionLine.Split('"')[1]
if ($Patch) {
    . (Join-Path $PSScriptRoot 'app-runtime.ps1')
    $runtime = Get-LocalCastAppRuntime -Root $projectRoot
    & $runtime.Executable -B (Join-Path $PSScriptRoot 'build_patch.py') --revision $PatchRevision
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar os arquivos do patch.' }
    $patchNumber = '{0:D2}' -f $PatchRevision
    & $compiler ('/DPatchNumber=' + $patchNumber) ('/DPatchRevision=' + $PatchRevision) (Join-Path $projectRoot 'installer\LocalCast-patch.iss')
} else {
    & $compiler ('/DAppVersion=' + $version) (Join-Path $projectRoot 'installer\LocalCast.iss')
}
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar instalador.' }
if ($Patch) { Write-Host ('Pronto: dist\LocalCast-Patch-0.2.0-' + $patchNumber + '.exe') }
else { Write-Host ('Pronto: dist\LocalCast-Setup-' + $version + '.exe') }
