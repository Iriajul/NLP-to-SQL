#!/usr/bin/env bash
# Start the API (port 8100) and the website (port 3100). Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"
trap 'kill 0' EXIT
.venv/bin/uvicorn api.server:app --port 8100 --reload --reload-dir api --reload-dir zax_backend &
(cd web && npx next dev -p 3100) &
echo "Open http://localhost:3100"
wait
