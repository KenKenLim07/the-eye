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
  throw "Python not found (expected `python` or `py -3`)."
}

$py = Get-PythonCommand
$scriptPath = Join-Path $PSScriptRoot "smoke_test.py"

& $py $scriptPath `
  --backend-url $BackendUrl `
  --retries $Retries `
  --retry-delay-ms $RetryDelayMs
