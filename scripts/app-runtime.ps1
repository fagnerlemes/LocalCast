# Resolve the runtime for launch; a private Python always takes precedence.
function Get-LocalCastAppRuntime {
    param([string]$Root, [switch]$Developer)
    $portableExe = Join-Path $Root 'runtime\python\python.exe'
    if (-not $Developer -and (Test-Path -LiteralPath $portableExe -PathType Leaf)) {
        return [pscustomobject]@{ Executable = $portableExe; Portable = $true }
    }
    $venvExe = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvExe -PathType Leaf) {
        return [pscustomobject]@{ Executable = $venvExe; Portable = $false }
    }
    if ($Developer) { throw 'Para ferramentas de desenvolvimento, execute preparar.cmd -Python com uma instalação completa do Python.' }
    throw 'Execute preparar.cmd, ou extraia a versão LocalCast-Portable completa.'
}

function Initialize-LocalCastAppRuntime {
    param($Runtime, [string]$Root)
    if ($Runtime.Portable -and -not $env:LOCALCAST_DATA_DIR) {
        $env:LOCALCAST_DATA_DIR = Join-Path $Root 'localcast-data'
    }
}
