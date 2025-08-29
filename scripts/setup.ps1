Param(
  [switch]$NoDocker
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$app = Join-Path $root 'apps' 'legal_discovery'

Write-Host "[1/6] Checking prerequisites..."
foreach ($cmd in @('python','pip','npm','docker')) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    throw "$cmd not found"
  }
}

Write-Host "[2/6] Setting up Python virtualenv..."
Push-Location $root
python -m venv .venv
& .\.venv\Scripts\python -m pip install --upgrade pip
& .\.venv\Scripts\pip install -r requirements.txt

Write-Host "[3/6] Building frontend via Vite..."
Push-Location $app
npm ci
npm run build
Pop-Location

Write-Host "[4/6] Validating environment files..."
$envPath = Join-Path $root '.env'
if (-not (Test-Path $envPath)) {
  $flask = [System.BitConverter]::ToString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(16)).Replace('-', '')
  $jwt = [System.BitConverter]::ToString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(16)).Replace('-', '')
  @(
    "FLASK_SECRET_KEY=$flask"
    "JWT_SECRET=$jwt"
  ) | Out-File -FilePath $envPath -Encoding ascii
  Write-Host "Created default .env with secrets"
}

if ($NoDocker) {
  Write-Host "Skipping Docker build/start per -NoDocker flag."
  Pop-Location
  exit 0
}

Write-Host "[5/6] Building Docker images..."
Push-Location $root
docker compose build

Write-Host "[6/6] Starting core services and app..."
docker compose up -d

Write-Host "`nAll set!"
Write-Host "- App:        http://localhost:8080"
Write-Host "- Neo4j UI:   http://localhost:7474"
Write-Host "- Chroma API: http://localhost:8000"
Write-Host "- Postgres:   localhost:5432 (trust auth)"
Pop-Location

