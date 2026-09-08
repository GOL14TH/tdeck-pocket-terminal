# T-Deck Pocket Terminal — integration build

Meshtastic-based LILYGO T-Deck Plus firmware and a Raspberry Pi/Linux companion. The active firmware uses the already-buildable Meshtastic **2.7.15 / 567b8ea1c2b2d100c24b0d6cbc437ec89fae0a56** base and its LVGL device UI. It does not replace the board drivers or pin map.

## Installation and real-device demos

Start with the [complete installation guide](docs/INSTALL.md) and [bring-your-own model/API guide](docs/API-MODELS.md), then see the [desktop photo and hardware videos](docs/MEDIA.md). The firmware has been flashed and verified, and the Pi5 AI/terminal/desktop APIs passed live tests. **The handheld recordings show intermittent response errors; this remains an experimental build.** See [known issues](docs/KNOWN-ISSUES.md).

![T-Deck remote desktop](docs/media/desktop.jpg)

## What is implemented

- Launcher with a route into and back out of normal Meshtastic.

- Four persistent host profiles, companion URL/host ID/token, mesh gateway node and signing key.

- Four saved Wi-Fi profiles. Applying one saves Meshtastic's network configuration and restarts; the upstream service owns reconnection.

- AI prompt/reply screen using bounded asynchronous companion jobs. Thinking is disabled and output/context are capped for the Pi.

- Line-oriented PTY terminal with command entry, output polling, Ctrl-C, Tab and Escape. It is not a complete VT100 emulator; full-screen programs such as vim are not a verified use case.

- Remote desktop through a VNC/RFB adapter on the companion: 320×176 viewport within the 320×240 UI, changed RGB565 tiles, tap/click, keyboard input and panning.

- Signed, chunked Meshtastic command requests on PRIVATE_APP, channel 0. Retries retain the same message ID. The companion persistently reserves IDs before executing commands.

- Read-only SD directory listing and text preview, using the upstream-mounted SD/shared SPI bus. A listing is limited to 64 entries and previews to 4KB.

- Battery/Wi-Fi/GPS/time status. Display, input, power, radio, Bluetooth and other hardware settings remain available in the existing Meshtastic UI.

- An explicitly labelled browser simulator that exercises the real companion APIs without loading models or executing terminal commands.

## Verification boundaries

Read **PROJECT_STATUS.md** for the exact tested state and image hashes. A browser simulator is not ESP32 emulation. Passing companion tests does not establish physical keyboard, touchscreen, radio, GPS, SD, audio, battery or Wi-Fi behavior on the board. Live integration now uses the existing Raspberry Pi 5. The separate earlier T-Deck Pi with a failing power supply was not used for these live tests.

The legacy monochrome overlay is not included in this public distribution. Active device code is under `firmware/`. The former WebSocket endpoints have been replaced by bounded REST session APIs used by this device build.

## Local simulation

Python 3.11+:

```sh

python -m venv .venv

# Linux: source .venv/bin/activate

# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install ./companion

python -m tdeck_companion.simulator

```

Open http://127.0.0.1:8788. The simulator binds only to loopback and uses a fixed **simulation-only** token. It never contacts a Pi, loads Ollama or executes shell commands. Do not use its token for a real deployment. AI and terminal responses visibly identify themselves as simulated. The desktop grid uses the same tile format as firmware.

## Build

Linux/macOS with git and Python 3.11+:

```sh

bash tools/bootstrap_upstream.sh

bash tools/build_stock.sh

bash tools/build_custom.sh

```

`bootstrap_upstream.sh` pins the release above and initializes submodules. `apply_firmware.py` copies the LVGL integration and adds the two registration hooks. It is idempotent. No build script flashes a device. Toolchains and upstream dependencies require Internet access on first build.

On the prepared Windows work root from this project:

```powershell

./tools/build_windows.ps1 -WorkRoot 'C:\tdeck-work'

```

This reuses the isolated PlatformIO environment and short `M:` paths, including a short TEMP/TMP path required by the linker. It refuses to replace another existing M: mapping. The sandbox build can report `APP_REPO=unknown`; use the pinned source commit and artifact SHA-256 manifest for provenance.

## Configure a real companion after power is fixed

On the dedicated Pi (not the existing website server):

```sh

sudo apt-get install python3-venv

cd companion

sudo bash install.sh

sudoedit /etc/tdeck-companion/config.yaml

sudo systemctl enable --now tdeck-companion

curl http://127.0.0.1:8787/health

```

