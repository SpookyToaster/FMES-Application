param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$artifactRoot = Join-Path $env:LOCALAPPDATA 'SchedulerProgram\PyInstaller'
$workPath = Join-Path $artifactRoot "build_$stamp"
$distPath = Join-Path $artifactRoot "dist_$stamp"

New-Item -ItemType Directory -Force -Path $workPath | Out-Null
New-Item -ItemType Directory -Force -Path $distPath | Out-Null

Push-Location $repoRoot
try {
    .\.venv\Scripts\python.exe -m PyInstaller Scheduler.spec --noconfirm --clean --workpath $workPath --distpath $distPath
    Write-Host "Built Scheduler.exe at:"
    Write-Host (Join-Path $distPath 'Scheduler.exe')
}
finally {
    Pop-Location
}