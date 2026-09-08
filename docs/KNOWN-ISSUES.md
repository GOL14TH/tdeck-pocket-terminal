# Known issues and hardware evidence — 2026-09-08

The app was flashed at 0x10000 through Espressif OpenOCD with **Verify OK**, then booted successfully according to the owner. Live Pi5 API tests passed for a Linux terminal command, local `qwen3.5:4b` inference (46.5 seconds), and a real 113,130-byte desktop tile frame.

The owner's photos and videos additionally demonstrate on-device AI text and desktop interaction. They also show repeated **Incomplete or oversized response** / **Link -1** errors, including after terminal control input. These recordings are evidence of partial functionality, not a clean acceptance pass.

The current firmware uses one generic error for HTTP body read failures, buffer allocation failure and size overflow. The photos alone cannot establish which happened. Investigate HTTP 204/empty response handling, actual read error codes, content length, allocation and connection timeouts. Do not simply raise the maximum body size or disable the bounds checks. A fix must be tested against the handheld before being labelled resolved.

Other boundaries: line-oriented terminal rather than full VT100; desktop viewport with panning rather than full mouse dragging; AI model access rather than Discord-agent memory; real two-node mesh retries, GPS/audio/SD/power acceptance remain incomplete. No fix for these observed response errors is included in this documentation/media update.

See [demo gallery](MEDIA.md) and [installation guide](INSTALL.md).
