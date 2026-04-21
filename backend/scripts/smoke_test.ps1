param(
  [string]$BackendUrl = $(if ($env:BACKEND_URL) { $env:BACKEND_URL } else { "http://localhost:8000" }),
  [int]$Retries = 8,
  [int]$RetryDelayMs = 750
)

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
  if (Get-Command python -ErrorAction SilentlyContinue) {
    return @("python")
  }
  if (Get-Command py -ErrorAction SilentlyContinue) {
    return @("py", "-3")
  }
  return $null
}

function Invoke-DockerSmokeTest {
  param(
    [string]$BackendUrl,
    [int]$Retries,
    [int]$RetryDelayMs
  )

  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Python not found and docker not found. Install Python 3.x or Docker Desktop."
  }

  $container = "ph-eye-api"
  $running = docker ps --format "{{.Names}}" | Select-String -SimpleMatch $container
  if (-not $running) {
    throw "Docker container '$container' is not running. Start the backend first (e.g. docker compose up -d redis api)."
  }

  & docker exec $container python /app/backend/scripts/smoke_test.py `
    --backend-url $BackendUrl `
    --retries $Retries `
    --retry-delay-ms $RetryDelayMs
}

$py = Get-PythonCommand
$scriptPath = Join-Path $PSScriptRoot "smoke_test.py"

if ($py) {
  & $py $scriptPath `
    --backend-url $BackendUrl `
    --retries $Retries `
    --retry-delay-ms $RetryDelayMs
} else {
  Invoke-DockerSmokeTest -BackendUrl $BackendUrl -Retries $Retries -RetryDelayMs $RetryDelayMs
}
