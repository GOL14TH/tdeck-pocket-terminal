#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM_DIR="${UPSTREAM_DIR:-$ROOT/.upstream/firmware}"
VENV="${VENV:-$ROOT/.venv}"
[[ -x "$VENV/bin/pio" ]] || { echo "Run tools/bootstrap_upstream.sh first" >&2; exit 2; }
[[ -d "$UPSTREAM_DIR/.git" ]] || { echo "Missing upstream checkout" >&2; exit 2; }
[[ ! -f "$UPSTREAM_DIR/src/graphics/PocketLauncher.cpp" ]] || { echo "Stock build requires a clean pinned checkout, not an overlaid custom tree." >&2; exit 3; }
cd "$UPSTREAM_DIR"
"$VENV/bin/pio" run -e t-deck
"$VENV/bin/pio" run -e t-deck-tft
sha256sum .pio/build/t-deck/firmware.bin .pio/build/t-deck-tft/firmware.bin | tee "$ROOT/build-stock.sha256"
