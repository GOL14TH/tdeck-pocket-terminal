# Pocket Terminal wire protocol

The device/companion Wi-Fi transport uses authenticated WebSockets. Meshtastic fallback uses `PRIVATE_APP` (PortNum 256) with the compact frame below.

## Mesh frame (little-endian, 20-byte header)

| Field | Bytes | Notes |
|---|---:|---|
| magic | 2 | `0x5444` (`TD`) |
| version | 1 | `1` |
| kind | 1 | command request/ack/result/error |
| flags | 1 | reserved |
| reserved | 1 | zero |
| session | 2 | sender-chosen session id |
| message_id | 4 | idempotency and correlation key; non-zero |
| chunk_index | 1 | zero based |
| chunk_count | 1 | 1..255 |
| payload_len | 2 | bytes in this chunk |
| crc32 | 4 | CRC32 of this chunk payload |

The default mesh chunk payload is 160 bytes, keeping every encoded frame comfortably below Meshtastic's data payload ceiling and leaving headroom for future metadata.

### Kinds

* `1 CMD_REQUEST` — length-prefixed command name and arguments.
* `2 CMD_ACK` — complete request received and accepted for execution or deduplicated.
* `3 CMD_RESULT` — int16 exit status + UTF-8 output.
* `4 CMD_ERROR` — int16 error status + UTF-8 error text.

### Command request payload

`u8 command_name_len | command_name | u16 args_len | args_utf8`

The companion maps `command_name` to an allow-listed argv template. Raw shell execution is disabled by default.

### Command result payload

`i16 status | u16 text_len | text_utf8`

## Reliability and replay safety

1. Each Meshtastic packet is sent with `want_ack=true`, using Meshtastic's native retransmission machinery.
2. The application sends a `CMD_ACK` only after all chunks are assembled and validated.
3. The Raspberry Pi companion stores `(source_node, message_id)` results in SQLite. A repeated request returns the stored result and is never executed twice.
4. In-flight reassembly has a strict size limit and timeout.
5. High-risk raw-shell mode, if enabled by the operator, is separate from the default allow-list mode.
