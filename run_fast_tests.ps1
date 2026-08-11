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
    'tests.test_scheduler_build'
)

Push-Location $repoRoot
try {
    $testArgs = @('-m', 'unittest') + $testModules
    if ($AdditionalArgs) {
        $testArgs += $AdditionalArgs
    }

    & $pythonExe @testArgs
}
finally {
    Pop-Location
}
