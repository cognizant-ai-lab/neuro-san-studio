#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/apps/legal_discovery"

echo "[1/6] Checking prerequisites..."
command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
command -v pip3 >/dev/null || { echo "pip3 not found"; exit 1; }
command -v npm >/dev/null || { echo "npm not found"; exit 1; }
command -v docker >/dev/null || { echo "docker not found"; exit 1; }
command -v docker compose >/dev/null || command -v docker-compose >/dev/null || { echo "docker compose not found"; exit 1; }

echo "[2/6] Setting up Python virtualenv..."
cd "$ROOT_DIR"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[3/6] Building frontend via Vite..."
cd "$APP_DIR"
npm ci
npm run build

echo "[4/6] Validating environment files..."
cd "$ROOT_DIR"
if [ ! -f .env ]; then
  echo "FLASK_SECRET_KEY=$(python - <<'PY' 
import secrets
print(secrets.token_hex(16))
PY
)" > .env
  echo "JWT_SECRET=$(python - <<'PY' 
import secrets
print(secrets.token_hex(16))
PY
)" >> .env
  echo "Created default .env with secrets"
fi

echo "[5/6] Building Docker images..."
if command -v docker compose >/dev/null; then
  docker compose build
else
  docker-compose build
fi

echo "[6/6] Starting core services (postgres, chroma, neo4j, redis) and app..."
if command -v docker compose >/dev/null; then
  docker compose up -d
else
  docker-compose up -d
fi

echo "\nAll set!"
echo "- App:        http://localhost:8080"
echo "- Neo4j UI:   http://localhost:7474"
echo "- Chroma API: http://localhost:8000"
echo "- Postgres:   localhost:5432 (trust auth)"

