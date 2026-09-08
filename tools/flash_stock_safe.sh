#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Use tools/flash_verified.py with an explicit port, expected MAC, image and reviewed SHA-256."
echo "It defaults to inspection. --confirm-app-write is required for the application write."
exit 2
