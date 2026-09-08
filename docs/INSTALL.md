# Install the complete system

This guide covers the tested T-Deck Plus + Raspberry Pi 5 arrangement. The firmware is an experimental Meshtastic 2.7.15 integration. Read [known issues](KNOWN-ISSUES.md) before installing: the recorded handheld sessions show intermittent response errors.

## 1. Requirements and architecture

- LILYGO T-Deck Plus, ESP32-S3, 16 MB flash, USB data cable.
- Linux companion with Python 3.11+, a working power supply and LAN access.
- Ollama and a locally installed model for AI.
- An existing desktop/VNC server for desktop access. A headless OS alone does not provide a desktop.
- A second Meshtastic node only if you want the optional radio-command gateway.

The handheld sends authenticated HTTP requests to the companion on port 8787. The companion talks locally to Ollama, starts a Linux PTY, and converts VNC frames into small RGB565 tiles. Ordinary AI, terminal and desktop traffic uses Wi-Fi, not LoRa. local model here means the local `qwen3.5:4b` model; Discord history and council delegation are not included.

Clone this repository on both your build computer and the Linux companion:

```sh
git clone https://github.com/GOL14TH/tdeck-pocket-terminal.git
cd tdeck-pocket-terminal
```

Never commit your live token, Wi-Fi password, SSH password or configuration snapshots.

## 2. Build firmware

On Linux, install Git and Python with venv support, then:

```sh
bash tools/bootstrap_upstream.sh
bash tools/build_custom.sh
```

The bootstrap script fetches Meshtastic commit `567b8ea1c2b2d100c24b0d6cbc437ec89fae0a56` and its submodules, and installs PlatformIO 6.1.19/esptool 4.8.1. The first build downloads dependencies and can take a long time. The app is `.upstream/firmware/.pio/build/t-deck-tft/firmware.bin`. Do not substitute a factory image in app-only commands.

Windows: the tested helper `tools/build_windows.ps1 -WorkRoot <prepared-work-root>` expects `firmware-venv`, `firmware-2.7.15`, and `pio-stable` under that directory. It maps short paths under M: and sets TEMP/TMP there to avoid Windows LTO path failures. It is a helper for that prepared layout, not a fresh Windows installer. For a new setup, use the Linux build flow or prepare those directories with the same pinned source and PlatformIO version. `TESTED_FIRMWARE_DEPENDENCIES.json` records the libraries used in the successful build; this is not a guarantee of bit-identical future builds.

The tested app SHA-256 was `81bf72d05b7afaf45ac5bf00287b3f4fe3aba421db628c8dd0680514a577ae32`, size 3,586,896 bytes. Your rebuild may differ; calculate and use its actual hash.

## 3. Flash with serial, or the verified JTAG fallback

Identify the runtime first with `python tools/detect_tdeck.py --port YOUR_PORT`. Record the physical board's identity. Save configuration if desired. These app-only instructions require the known Meshtastic partition layout with an app at `0x10000` and capacity `0x640000`; do not use them blindly on another layout.

