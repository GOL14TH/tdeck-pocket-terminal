from __future__ import annotations
import binascii, struct, time
from dataclasses import dataclass, field
from enum import IntEnum

MAGIC = 0x5444
VERSION = 1
HEADER = struct.Struct("<HBBBBHIBBHI")
MAX_REASSEMBLED = 4096

class Kind(IntEnum):
    COMMAND_REQUEST = 1
    COMMAND_ACK = 2
    COMMAND_RESULT = 3
    COMMAND_ERROR = 4

@dataclass
class Frame:
    kind: Kind
    session: int
    message_id: int
    chunk_index: int = 0
    chunk_count: int = 1
    payload: bytes = b""
    flags: int = 0

def encode_frame(f: Frame) -> bytes:
    if (
        not f.message_id
        or not (1 <= f.chunk_count <= 255)
        or not (0 <= f.chunk_index < f.chunk_count)
    ):
        raise ValueError("bad frame")
    crc = binascii.crc32(f.payload) & 0xFFFFFFFF
    return (
        HEADER.pack(
            MAGIC,
            VERSION,
            int(f.kind),
            f.flags,
            0,
            f.session & 0xFFFF,
            f.message_id & 0xFFFFFFFF,
            f.chunk_index,
            f.chunk_count,
            len(f.payload),
            crc,
        )
        + f.payload
    )

def decode_frame(b: bytes) -> Frame:
    if len(b) < HEADER.size:
        raise ValueError("short frame")
    magic, ver, kind, flags, _r, session, msg, idx, count, n, crc = HEADER.unpack_from(
        b
    )
    if (
        magic != MAGIC
        or ver != VERSION
        or not msg
        or not count
        or idx >= count
        or len(b) != HEADER.size + n
    ):
        raise ValueError("bad header")
    p = b[HEADER.size :]
    if binascii.crc32(p) & 0xFFFFFFFF != crc:
        raise ValueError("crc")
    return Frame(Kind(kind), session, msg, idx, count, p, flags)

def chunk_payload(
    kind: Kind, session: int, msg: int, payload: bytes, max_payload: int = 160
):
    count = max(1, (len(payload) + max_payload - 1) // max_payload)
    if count > 255:
        raise ValueError("too large")
    return [
        encode_frame(
            Frame(
                kind,
                session,
                msg,
                i,
                count,
                payload[i * max_payload : (i + 1) * max_payload],
            )
        )
        for i in range(count)
    ]

def encode_command_request(command: str, args: str) -> bytes:
    c = command.encode()
    a = args.encode()
    if not c or len(c) > 255 or len(a) > 65535:
        raise ValueError("bad command")
    return bytes([len(c)]) + c + struct.pack("<H", len(a)) + a

def decode_command_request(p: bytes):
    if len(p) < 3:
        raise ValueError("short request")
    n = p[0]
    if not n or len(p) < 1 + n + 2:
        raise ValueError("bad request")
    alen = struct.unpack_from("<H", p, 1 + n)[0]
    if len(p) != 1 + n + 2 + alen:
        raise ValueError("bad request size")
    return p[1 : 1 + n].decode(), p[1 + n + 2 :].decode()

def encode_command_result(status: int, text: str) -> bytes:
    t = text.encode(errors="replace")[:65535]
    return struct.pack("<hH", status, len(t)) + t

def decode_command_result(p: bytes):
    if len(p) < 4:
        raise ValueError("short result")
    status, n = struct.unpack_from("<hH", p)
    if len(p) != 4 + n:
        raise ValueError("bad result size")
    return status, p[4:].decode(errors="replace")

@dataclass
class Reassembler:
    key: tuple | None = None
    started: float = 0
    count: int = 0
    chunks: dict[int, bytes] = field(default_factory=dict)

    def ingest(self, f: Frame):
        key = (f.kind, f.session, f.message_id, f.chunk_count)
        if self.key != key or time.monotonic() - self.started > 120:
            self.key = key
            self.started = time.monotonic()
            self.count = f.chunk_count
            self.chunks = {}
        self.chunks.setdefault(f.chunk_index, f.payload)
        if sum(map(len, self.chunks.values())) > MAX_REASSEMBLED:
            self.key = None
            self.chunks = {}
            raise ValueError("reassembly too large")
        if len(self.chunks) != self.count:
            return None
        out = b"".join(self.chunks[i] for i in range(self.count))
        self.key = None
        self.chunks = {}
        return out
