"""Bounded authenticated desktop sessions for the embedded REST client."""

import asyncio, secrets, time, struct

from dataclasses import dataclass, field

from .desktop import VncBackend, changed_tiles, rgb565be

from .simulation import SimDesktop

@dataclass

class Session:

    backend: object

    touched: float = field(default_factory=time.monotonic)

    previous: object = None

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

class DesktopManager:

    def __init__(self, simulation=False):

        self.sessions = {}

        self.simulation = simulation

        self.guard = asyncio.Lock()

    async def create(self, host):

        async with self.guard:

            if len(self.sessions) >= 2:

                raise RuntimeError("desktop session limit reached")

            if not self.simulation and not host.vnc_host:

                raise ValueError("No VNC host configured")

            backend = (SimDesktop if self.simulation else VncBackend)(

                host.vnc_host, host.vnc_port, host.vnc_password

            )

            backend = await asyncio.wait_for(backend.connect(), 10)

            sid = secrets.token_hex(12)

            self.sessions[sid] = Session(backend)

            return sid

    async def frame(self, sid, x, y, reset=False):

        s = self.sessions[sid]

        async with s.lock:

            s.touched = time.monotonic()

            full = await asyncio.wait_for(s.backend.snapshot(), 10)

            x = max(0, min(x, max(0, full.width - 320)))

            y = max(0, min(y, max(0, full.height - 176)))

            from PIL import Image

            crop = Image.new("RGB", (320, 176))

            crop.paste(

                full.crop((x, y, min(x + 320, full.width), min(y + 176, full.height))),

                (0, 0),

            )

            tiles = changed_tiles(None if reset else s.previous, crop, 32)

            result = bytearray(struct.pack("<4sHHH", b"TDT2", x, y, len(tiles)))

            for (x0, y0, x1, y1), tile in tiles:

                result.extend(

                    struct.pack("<HHHH", x0, y0, x1 - x0, y1 - y0) + rgb565be(tile)

                )

            s.previous = crop

            return bytes(result)

    async def input(self, sid, event):

        s = self.sessions[sid]

        async with s.lock:

            s.touched = time.monotonic()

            if event.get("type") == "key":

                await s.backend.key(str(event.get("key", ""))[:32])

            elif event.get("type") == "pointer":

                await s.backend.pointer(

                    max(0, min(65535, int(event.get("x", 0)))),

                    max(0, min(65535, int(event.get("y", 0)))),

                    int(event.get("buttons", 0)) & 7,

                )

            else:

                raise ValueError("unknown input type")

    async def close(self, sid):

        s = self.sessions.pop(sid, None)

        if s:

            async with s.lock:

                await s.backend.close()

    async def reap(self):

        for sid, s in list(self.sessions.items()):

            if time.monotonic() - s.touched > 120:

                await self.close(sid)

    async def close_all(self):

        for sid in list(self.sessions):

            await self.close(sid)
