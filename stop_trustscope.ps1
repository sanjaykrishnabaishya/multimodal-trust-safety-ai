$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".trustscope-local"
$statePath = Join-Path $runtimeRoot "processes.json"

if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    Write-Host "TrustScope is not recorded as running."
    exit 0
}

$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json

foreach ($serviceName in @("frontend", "api")) {
    $entry = $state.$serviceName

    if (-not $entry) {
        continue
    }

    $process = Get-Process -Id ([int]$entry.id) -ErrorAction SilentlyContinue

    if (-not $process) {
        continue
    }

    $recordedStart = [DateTime]::Parse($entry.started_at).ToUniversalTime()
    $actualStart = $process.StartTime.ToUniversalTime()

    if ($actualStart -ne $recordedStart) {
        Write-Warning "Skipped PID $($entry.id) because it now belongs to a different process."
        continue
    }

    Stop-Process -Id $process.Id
}

Remove-Item -LiteralPath $statePath
Write-Host "TrustScope services stopped."
