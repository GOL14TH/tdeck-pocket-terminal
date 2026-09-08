#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; VENV="${VENV:-$ROOT/.venv}"; RECORD="${TDECK_RECORD:-$ROOT/.tdeck-device.json}"
PORT="${1:-}"
if [[ -z "$PORT" && -f "$RECORD" ]]; then PORT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["port"])' "$RECORD")"; fi
[[ -n "$PORT" ]] || { echo "usage: $0 /dev/tty..." >&2; exit 2; }
exec "$VENV/bin/python" -m serial.tools.miniterm "$PORT" 115200
