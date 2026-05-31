#!/usr/bin/env bash
set -e

echo
echo "=== MathCraft self-host launcher ==="
echo

if ! command -v cloudflared &> /dev/null; then
    echo "X cloudflared is not on PATH."
    echo "  Install: https://github.com/cloudflare/cloudflared/releases"
    echo "  macOS:   brew install cloudflared"
    echo "  Linux:   see Cloudflare docs for your distro's package"
    exit 1
fi

if [ ! -d "backend/venv" ]; then
    echo "X Backend venv not found. Run ./setup.sh first."
    exit 1
fi

echo "Starting backend on http://localhost:8000 ..."
(
    cd backend
    # shellcheck source=/dev/null
    source venv/bin/activate
    exec uvicorn main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

# Stop the backend if this script exits (Ctrl+C, error, etc.)
trap 'echo; echo "Shutting down backend (pid $BACKEND_PID)..."; kill $BACKEND_PID 2>/dev/null || true' EXIT

echo "Waiting 4 seconds for backend to come up..."
sleep 4

echo
echo "Starting Cloudflare quick tunnel..."
echo "Look for the 'https://...trycloudflare.com' URL below — copy it,"
echo "then on the GitHub Pages site click 'Connect backend' and paste it."
echo
echo "Press Ctrl+C to stop both the tunnel and the backend."
echo

cloudflared tunnel --url http://localhost:8000
