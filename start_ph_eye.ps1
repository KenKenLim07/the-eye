param(
  [switch]$Prod,
  [switch]$Linux
)

$ErrorActionPreference = "Stop"

function Get-ComposeCommand {
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    return @("docker-compose")
  }
  return @("docker", "compose")
}

$compose = Get-ComposeCommand

$composeFile = if ($Prod) { "docker-compose.prod.yml" } else { "docker-compose.yml" }
$files = @("-f", $composeFile)
if ($Linux -and (Test-Path "docker-compose.linux.yml")) {
  $files += @("-f", "docker-compose.linux.yml")
}

Write-Host "🚀 Starting PH Eye (Docker Compose)..."
& $compose @files up -d redis api worker beat

Write-Host ""
Write-Host "✅ Services started"
Write-Host "🌐 API: http://localhost:8000"
Write-Host "📱 Frontend: http://localhost:3000 (run npm run dev)"

