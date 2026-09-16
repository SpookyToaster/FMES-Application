param(
    [string]$VersionLabel = "",
    [string]$ReleasePath = "",
    [string]$InnoCompilerPath = ""
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$artifactRoot = Join-Path $env:LOCALAPPDATA 'SchedulerProgram\PyInstaller'
$issPath = Join-Path $repoRoot 'installer\SchedulerInstaller.iss'

if (-not (Test-Path $issPath)) {
    throw "Installer definition not found: $issPath"
}

function Resolve-InnoCompilerPath {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        if (Test-Path $ExplicitPath) {
            return $ExplicitPath
        }
        throw "Inno Setup compiler path does not exist: $ExplicitPath"
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    throw (
        "Inno Setup compiler was not found. Install Inno Setup 6, then rerun this script. " +
        "Expected ISCC.exe under Program Files or Program Files (x86)."
    )
}

function Resolve-ReleasePath {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        if (Test-Path $ExplicitPath) {
            return (Resolve-Path $ExplicitPath).Path
        }
        throw "Release path does not exist: $ExplicitPath"
    }

    $releaseDirs = Get-ChildItem -Directory $artifactRoot -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'release_*' } |
        Sort-Object Name -Descending

    if (-not $releaseDirs -or $releaseDirs.Count -eq 0) {
        throw "No release_* folders found under $artifactRoot. Build EXEs first with build_scheduler.ps1"
    }

    return $releaseDirs[0].FullName
}

$compilerPath = Resolve-InnoCompilerPath -ExplicitPath $InnoCompilerPath
$resolvedReleasePath = Resolve-ReleasePath -ExplicitPath $ReleasePath

if (-not $VersionLabel) {
    $leaf = Split-Path -Leaf $resolvedReleasePath
    if ($leaf -like 'release_*') {
        $VersionLabel = $leaf.Substring('release_'.Length)
    } else {
        $VersionLabel = Get-Date -Format 'yyyyMMdd_HHmmss'
    }
}

$arguments = @(
    "/DSourceReleaseDir=$resolvedReleasePath",
    "/DRepoRoot=$repoRoot",
    "/DMyAppVersion=$VersionLabel",
    "/DMyBuildLabel=$VersionLabel",
    $issPath
)

Write-Host "Compiling installer with: $compilerPath"
Write-Host "Release source: $resolvedReleasePath"
Write-Host "Version label: $VersionLabel"

& $compilerPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compiler failed with exit code $LASTEXITCODE"
}

$installerPath = Join-Path $resolvedReleasePath "FMES_Scheduler_Setup_$VersionLabel.exe"
if (Test-Path $installerPath) {
    Write-Host "Installer created: $installerPath"
} else {
    Write-Host "Installer compile completed. Check output folder: $resolvedReleasePath"
}
