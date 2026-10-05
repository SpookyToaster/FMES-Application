param(
    [string]$VersionLabel = "0.90"
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
$templatePath = Join-Path $repoRoot '.env.example'
$artifactRoot = Join-Path $env:LOCALAPPDATA 'SchedulerProgram\PyInstaller'
$buildRoot = Join-Path $artifactRoot "prerequisite_$VersionLabel"
$distPath = Join-Path $buildRoot 'dist'
$workPath = Join-Path $buildRoot 'work'
$specPath = Join-Path $buildRoot 'spec'
$releasePath = Join-Path $artifactRoot "release_$VersionLabel"
$outputPath = Join-Path $releasePath "FMES_Prerequisite_Setup_$VersionLabel.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment executable not found at $pythonExe"
}
if (-not (Test-Path $templatePath)) {
    throw "Local config template not found at $templatePath"
}
if (-not (Test-Path (Join-Path $repoRoot 'installer\setup_fmes.py'))) {
    throw "Prerequisite setup application not found under installer."
}

New-Item -ItemType Directory -Force -Path $distPath, $workPath, $specPath, $releasePath | Out-Null
$addData = "$templatePath;."
$arguments = @(
    '-m', 'PyInstaller',
    (Join-Path $repoRoot 'installer\setup_fmes.py'),
    '--onefile',
    '--windowed',
    '--noconfirm',
    '--clean',
    '--name', "FMES_Prerequisite_Setup_$VersionLabel",
    '--add-data', $addData,
    '--distpath', $distPath,
    '--workpath', $workPath,
    '--specpath', $specPath
)

Push-Location $repoRoot
try {
    & $pythonExe @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Prerequisite setup build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$builtApp = Join-Path $distPath "FMES_Prerequisite_Setup_$VersionLabel.exe"
if (-not (Test-Path $builtApp)) {
    throw "Prerequisite setup executable was not created at $builtApp"
}

Copy-Item $builtApp $outputPath -Force
Write-Host "Built prerequisite setup app: $outputPath"
