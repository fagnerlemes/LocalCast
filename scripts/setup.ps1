param([string]$Python = '', [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    $portablePython = Join-Path $taskRoot 'runtime\python\python.exe'
    if (-not $Python -and (Test-Path -LiteralPath $portablePython)) {
        & $portablePython -B (Join-Path $PSScriptRoot 'check_portable.py')
        if ($LASTEXITCODE -ne 0) { throw 'A pasta runtime está incompleta. Extraia novamente a versão portátil completa.' }
        Write-Host 'Python portátil e dependências disponíveis. Não precisa instalar Python no Windows.'
        if (-not $CheckOnly) { Write-Host 'Preparação concluída. Abra iniciar.cmd.' }
        exit 0
    }
    . (Join-Path $PSScriptRoot 'python-runtime.ps1')
    $venvPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
    $runtime = if (-not $Python -and (Test-Path -LiteralPath $venvPython)) { Test-LocalCastPython -Executable $venvPython } else { $null }
    if (-not $runtime) {
        try { $runtime = Resolve-LocalCastPython -Python $Python }
        catch {
            if ($CheckOnly -or $Python) { throw }
            Write-Host $_.Exception.Message -ForegroundColor Yellow
            Write-Host ''
            $answer = Read-Host 'Baixar e preparar o Python portátil nesta pasta, sem instalação no Windows? [S/N]'
            if ($answer.Trim().ToUpperInvariant() -notin @('S', 'SIM', 'Y', 'YES')) { throw 'Download cancelado. Você pode instalar Python manualmente ou usar o ZIP portátil completo.' }
            & (Join-Path $PSScriptRoot 'install-portable.ps1') -Root $taskRoot
            Write-Host 'Preparação concluída. Abra iniciar.cmd.'
            exit 0
        }
    }
    Write-Host ('Python encontrado: {0} ({1}, {2} bits)' -f $runtime.executable, ($runtime.version -join '.'), $runtime.bits)
    if ($CheckOnly) { Write-Host 'Verificação concluída. Nenhuma dependência foi instalada.'; exit 0 }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $runtime.executable -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar .venv. Use uma instalação completa do Python; confira permissões da pasta.' }
    }
    & $venvPython -m pip --version
    if ($LASTEXITCODE -ne 0) {
        & $venvPython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw 'O ambiente .venv ficou incompleto. Renomeie essa pasta e execute preparar.cmd novamente.' }
    }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar pip.' }
    & .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências.' }
    Write-Host 'Pronto. Coloque ffmpeg.exe e ffprobe.exe em tools e abra iniciar.cmd.'
} catch {
    Write-Host ''
    Write-Host 'Preparação não concluída:' -ForegroundColor Yellow
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    exit 1
} finally { Pop-Location }

