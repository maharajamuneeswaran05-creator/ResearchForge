#!/bin/sh
set -e

echo "=== Starting ResearchForge Unified Container ==="

# 1. Start FastAPI backend on internal loopback port 8000
echo "Starting FastAPI backend on 127.0.0.1:8000..."
cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# 2. Wait for FastAPI backend to be ready
echo "Waiting for FastAPI backend to be ready..."
for i in $(seq 1 30); do
  if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "FastAPI backend is ready!"
    break
  fi
  sleep 1
done

# 3. Start Next.js standalone server on public $PORT
export PORT="${PORT:-10000}"
export BACKEND_URL="http://127.0.0.1:8000"
export HOSTNAME="0.0.0.0"

echo "Starting Next.js frontend on public port $PORT..."

if [ -f /app/frontend/server.js ]; then
  cd /app/frontend
  exec node server.js
elif [ -f /app/frontend/frontend/server.js ]; then
  cd /app/frontend/frontend
  exec node server.js
elif [ -f /app/frontend/.next/standalone/server.js ]; then
  cd /app/frontend/.next/standalone
  exec node server.js
else
  echo "Looking for server.js..."
  find /app -name "server.js"
  SERVER_FILE=$(find /app -name "server.js" | head -n 1)
  cd "$(dirname "$SERVER_FILE")"
  exec node server.js
fi
