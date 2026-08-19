param(
    [string]$VersionLabel = $(Get-Date -Format 'yyyyMMdd_HHmmss'),
    [int]$KeepReleases = 5
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$artifactRoot = Join-Path $env:LOCALAPPDATA 'SchedulerProgram\PyInstaller'
$workPath = Join-Path $artifactRoot "build_$VersionLabel"
$distPath = Join-Path $artifactRoot "dist_$VersionLabel"
$specPath = Join-Path $artifactRoot "spec_$VersionLabel"
$releasePath = Join-Path $artifactRoot "release_$VersionLabel"

New-Item -ItemType Directory -Force -Path $workPath | Out-Null
New-Item -ItemType Directory -Force -Path $distPath | Out-Null
New-Item -ItemType Directory -Force -Path $specPath | Out-Null
New-Item -ItemType Directory -Force -Path $releasePath | Out-Null

Push-Location $repoRoot
try {
    $fullWorkPath = Join-Path $workPath 'full'
    $updateWorkPath = Join-Path $workPath 'update_only'

    .\.venv\Scripts\python.exe -m PyInstaller .\run_scheduler.py --paths .\src --name Scheduler --onefile --noconfirm --clean --specpath $specPath --workpath $fullWorkPath --distpath $distPath
    .\.venv\Scripts\python.exe -m PyInstaller .\run_oor_schedule.py --paths .\src --name SchedulerUpdateOnly --onefile --noconfirm --clean --specpath $specPath --workpath $updateWorkPath --distpath $distPath

    $builtFullExe = Join-Path $distPath 'Scheduler.exe'
    $builtUpdateExe = Join-Path $distPath 'SchedulerUpdateOnly.exe'
    $versionedFullExe = Join-Path $releasePath "Scheduler_$VersionLabel.exe"
    $versionedUpdateExe = Join-Path $releasePath "SchedulerUpdateOnly_$VersionLabel.exe"

    Copy-Item $builtFullExe $versionedFullExe -Force
    Copy-Item $builtUpdateExe $versionedUpdateExe -Force

    $buildInfo = @"
Build Label: $VersionLabel
Built On: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Source: $repoRoot
Full Executable: $versionedFullExe
Update-Only Executable: $versionedUpdateExe
"@

    Set-Content -Path (Join-Path $releasePath 'build-info.txt') -Value $buildInfo -Encoding UTF8

    Write-Host 'Built release files:'
    Write-Host $versionedFullExe
    Write-Host $versionedUpdateExe
    Write-Host (Join-Path $releasePath 'build-info.txt')

    # Work/dist folders are throwaway; releases keep only the newest $KeepReleases.
    Get-ChildItem -Directory $artifactRoot |
        Where-Object { $_.Name -match '^(build|dist|spec)_' -and $_.FullName -ne $workPath -and $_.FullName -ne $distPath -and $_.FullName -ne $specPath } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    Get-ChildItem -Directory $artifactRoot |
        Where-Object { $_.Name -match '^release_' } |
        Sort-Object Name -Descending |
        Select-Object -Skip $KeepReleases |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}
finally {
    Pop-Location
}