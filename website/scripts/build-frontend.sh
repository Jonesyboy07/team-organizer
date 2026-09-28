#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../frontend"
[ -d node_modules ] || npm install
npm run build