param(
  [string]$BackendUrl = $(if ($env:BACKEND_URL) { $env:BACKEND_URL } else { "http://localhost:8000" }),
  [string]$Source = "inquirer",
  [int]$PollSeconds = 5,
  [int]$MaxMinutes = 20
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
$scriptPath = Join-Path $PSScriptRoot "pipeline_test.py"

& $py $scriptPath `
  --backend-url $BackendUrl `
  --source $Source `
  --poll-seconds $PollSeconds `
  --max-minutes $MaxMinutes