The installer generates a random bearer token only for a new configuration and preserves an existing configuration. It installs but does not automatically start the service. The service runs as unprivileged `tdeck`, with its home/state under `/var/lib/tdeck-companion`.

Set each host's `id`, AI URL/model, optional SSH `terminal_target` and optional VNC host/port/password. A null terminal target opens a shell as the unprivileged companion service user. Use SSH keys and verified known_hosts belonging to that user for remote machines. For a Tailscale destination, run Tailscale on the companion and use its SSH/VNC reachability; the handheld contacts the companion's LAN URL. Do not put an unreachable Tailscale-only address directly into the handheld unless the LAN has a route to it.

The configuration does not install OpenClaw or any model. Set `ai_model` to a model actually installed after the Pi's power is verified. Raspberry Pi OS Lite has no desktop to view by default; point VNC at an existing desktop host or intentionally configure a desktop/VNC server on the dedicated Pi.

For HTTPS, configure `tls_cert` and `tls_key`, use a certificate matching the companion URL hostname, and put its CA PEM on the SD card at `/pocket-ca.pem`. Import it in Hosts. TLS verification is never disabled. Plain HTTP is supported for a trusted LAN bring-up, not for untrusted Wi-Fi. Device and server time must be valid for certificates.

On the T-Deck, enter the companion base URL (for example `http://tdeckpi.local:8787`), matching host ID `pi`, and the generated token. Save, then Test link. Configure Wi-Fi through the launcher or existing Meshtastic settings.

## Mesh commands

A **second Meshtastic radio node** must connect to the Pi through serial or TCP. Configure exactly one of `mesh_serial` and `mesh_tcp`, a separate random `mesh_key` of at least 32 characters, and `mesh_allowed_nodes` containing the handheld's numeric node ID. Enter that same key and the gateway node's hexadecimal ID in the handheld's saved host profile. Both radios must use compatible channel-0 radio/channel settings.

Only explicitly allowlisted command names execute by default, with fixed argv templates and no shell expansion. Raw shell is disabled. The application adds an HMAC-SHA256 to payloads before chunking; the signature binds the handheld node, message kind, session and message ID. Normal Meshtastic channel encryption remains in use.

Duplicate execution protection is **at-most-once**, not a claim of exactly-once completion: the database reserves an ID before starting a process. After a crash, an interrupted reservation remains indeterminate and is not re-executed. A lost result may mean the command already ran. Do not create a fresh command ID to repeat a side effect without checking its state. Radio delivery under real packet loss remains a two-node hardware test.

## Flash and recovery

Before any write, review the exact image/hash, back up existing configuration, identify the selected runtime as T_DECK, then verify the ROM MAC matches that board. Do not scan/reset unrelated serial devices.

```sh

python tools/detect_tdeck.py --port YOUR_PORT --output .tdeck-device.json

python tools/flash_verified.py --port YOUR_ROM_PORT --expected-mac YOUR_VERIFIED_MAC --image YOUR_UPDATE.bin --sha256 REVIEWED_SHA256

```

The second command defaults to **inspection only**. Only after reviewing the image and confirming the write, add `--confirm-app-write`. It requires an ESP32-S3 ROM connection, matching MAC, 16MB flash and the expected image hash, then writes only the app at `0x10000` for this known partition layout. It does not erase flash or write a filesystem/factory image. Never use it on an unknown partition layout.

If a custom build fails to boot, use the preserved stock 2.7.15 app image through the same checked ROM path. Keep the configuration backup and original images. Windows ROM sync was previously unreliable even though normal serial/API operation works; diagnose that path rather than repeatedly issuing writes.

## Tests

```sh

python -m pip install ./companion[desktop] pytest pytest-asyncio

PYTHONPATH=companion pytest companion/tests

make test-core

```

Tests include auth/errors/body limits, simulated AI/PTY/desktop lifecycle, real loopback HTTP proxy traffic, the real VNC adapter against a small RFB test server, signed radio framing, replay/collision handling and concurrent execution reservations. Native C++ tests validate framing, CRC corruption and out-of-order reassembly.

## Remaining acceptance

- Release candidate compiled successfully; artifact hashes and source commits are recorded in the release manifest.

- App-only flash verified through JTAG; owner confirmed boot. See the dated status and media for subsequent tests.

- Keyboard, trackball, touch, saved profile reboot persistence, Wi-Fi reconnection, SD and Meshtastic messaging checked on hardware.

- Real dedicated-Pi Ollama and Linux PTY/SSH tested after power replacement.

- VNC against the chosen real desktop, two-radio mesh delivery, GPS, audio and battery behavior verified.

These are acceptance gates, not claims that the tests have already happened.
