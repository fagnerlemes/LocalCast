param([switch]$Integration)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    . (Join-Path $PSScriptRoot 'app-runtime.ps1')
    $runtime = Get-LocalCastAppRuntime -Root $taskRoot -Developer
    if ($Integration) { & $runtime.Executable -m pytest -q }
    else { & $runtime.Executable -m pytest -q -m 'not integration' }
    exit $LASTEXITCODE
} finally { Pop-Location }

