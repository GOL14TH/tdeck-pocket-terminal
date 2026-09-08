#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM_DIR="${UPSTREAM_DIR:-$ROOT/.upstream/firmware}"
UPSTREAM_REF="${UPSTREAM_REF:-567b8ea1c2b2d100c24b0d6cbc437ec89fae0a56}"
VENV="${VENV:-$ROOT/.venv}"

if ! command -v git >/dev/null; then echo "git is required" >&2; exit 2; fi
if [[ ! -d "$UPSTREAM_DIR/.git" ]]; then
  mkdir -p "$(dirname "$UPSTREAM_DIR")"
  git clone --filter=blob:none https://github.com/meshtastic/firmware.git "$UPSTREAM_DIR"
fi
git -C "$UPSTREAM_DIR" fetch --tags origin
git -C "$UPSTREAM_DIR" checkout --detach "$UPSTREAM_REF"
git -C "$UPSTREAM_DIR" submodule update --init --recursive

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/pip" install platformio==6.1.19 esptool==4.8.1 meshtastic==2.7.11 pyserial

echo "Pinned upstream: $(git -C "$UPSTREAM_DIR" rev-parse HEAD)"
echo "Toolchain: $VENV"
