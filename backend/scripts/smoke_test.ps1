param(
  [string]$BackendUrl = $(if ($env:BACKEND_URL) { $env:BACKEND_URL } else { "http://localhost:8000" }),
  [int]$Retries = 8,
  [int]$RetryDelayMs = 750
)

$ErrorActionPreference = "Stop"

function Invoke-WithRetry($name, $scriptBlock) {
  $attempt = 0
  while ($true) {
    try {
      $attempt++
      return (& $scriptBlock)
    } catch {
      if ($attempt -ge $Retries) { throw }
      Write-Host ("[RETRY] " + $name + " (attempt " + $attempt + " failed; retrying in " + $RetryDelayMs + "ms)")
      Start-Sleep -Milliseconds $RetryDelayMs
    }
  }
}

function Assert-Ok($name, $scriptBlock) {
  Write-Host ("[SMOKE] " + $name)
  $res = Invoke-WithRetry $name $scriptBlock
  if ($null -eq $res) { throw ("Smoke check failed: " + $name + " (null response)") }
  Write-Host ("[OK] " + $name)
}

Assert-Ok "GET /health" { Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get -TimeoutSec 30 }

Assert-Ok "GET /articles/home-optimized" {
  Invoke-RestMethod -Uri "$BackendUrl/articles/home-optimized?limit_per_source=2&refresh=true" -Method Get -TimeoutSec 60
}

Assert-Ok "GET /ml/trends" {
  # Trends can be slow on cold cache because it fans out to Supabase for many rows.
  Invoke-RestMethod -Uri "$BackendUrl/ml/trends?period=7d&include_today=true&refresh=true" -Method Get -TimeoutSec 180
}

Assert-Ok "GET /ml/correlation" {
  Invoke-RestMethod -Uri "$BackendUrl/ml/correlation?period=7d&include_today=true&refresh=true" -Method Get -TimeoutSec 180
}

Assert-Ok "GET /ml/entities/top" {
  Invoke-RestMethod -Uri "$BackendUrl/ml/entities/top?period=7d&include_today=true&refresh=true" -Method Get -TimeoutSec 180
}

Write-Host "[DONE] smoke checks passed"
