param([string]$Root = (Split-Path -Parent $PSScriptRoot), [string]$OfflineCache = '')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Root = [IO.Path]::GetFullPath($Root)
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\runtime-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema -ne 1 -or $manifest.platform -ne 'windows-x64') { throw 'Manifesto portátil inválido.' }
$runtimeRoot = Join-Path $Root 'runtime'
$targetRoot = [IO.Path]::GetFullPath((Join-Path $runtimeRoot 'python'))
if (Test-Path -LiteralPath $targetRoot) { throw 'O runtime já existe. Preserve a pasta existente e use uma nova extração para substituir o pacote.' }
$stageRoot = [IO.Path]::GetFullPath((Join-Path $runtimeRoot ('p-' + [guid]::NewGuid().ToString('N').Substring(0, 8))))
$downloads = [IO.Path]::GetFullPath((Join-Path $runtimeRoot ('d-' + [guid]::NewGuid().ToString('N').Substring(0, 8))))
foreach ($path in @($stageRoot, $targetRoot, $downloads)) {
    if (-not $path.StartsWith($Root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Pasta fora do LocalCast.' }
}
New-Item -ItemType Directory -Force -Path $stageRoot, $downloads | Out-Null

function Get-VerifiedArchive {
    param($Item, [switch]$PythonArchive)
    $uri = [Uri]$Item.url
    if ($uri.Scheme -ne 'https' -or $uri.Host -notin @('www.python.org', 'files.pythonhosted.org')) { throw 'Origem de download não permitida.' }
    if ([IO.Path]::GetFileName($Item.filename) -ne $Item.filename) { throw 'Nome de download inválido.' }
    $destination = Join-Path $downloads $Item.filename
    if ($OfflineCache) {
        $cachedFile = if ($PythonArchive) { Join-Path $OfflineCache 'python.zip' } else { Join-Path $OfflineCache ('wheels-core\' + $Item.filename) }
        Copy-Item -LiteralPath $cachedFile -Destination $destination
    } else {
        Write-Host ('Baixando ' + $Item.filename + '…')
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $Item.url -OutFile $destination
    }
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $Item.sha256) { throw ('Checksum não confere: ' + $Item.filename) }
    return $destination
}

function Expand-VerifiedArchive {
    param([string]$Archive, [string]$Destination, [switch]$Wheel)
    $directory = [IO.Path]::GetFullPath($Destination)
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($entry in $zip.Entries) {
            $entryPath = [IO.Path]::GetFullPath((Join-Path $directory $entry.FullName))
            if (-not $entryPath.StartsWith($directory.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Arquivo ZIP contém caminho fora do destino.' }
            if ($Wheel -and $entry.FullName -match '\.data/' -and $entry.FullName -notmatch '\.data/data/LICENSE$') { throw 'Wheel requer instalação não suportada por este empacotador.' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($Archive, $directory)
}

try {
    $pythonArchive = Get-VerifiedArchive -Item $manifest.python -PythonArchive
    Expand-VerifiedArchive -Archive $pythonArchive -Destination $stageRoot
    $packagesRoot = Join-Path $stageRoot 'site-packages'
    foreach ($package in $manifest.packages) {
        $archive = Get-VerifiedArchive -Item $package
        Expand-VerifiedArchive -Archive $archive -Destination $packagesRoot -Wheel
    }
    $pthFile = Get-ChildItem -LiteralPath $stageRoot -Filter 'python*._pth' | Select-Object -First 1
    if (-not $pthFile) { throw 'Python não contém arquivo de isolamento ._pth.' }
    $stdlibZip = (Get-ChildItem -LiteralPath $stageRoot -Filter 'python*.zip' | Select-Object -First 1).Name
    $configuration = @($stdlibZip, '.', 'site-packages', '..\..\src', 'import site') -join "`r`n"
    [IO.File]::WriteAllText($pthFile.FullName, ($configuration + "`r`n"), (New-Object Text.UTF8Encoding $false))
    & (Join-Path $stageRoot 'python.exe') -B (Join-Path $Root 'scripts\check_portable.py')
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao validar Python e dependências; a pasta anterior não foi alterada.' }
    Move-Item -LiteralPath $stageRoot -Destination $targetRoot
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\runtime-manifest.json') -Destination (Join-Path $runtimeRoot 'manifest.json')
    Write-Host ('Python portátil ' + $manifest.python.version + ' preparado nesta pasta. Abra iniciar.cmd.')
} finally {
    # Explicitly verified paths; never remove an existing or active runtime.
    foreach ($temporary in @($stageRoot, $downloads)) {
        $checked = [IO.Path]::GetFullPath($temporary)
        if ($checked.StartsWith($Root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $checked)) {
            Remove-Item -LiteralPath $checked -Recurse -Force
        }
    }
}
