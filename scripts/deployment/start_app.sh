#!/usr/bin/env bash
# Local run: API + web console on http://localhost:8000, plus (optionally) the live replay simulator.
#   scripts/deployment/start_app.sh            # API only
#   scripts/deployment/start_app.sh --demo     # API + virtual wearables streaming real recordings
set -euo pipefail
cd "$(dirname "$0")/../.."

if [ ! -f src/frontend/web/dist/index.html ]; then
  echo "Building the web console (src/frontend/web)..."
  (cd src/frontend/web && npm ci && npm run build)
fi

python -m uvicorn src.backend.app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
sleep 4
echo "TRIDENT running at http://localhost:8000  (API docs: /api/docs)"

if [ "${1:-}" = "--demo" ]; then
  python -m src.backend.app.tools.simulate --api http://localhost:8000 --speed 1 --with-sos
else
  wait $API_PID
fi
