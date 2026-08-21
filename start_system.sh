#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [ -x "$BACKEND_DIR/.venv-1/bin/python" ]; then
  PYTHON_BIN="$BACKEND_DIR/.venv-1/bin/python"
elif [ -x "$BACKEND_DIR/venv/bin/python" ]; then
  PYTHON_BIN="$BACKEND_DIR/venv/bin/python"
else
  PYTHON_BIN="python"
fi

echo "==================================================="
echo "  Starting PhishGuard AI Phishing Detection System"
echo "==================================================="
echo ""

cd "$BACKEND_DIR"
"$PYTHON_BIN" -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

cd "$FRONTEND_DIR"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID, Frontend PID: $FRONTEND_PID"
echo "System active at http://localhost:5173"

echo "Backend API docs at http://localhost:8000/docs"

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
