#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Run with sudo" >&2; exit 2; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
id tdeck >/dev/null 2>&1 || useradd --system --home /var/lib/tdeck-companion --shell /usr/sbin/nologin tdeck
install -d -o tdeck -g tdeck /var/lib/tdeck-companion /etc/tdeck-companion /opt/tdeck-companion
python3 -m venv /opt/tdeck-companion/venv
/opt/tdeck-companion/venv/bin/pip install "${SRC}[desktop,mesh]"
if [[ ! -f /etc/tdeck-companion/config.yaml ]]; then
  install -m 640 -o root -g tdeck "$SRC/examples/config.yaml" /etc/tdeck-companion/config.yaml
  /opt/tdeck-companion/venv/bin/python - <<'PY'
from pathlib import Path
import secrets,yaml
p=Path('/etc/tdeck-companion/config.yaml')
data=yaml.safe_load(p.read_text());data['token']=secrets.token_hex(32)
p.write_text(yaml.safe_dump(data,sort_keys=False))
PY
fi
getent group dialout >/dev/null && usermod -a -G dialout tdeck
install -m 644 "$SRC/systemd/tdeck-companion.service" /etc/systemd/system/tdeck-companion.service
systemctl daemon-reload
echo "Installed, not started. Configure /etc/tdeck-companion/config.yaml; then systemctl enable --now tdeck-companion."
