# Third-party / open-source references

This project deliberately keeps current Meshtastic firmware as the upstream base and does not vendor whole third-party projects into this repository.

- **Meshtastic firmware** — primary firmware base and API compatibility target; GPL-3.0.
- **LILYGO T-Deck official repository** — hardware definitions, factory/unit-test references and recovery procedure reference.
- **T-UI (`jeeab/t-ui-firmware`)** — GPL-3.0 Meshtastic-derived T-Deck launcher; reference for launcher/file/Wi-Fi UX patterns.
- **NeoDeck (`justynroberts/NeoDeck`)** — T-Deck Plus SSH/terminal implementation reference. It demonstrates that native libssh is possible, but this project defaults to a Linux companion to preserve Meshtastic RAM/stack headroom.
- **bmorcelli Launcher** — T-Deck firmware launcher/recovery workflow reference.
- **vncdotool** — VNC/RFB client used on the Linux companion side.
- **Ollama** — local AI service compatible with the companion `/api/chat` proxy.

No source from T-UI or NeoDeck has been copied into the PocketTerminal module. If code is later ported, preserve its original license and notices and document the exact source commit here.
