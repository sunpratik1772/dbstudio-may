#!/usr/bin/env bash
# dbSherpa startup script — starts backend + frontend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  dbSherpa — Trade Surveillance Engine"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python
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
cd "$SCRIPT_DIR/backend"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
echo "✅ Backend dependencies installed"

# Load backend/.env if present (for GEMINI_API_KEY etc.)
if [ -f "$SCRIPT_DIR/backend/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/backend/.env"
  set +a
fi

if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "⚠️  GEMINI_API_KEY is not set — Copilot + LLM summaries will fail."
  echo "    Quick fix:"
  echo "      cp backend/.env.example backend/.env"
  echo "      \$EDITOR backend/.env          # paste your key"
  echo "    …or export GEMINI_API_KEY=... in your shell before re-running."
fi

# Start backend in background
echo "🚀 Starting backend on http://localhost:8000"
GEMINI_API_KEY="${GEMINI_API_KEY:-}" python3 -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload &
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
echo "  Set GEMINI_API_KEY — copy backend/.env.example to backend/.env and fill it in"
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
