param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$pythonPath = Join-Path $backendRoot ".venv\Scripts\python.exe"
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
$vitePath = Join-Path $frontendRoot "node_modules\vite\bin\vite.js"
$runtimeRoot = Join-Path $projectRoot ".trustscope-local"
$statePath = Join-Path $runtimeRoot "processes.json"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Backend Python was not found at $pythonPath"
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules") -PathType Container)) {
    throw "Frontend dependencies are missing. Run npm install in the frontend directory first."
}

if (-not (Test-Path -LiteralPath $vitePath -PathType Leaf)) {
    throw "The Vite launcher is missing. Run npm install in the frontend directory first."
}

if (-not (Test-Path -LiteralPath $runtimeRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $runtimeRoot | Out-Null
}

if (Test-Path -LiteralPath $statePath -PathType Leaf) {
    throw "TrustScope may already be running. Run .\stop_trustscope.ps1 first."
}

$apiProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @(
        "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8010"
    ) `
    -WorkingDirectory $backendRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $runtimeRoot "api.out.log") `
    -RedirectStandardError (Join-Path $runtimeRoot "api.err.log") `
    -PassThru

$frontendProcess = Start-Process `
    -FilePath $nodePath `
    -ArgumentList @(
        $vitePath,
        "--host", "0.0.0.0",
        "--port", "5173",
        "--strictPort"
    ) `
    -WorkingDirectory $frontendRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $runtimeRoot "frontend.out.log") `
    -RedirectStandardError (Join-Path $runtimeRoot "frontend.err.log") `
    -PassThru

@{
    api = @{
        id = $apiProcess.Id
        started_at = $apiProcess.StartTime.ToUniversalTime().ToString("O")
        process_name = $apiProcess.ProcessName
    }
    frontend = @{
        id = $frontendProcess.Id
        started_at = $frontendProcess.StartTime.ToUniversalTime().ToString("O")
        process_name = $frontendProcess.ProcessName
    }
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding utf8

$deadline = (Get-Date).AddSeconds(45)
$apiReady = $false
$frontendReady = $false

while ((Get-Date) -lt $deadline -and (-not $apiReady -or -not $frontendReady)) {
    if (-not $apiReady) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8010/health" -UseBasicParsing -TimeoutSec 2
            $apiReady = $response.StatusCode -eq 200
        } catch {
            $apiReady = $false
        }
    }

    if (-not $frontendReady) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 2
            $frontendReady = $response.StatusCode -eq 200
        } catch {
            $frontendReady = $false
        }
    }

    if (-not $apiReady -or -not $frontendReady) {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $apiReady -or -not $frontendReady) {
    Write-Warning "TrustScope did not become ready within 45 seconds. Check .trustscope-local\*.err.log."
    exit 1
}

$privateAddress = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -ne "127.0.0.1" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.AddressState -eq "Preferred"
    } |
    Select-Object -ExpandProperty IPAddress -First 1

Write-Host "TrustScope is ready."
Write-Host "Laptop/desktop: http://127.0.0.1:5173"

if ($privateAddress) {
    Write-Host "Phone on the same trusted Wi-Fi: http://${privateAddress}:5173"
}

Write-Host "Stop both services with .\stop_trustscope.ps1"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173"
}
