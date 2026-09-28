#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT_DIR"
if [ ! -f website/static/dist/assets/dashboard.js ]; then
    sh website/scripts/build-frontend.sh
fi

if [ -n "${PYTHON:-}" ]; then
    PYTHON_BIN="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
else
    PYTHON_BIN=python
fi

exec "$PYTHON_BIN" -m website.wsgi