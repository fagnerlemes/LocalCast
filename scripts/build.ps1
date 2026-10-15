param([switch]$IncludeFFmpeg, [switch]$OneFile)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
try {
    . (Join-Path $PSScriptRoot 'app-runtime.ps1')
    $runtime = Get-LocalCastAppRuntime -Root $taskRoot
    $buildArguments = @('-B', (Join-Path $PSScriptRoot 'build_exe.py'))
    if ($OneFile) { $buildArguments += '--onefile' }
    if ($IncludeFFmpeg) { $buildArguments += '--include-ffmpeg' }
    Write-Host 'Gerando LocalCast.exe. Feche o executável antigo antes de substituir.'
    & $runtime.Executable @buildArguments
    if ($LASTEXITCODE -ne 0) { throw 'Build falhou.' }
} finally { Pop-Location }

