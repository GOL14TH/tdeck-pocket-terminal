# Project status — 2026-09-08

App-only JTAG flash succeeded with OpenOCD Verify OK. The owner confirmed boot. Image SHA256: 81bf72d05b7afaf45ac5bf00287b3f4fe3aba421db628c8dd0680514a577ae32; size 3,586,896 bytes. ESP32-S3, 16MB flash, app offset 0x10000. Build used 143,388 bytes static RAM and 3,586,469 bytes app flash.

17 companion tests, 4 flash-guard tests and 2 native C++ tests passed before deployment. Real Pi5 companion tests then passed: Linux terminal marker, qwen3.5:4b reply in 46.5 seconds, and a 113,130-byte VNC tile frame. User services for companion and loopback WayVNC are enabled. No private tokens or credentials are included here.

The owner's new photos/videos demonstrate real handheld AI and desktop use but show intermittent Incomplete or oversized response errors. This is NOT a fully validated/error-free release. Read docs/KNOWN-ISSUES.md. No firmware changes were made in this documentation update.

See docs/INSTALL.md for reproducible setup and the Windows JTAG driver resolution, docs/MEDIA.md for privacy-reviewed desktop media. Public video copies have reduced resolution/bitrate and omit audio and metadata. Other computers is deferred. Two-radio mesh, GPS/audio/SD/power and longer reliability testing remain outstanding.


Public companion 0.2.1 adds an OpenAI-compatible adapter with server-side environment credentials. All 19 companion tests pass, including two new provider tests. This adapter has not been deployed to the original device setup or tested against a paid provider. Firmware is unchanged.
