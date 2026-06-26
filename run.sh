#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env — set -a exports all variables defined while it's active,
# handles values with spaces correctly unlike the xargs approach
if [ -f ".env" ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

# Create virtualenv if needed
if [ ! -d ".venv" ]; then
  echo "→ Creando entorno virtual..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "→ Instalando dependencias..."
pip install -q -r backend/requirements.txt

echo ""
echo "✅ BuscaPrecios iniciado en http://localhost:8000"

if [ -n "${ML_CLIENT_ID:-}" ]; then
  echo "   MercadoLibre: habilitado ✓"
else
  echo "   MercadoLibre: deshabilitado (agrega ML_CLIENT_ID y ML_CLIENT_SECRET en .env)"
fi

echo "   Presiona Ctrl+C para detener"
echo ""

cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
