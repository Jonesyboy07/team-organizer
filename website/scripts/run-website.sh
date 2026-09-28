#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
cd "$ROOT_DIR"
if [ ! -f website/static/dist/assets/dashboard.js ]; then
	sh website/scripts/build-frontend.sh
fi
python -m website.app
