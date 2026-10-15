# Runtime discovery without opening Microsoft Store or installing Python automatically.
function Test-LocalCastPython {
    param([string]$Executable, [string[]]$Prefix = @())
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
    $probeCode = "import json,struct,sys,importlib.util; print(json.dumps({'executable':sys.executable,'version':list(sys.version_info[:3]),'bits':struct.calcsize('P')*8,'venv':importlib.util.find_spec('venv') is not None,'ensurepip':importlib.util.find_spec('ensurepip') is not None}))"
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = $Executable
    $processInfo.Arguments = (($Prefix + @('-c', ('"' + $probeCode + '"'))) -join ' ')
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.EnvironmentVariables['PYTHON_MANAGER_AUTOMATIC_INSTALL'] = '0'
    $probeProcess = New-Object System.Diagnostics.Process
    $probeProcess.StartInfo = $processInfo
    try {
        [void]$probeProcess.Start()
        if (-not $probeProcess.WaitForExit(8000)) {
            $probeProcess.Kill()
            return $null
        }
        if ($probeProcess.ExitCode -ne 0) { return $null }
        $result = $probeProcess.StandardOutput.ReadToEnd().Trim() | ConvertFrom-Json
        if ($result.version[0] -ne 3 -or $result.version[1] -lt 11 -or $result.bits -ne 64) { return $null }
        if (-not $result.venv -or -not $result.ensurepip) { return $null }
        if (-not (Test-Path -LiteralPath $result.executable -PathType Leaf)) { return $null }
        return $result
    } catch {
        return $null
    } finally {
        $probeProcess.Dispose()
    }
}

function Resolve-LocalCastPython {
    param([string]$Python = '')
    if ($Python) {
        $explicit = Get-Command -Name $Python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        $explicitPath = if ($explicit) { $explicit.Source } else { $Python }
        $prefix = if ([IO.Path]::GetFileName($explicitPath) -eq 'py.exe') { @('-3') } else { @() }
        if ($explicitPath -notmatch '\\Microsoft\\WindowsApps\\') {
            $runtime = Test-LocalCastPython -Executable $explicitPath -Prefix $prefix
            if ($runtime) { return $runtime }
        }
        throw "Python informado não é uma instalação utilizável de Python 3.11+ 64 bits com venv/pip: $Python"
    }

    $candidatePaths = New-Object 'System.Collections.Generic.List[string]'
    foreach ($commandName in @('python.exe', 'python3.exe')) {
        foreach ($command in @(Get-Command -Name $commandName -CommandType Application -All -ErrorAction SilentlyContinue)) {
            if ($command.Source -notmatch '\\Microsoft\\WindowsApps\\') { $candidatePaths.Add($command.Source) }
        }
    }
    foreach ($registryRoot in @('HKCU:\Software\Python\PythonCore', 'HKLM:\Software\Python\PythonCore', 'HKLM:\Software\WOW6432Node\Python\PythonCore')) {
        if (Test-Path -LiteralPath $registryRoot) {
            foreach ($versionKey in @(Get-ChildItem -LiteralPath $registryRoot -ErrorAction SilentlyContinue)) {
                $installPathKey = Join-Path $versionKey.PSPath 'InstallPath'
                if (Test-Path -LiteralPath $installPathKey) {
                    $key = Get-Item -LiteralPath $installPathKey
                    $registeredExe = $key.GetValue('ExecutablePath')
                    $registeredDirectory = $key.GetValue('')
                    if ($registeredExe) { $candidatePaths.Add([string]$registeredExe) }
                    elseif ($registeredDirectory) { $candidatePaths.Add((Join-Path $registeredDirectory 'python.exe')) }
                }
            }
        }
    }
    $installRoots = @()
    if ($env:LOCALAPPDATA) {
        $installRoots += Join-Path $env:LOCALAPPDATA 'Programs\Python'
        $installRoots += Join-Path $env:LOCALAPPDATA 'Python'
    }
    if ($env:ProgramFiles) { $installRoots += $env:ProgramFiles }
    if ($env:USERPROFILE) {
        $installRoots += Join-Path $env:USERPROFILE 'anaconda3'
        $installRoots += Join-Path $env:USERPROFILE 'miniconda3'
    }
    foreach ($installRoot in $installRoots) {
        if (Test-Path -LiteralPath $installRoot -PathType Container) {
            $candidatePaths.Add((Join-Path $installRoot 'python.exe'))
            foreach ($directory in @(Get-ChildItem -LiteralPath $installRoot -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'Python*' } | Sort-Object Name -Descending)) {
                $candidatePaths.Add((Join-Path $directory.FullName 'python.exe'))
            }
        }
    }
    foreach ($candidate in @($candidatePaths | Select-Object -Unique)) {
        $runtime = Test-LocalCastPython -Executable $candidate
        if ($runtime) { return $runtime }
    }
    # A real launcher can resolve installations not present in PATH or conventional folders.
    foreach ($launcher in @(Get-Command -Name 'py.exe' -CommandType Application -All -ErrorAction SilentlyContinue)) {
        if ($launcher.Source -notmatch '\\Microsoft\\WindowsApps\\') {
            $runtime = Test-LocalCastPython -Executable $launcher.Source -Prefix @('-3')
            if ($runtime) { return $runtime }
        }
    }
    throw @'
Python 3.11+ de 64 bits não foi encontrado.

Instale Python 3.13 para Windows (Windows installer 64-bit):
https://www.python.org/downloads/windows/
Marque "Add python.exe to PATH" no instalador, se a opção aparecer.
Depois feche esta janela e execute preparar.cmd novamente.

Se o Python já está instalado em outra pasta, execute na pasta LocalCast:
preparar.cmd -Python "C:\caminho\python.exe"

Os atalhos WindowsApps da Microsoft Store não foram tratados como Python instalado.
'@
}
