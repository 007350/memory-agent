#!/usr/bin/env bash
# memory-agent — start all services on macOS / Linux
# Usage: ./start.sh   (Ctrl-C stops everything)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="${MEMORYAGENT_PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  elif [[ -x "$ROOT/backend/.venv/bin/python" ]]; then
    PYTHON="$ROOT/backend/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
  else
    echo "[ERROR] python3 not found. Create a venv or set MEMORYAGENT_PYTHON." >&2
    exit 1
  fi
fi
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

echo "[info] Python       : $PYTHON"
command -v npm >/dev/null 2>&1 || { echo "[ERROR] npm not found." >&2; exit 1; }

[[ -f backend/.env ]] || echo "[WARN] backend/.env missing — copy backend/.env.example and fill in keys"
[[ -f lightrag/.env ]] || echo "[WARN] lightrag/.env missing — copy lightrag/.env.example and fill in keys"
[[ -d frontend/node_modules ]] || echo "[WARN] frontend/node_modules missing — run: (cd frontend && npm install)"

pids=()
cleanup() {
  echo
  echo "[info] shutting down ..."
  for pid in "${pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[1/3] LightRAG Server (port 9621)"
( cd lightrag && "$PYTHON" -c "from lightrag.api.lightrag_server import main; main()" ) & pids+=($!)
sleep 6

echo "[2/3] Backend (port 8000)"
( cd backend && "$PYTHON" -m uvicorn app.main:app --reload --port 8000 ) & pids+=($!)
sleep 3

echo "[3/3] Frontend (port 5173)"
( cd frontend && npm run dev ) & pids+=($!)

echo
echo "  LightRAG : http://localhost:9621/health"
echo "  Backend  : http://localhost:8000/health"
echo "  Frontend : http://localhost:5173"
echo "  Ctrl-C to stop all services."
wait
