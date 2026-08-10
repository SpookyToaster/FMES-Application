param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AdditionalArgs
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment executable not found at $pythonExe"
}

$testModules = @(
    'tests.test_melt_planning',
    'tests.test_scheduler_integration',
    'tests.test_mold_schedule_from_melt'
)

Push-Location $repoRoot
try {
    $args = @('-m', 'unittest') + $testModules
    if ($AdditionalArgs) {
        $args += $AdditionalArgs
    }

    & $pythonExe @args
}
finally {
    Pop-Location
}
