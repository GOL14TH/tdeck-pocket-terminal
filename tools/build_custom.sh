#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; UPSTREAM_DIR="${UPSTREAM_DIR:-$ROOT/.upstream/firmware}"; VENV="${VENV:-$ROOT/.venv}"
"$ROOT/tools/apply_overlay.sh"
cd "$UPSTREAM_DIR"
"$VENV/bin/pio" run -e t-deck-tft
sha256sum .pio/build/t-deck-tft/firmware.bin | tee "$ROOT/build-custom.sha256"