Enter download mode by holding the trackball while powering on/reconnecting USB, then release it. Follow [LILYGO's board instructions](https://github.com/Xinyuan-LilyGO/T-Deck). The port can change between runtime and ROM mode.

```sh
python tools/flash_verified.py --port YOUR_ROM_PORT --expected-mac YOUR_BOARD_MAC --image firmware.bin --sha256 YOUR_IMAGE_SHA256
# After the inspection passes, repeat with --confirm-app-write.
```

The guard checks the image hash, ESP32-S3 ROM MAC and 16 MB flash before writing the app. It does not erase the full device. Press RESET without holding the trackball afterward.

### Windows USB JTAG recovery (used successfully on this device)

Repeated serial write timeouts did not resolve by repeating the same command. JTAG initially failed with `LIBUSB_ERROR_NOT_FOUND`: the generic WinUSB interface lacked its interface GUID. Installing Espressif's driver fixed JTAG access. This does not prove every serial timeout has the same cause.

Follow [Espressif's official driver instructions](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/jtag-debugging/configure-builtin-jtag.html). From an administrator PowerShell, the documented installer is:

```powershell
Invoke-WebRequest https://dl.espressif.com/dl/idf-env/idf-env.exe -OutFile idf-env.exe
Get-AuthenticodeSignature .\idf-env.exe
.\idf-env.exe driver install --espressif
```

Verify a valid Espressif signature before running. The JTAG interface is `VID_303A&PID_1001&MI_02`; do not replace the serial interface (`MI_00`) with a JTAG driver.

Use Espressif OpenOCD; tested version was `v0.12.0-esp32-20260424`. Set `OPENOCD` to its executable and `SCRIPTS` to its `share/openocd/scripts` directory. Verify the selected serial belongs to your board. Start with an inspection:

```powershell
& $OPENOCD -s $SCRIPTS -f board/esp32s3-builtin.cfg `
  -c "adapter serial YOUR_BOARD_MAC" -c "adapter speed 4000" `
  -c "gdb port disabled" -c "tcl port disabled" -c "telnet port disabled" `
  -c "init; reset halt; flash probe 0; shutdown"
Get-FileHash .\firmware.bin -Algorithm SHA256
```

Confirm the target is ESP32-S3 and the flash probe reports 16384 KB. Confirm the known partition layout and reviewed image hash before the following write:

```powershell
& $OPENOCD -s $SCRIPTS -f board/esp32s3-builtin.cfg `
  -c "adapter serial YOUR_BOARD_MAC" -c "adapter speed 4000" `
  -c "gdb port disabled" -c "tcl port disabled" -c "telnet port disabled" `
  -c "program_esp firmware.bin 0x10000 verify; shutdown"
```

Require **Verify OK**, then physically press RESET without holding the trackball. The default 40000 kHz debugger speed produced transfer errors in our session; 4000 kHz succeeded. Stop on errors; do not erase the device to solve a communication problem. Recover with a known compatible stock **app** image at the same offset if needed. Firmware compilation and app verification do not replace on-device testing.

## 4. Install the Pi companion (tested desktop-user arrangement)

Run the following as the Linux user whose terminal and desktop you want to access, not as root. This exposes a shell with that user's privileges to holders of the companion token. Use a trusted LAN or configure the HTTPS support described in the main README.

```sh
sudo apt-get update
sudo apt-get install python3-venv
mkdir -p "$HOME/.local/share/tdeck-companion" "$HOME/.config/systemd/user"
python3 -m venv "$HOME/.local/share/tdeck-companion/venv"
"$HOME/.local/share/tdeck-companion/venv/bin/pip" install './companion[desktop]'
"$HOME/.local/share/tdeck-companion/venv/bin/python" - <<'PY'
import pathlib,secrets,yaml
b=pathlib.Path.home()/'.local/share/tdeck-companion'; p=b/'config.yaml'
if p.exists(): raise SystemExit('Configuration already exists; edit it instead of overwriting')
d={'token':secrets.token_urlsafe(18),'bind_host':'0.0.0.0','bind_port':8787,
   'state_db':str(b/'state.sqlite3'),'hosts':[{'id':'local','name':'Local model',
   'ai_url':'http://127.0.0.1:11434','ai_model':'qwen3.5:4b',
   'terminal_target':None,'vnc_host':None}]}
p.write_text(yaml.safe_dump(d)); p.chmod(0o600)
PY
cat > "$HOME/.config/systemd/user/tdeck-companion.service" <<EOF
[Unit]
Description=T-Deck companion
After=network-online.target
[Service]
WorkingDirectory=$HOME/.local/share/tdeck-companion
Environment=TDECK_COMPANION_CONFIG=$HOME/.local/share/tdeck-companion/config.yaml
ExecStart=$HOME/.local/share/tdeck-companion/venv/bin/tdeck-companion
Restart=on-failure
RestartSec=3
UMask=0077
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now tdeck-companion
sudo loginctl enable-linger "$USER"
curl http://127.0.0.1:8787/health
```

If a firewall is enabled, permit TCP 8787 only from your trusted LAN. Do not port-forward the shell/desktop companion to the Internet. For a dedicated restricted service account, use the alternative `companion/install.sh` flow in the README instead; do not install both on the same port. That account does not automatically have access to your logged-in desktop or SSH keys.

## 5. Local AI / local model

If Ollama already hosts local model, reuse it. Check `ollama list` and select the exact installed model name. For a new machine, install Ollama from [its official Linux instructions](https://docs.ollama.com/linux), then run `ollama pull qwen3.5:4b`. This downloads a multi-gigabyte model; use a machine with adequate RAM and stable power.

The companion's `ai_url` can remain loopback; Ollama does not need to be exposed to the LAN. Its model setting lives in `config.yaml`. After changes, run `systemctl --user restart tdeck-companion`. The tested Pi5 reply took 46.5 seconds. The current client sends individual prompts, disables thinking, and limits output to 256 tokens; it does not provide local model's Discord memory, tools or agent routing.

## 6. Pi desktop using the existing Wayland session

The tested Pi had a running labwc desktop at `/run/user/1000/wayland-0` and `wayvnc` already installed. On Raspberry Pi OS Desktop, install `wayvnc` if missing. A headless Lite installation needs a desktop/compositor configured separately. Confirm your actual `WAYLAND_DISPLAY` before proceeding; do not assume `wayland-0` on every machine.

Create `~/.local/share/tdeck-companion/wayvnc.conf`:

```ini
address=127.0.0.1
port=5901
enable_auth=false
```

This unauthenticated VNC listener is **loopback only**. The LAN-facing companion requires its token. Create `~/.config/systemd/user/tdeck-desktop.service`, replacing `/home/YOUR_USER` with your home directory:

```ini
[Unit]
Description=Local desktop bridge for T-Deck
After=graphical-session.target
[Service]
Environment=WAYLAND_DISPLAY=wayland-0
ExecStart=/usr/bin/wayvnc -C /home/YOUR_USER/.local/share/tdeck-companion/wayvnc.conf -f 5 -r 127.0.0.1 5901
Restart=on-failure
RestartSec=5
[Install]
WantedBy=default.target
```

In the `local` host entry of companion `config.yaml`, set `vnc_host: 127.0.0.1` and `vnc_port: 5901`. Then:

```sh
systemctl --user daemon-reload
systemctl --user enable --now tdeck-desktop
systemctl --user restart tdeck-companion
ss -ltn | grep 5901
```

The desktop session must remain active; this service does not create one. For another VNC server, set its host/port/password instead, provided its authentication is supported by vncdotool. Other computers deployment has not been tested.

## 7. Handheld setup and controls

1. Open Apps → Wi-Fi, enter your LAN SSID/password, save, then Apply + restart.
2. Open Hosts. Set a name, base URL `http://YOUR_PI_LAN_IP:8787`, host ID `local`, and the token from the Pi's private config. Save and tap Test link. Do not put your SSH password in the token field.
3. AI: enter a prompt and tap Send. Wait for the asynchronous reply.
4. Terminal: entering the screen starts a shell. Enter `hostname` or `pwd` and tap Send. Ctrl-C interrupts a command; Tab/Esc send control keys. Full-screen editors are not a supported reliable workflow yet.
5. Desktop: entering the screen opens the configured desktop. Tap to click; use the keyboard to type into the focused desktop control. Arrow buttons pan the viewport. Full mouse dragging and a full-screen remote resolution are not implemented.
6. Back returns to the launcher; stock Meshtastic remains available.

For a terminal on a different Linux host, set `terminal_target: user@host` and configure that companion user's SSH keys and verified known_hosts. The T-Deck does not implement a standalone native SSH client.

## 8. Optional mesh gateway, simulation, maintenance

See the main README's mesh section for second-node wiring, `mesh_serial`/`mesh_tcp`, node allowlist, HMAC key and command allowlist. Install `./companion[mesh]` only if using that gateway. Real two-radio delivery/retry testing remains outstanding.

For a no-hardware demo, install `./companion` into a local venv and run `python -m tdeck_companion.simulator`; open `http://127.0.0.1:8788`. Simulation never runs shell commands or model inference.

```sh
systemctl --user status tdeck-companion tdeck-desktop
journalctl --user -u tdeck-companion -n 60 --no-pager
journalctl --user -u tdeck-desktop -n 60 --no-pager
# Stop the installed services:
systemctl --user disable --now tdeck-companion tdeck-desktop
```

Keep logs/configuration private when sharing diagnostics. A token grants terminal and desktop access. To rotate it, generate a new random token in the Pi config, restart the companion, and update the handheld host profile.
