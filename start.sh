#!/usr/bin/env bash
# dbSherpa startup script — starts backend + frontend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  dbSherpa — Trade Surveillance Engine"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BACKEND_ROOT="$SCRIPT_DIR/backend"
VENV_PY="$BACKEND_ROOT/.venv/bin/python"

# Check Python (for creating venv if missing)
if ! command -v python3 &>/dev/null; then
  echo "❌ python3 not found. Install Python 3.11+ from https://python.org"
  exit 1
fi

# Check Node
if ! command -v node &>/dev/null; then
  echo "❌ node not found. Install Node.js 20+ from https://nodejs.org"
  exit 1
fi

# Backend setup
echo ""
echo "📦 Setting up backend..."
cd "$BACKEND_ROOT"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# Always use the venv interpreter (reliable even if activate is skipped in odd shells).
"$VENV_PY" -m pip install -q -r requirements.txt
echo "✅ Backend dependencies installed ($VENV_PY)"

# Intentionally do not auto-source backend/.env here. Keep env files local and
# untracked; export required values in the shell that launches this script.
# If you prefer local dotenv loading during development, uncomment this block.
# if [ -f "$BACKEND_ROOT/.env" ]; then
#   set -a
#   # shellcheck disable=SC1091
#   source "$BACKEND_ROOT/.env"
#   set +a
# fi

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "⚠️  GEMINI_API_KEY is not set — Copilot + LLM summaries will fail."
  echo "    Quick fix:"
  echo "      export GEMINI_API_KEY=...      # in this shell before re-running"
  echo "    Optional local-only dotenv:"
  echo "      cp backend/.env.example backend/.env"
  echo "      \$EDITOR backend/.env          # uncomment + paste your key"
fi

# Start backend in background (cwd must be backend/ so `api:app` resolves)
echo "🚀 Starting backend on http://localhost:8000"
cd "$BACKEND_ROOT"
GEMINI_API_KEY="${GEMINI_API_KEY:-}" "$VENV_PY" -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Frontend setup
echo ""
echo "📦 Setting up frontend..."
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
  npm install
fi
echo "✅ Frontend dependencies installed"

# Start frontend
echo "🚀 Starting frontend on http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ dbSherpa running!"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "  Set GEMINI_API_KEY — export it before launch, or opt into local dotenv loading"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop all services"

cleanup() {
  echo ""
  echo "Stopping services..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}
trap cleanup INT TERM
wait
