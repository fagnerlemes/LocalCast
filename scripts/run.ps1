param([int]$Port = 8767, [switch]$Diagnose, [switch]$Console)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
try {
    . (Join-Path $PSScriptRoot 'app-runtime.ps1')
    $runtime = Get-LocalCastAppRuntime -Root $taskRoot
    Initialize-LocalCastAppRuntime -Runtime $runtime -Root $taskRoot
    if ($Diagnose) {
        & $runtime.Executable -B -m localcast --port $Port --diagnose
        exit $LASTEXITCODE
    }
    $launcher = Join-Path $taskRoot 'run_localcast.py'
    if ($Console) {
        & $runtime.Executable -B $launcher --port $Port
        exit $LASTEXITCODE
    }
    $windowedExe = Join-Path (Split-Path -Parent $runtime.Executable) 'pythonw.exe'
    if (-not (Test-Path -LiteralPath $windowedExe -PathType Leaf)) {
        throw 'pythonw.exe ausente. Execute preparar.cmd ou use iniciar-debug.cmd para verificar a instalação.'
    }
    # The native executable and working directory are passed separately; quote only the script path.
    $launchArguments = @('-B', ('"' + $launcher + '"'), '--port', [string]$Port)
    # Use literal native paths: Start-Process resolves [] as wildcards in WorkingDirectory.
    # CreateNoWindow suppresses a console; Qt still creates its interactive window normally.
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $windowedExe
    $startInfo.Arguments = [string]::Join(' ', $launchArguments)
    $startInfo.WorkingDirectory = $taskRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $appProcess = [System.Diagnostics.Process]::Start($startInfo)
    $appProcess.Dispose()
    exit 0
} catch {
    $message = $_.Exception.Message
    try {
        $launchData = if ($env:LOCALCAST_DATA_DIR) { $env:LOCALCAST_DATA_DIR } else { Join-Path $taskRoot 'localcast-data' }
        $launchLogs = Join-Path $launchData 'logs'
        [System.IO.Directory]::CreateDirectory($launchLogs) | Out-Null
        [System.IO.File]::AppendAllText((Join-Path $launchLogs 'startup-launcher.log'), ($_.ToString() + [Environment]::NewLine), [System.Text.Encoding]::UTF8)
    } catch { }
    if ($Diagnose -or $Console) {
        Write-Host ('LocalCast: ' + $message) -ForegroundColor Red
    } else {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($message, 'LocalCast - falha ao iniciar', 'OK', 'Error') | Out-Null
    }
    exit 1
} finally { Pop-Location }

