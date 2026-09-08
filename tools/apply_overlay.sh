#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/tools/apply_firmware.py" "${UPSTREAM_DIR:-$ROOT/.upstream/firmware}"
