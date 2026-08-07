param(
    [string]$VersionLabel = $(Get-Date -Format 'yyyyMMdd_HHmmss')
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$artifactRoot = Join-Path $env:LOCALAPPDATA 'SchedulerProgram\PyInstaller'
$workPath = Join-Path $artifactRoot "build_$VersionLabel"
$distPath = Join-Path $artifactRoot "dist_$VersionLabel"
$releasePath = Join-Path $artifactRoot "release_$VersionLabel"

New-Item -ItemType Directory -Force -Path $workPath | Out-Null
New-Item -ItemType Directory -Force -Path $distPath | Out-Null
New-Item -ItemType Directory -Force -Path $releasePath | Out-Null

Push-Location $repoRoot
try {
    .\.venv\Scripts\python.exe -m PyInstaller Scheduler.spec --noconfirm --clean --workpath $workPath --distpath $distPath
    $builtExe = Join-Path $distPath 'Scheduler.exe'
    $versionedExe = Join-Path $releasePath "Scheduler_$VersionLabel.exe"

    Copy-Item $builtExe $versionedExe -Force

    $buildInfo = @"
Build Label: $VersionLabel
Built On: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Source: $repoRoot
Executable: $versionedExe
"@

    Set-Content -Path (Join-Path $releasePath 'build-info.txt') -Value $buildInfo -Encoding UTF8

    Write-Host 'Built release files:'
    Write-Host $versionedExe
    Write-Host (Join-Path $releasePath 'build-info.txt')
}
finally {
    Pop-Location
}