param(
    [ValidateSet('excel', 'sql')]
    [string]$Source = 'excel',

    [int]$MaxJobsPerDay = 10
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment executable not found at $pythonExe"
}

Push-Location $repoRoot
try {
    & $pythonExe 'run_mold_schedule_preview.py' '--source' $Source '--max-jobs-per-day' $MaxJobsPerDay
}
finally {
    Pop-Location
}
