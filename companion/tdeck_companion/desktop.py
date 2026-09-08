from __future__ import annotations

import asyncio, io, struct

from PIL import Image, ImageChops

TILE_HDR = struct.Struct("<4sBHHHHI")  # magic,fmt,x,y,w,h,seq ; fmt 1=RGB565BE

def rgb565be(img: Image.Image) -> bytes:

    out = bytearray()

    px = img.convert("RGB").load()

    w, h = img.size

    for y in range(h):

        for x in range(w):

            r, g, b = px[x, y]

            v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

            out += bytes((v >> 8, v & 255))

    return bytes(out)

def changed_tiles(prev: Image.Image | None, cur: Image.Image, tile=32):

    if prev is None:

        box = (0, 0, *cur.size)

    else:

        diff = ImageChops.difference(prev, cur)

        box = diff.getbbox()

        if box is None:

            return []

    x0, y0, x1, y1 = box

    out = []

    for y in range((y0 // tile) * tile, y1, tile):

        for x in range((x0 // tile) * tile, x1, tile):

            b = (x, y, min(x + tile, cur.width), min(y + tile, cur.height))

            out.append((b, cur.crop(b)))

    return out

class VncBackend:

    def __init__(self, host, port=5900, password=None):

        self.host = host

        self.port = port

        self.password = password

        self.client = None

    async def connect(self):

        try:

            from vncdotool import api

        except ImportError as e:

            raise RuntimeError(

                "install tdeck-companion[desktop] for VNC support"

            ) from e

        self.client = await asyncio.to_thread(

            api.connect, f"{self.host}::{self.port}", password=self.password, timeout=8

        )

        return self

    async def snapshot(self) -> Image.Image:

        import tempfile, os

        fd, path = tempfile.mkstemp(suffix=".png")

        os.close(fd)

        try:

            await asyncio.to_thread(self.client.captureScreen, path)

            with Image.open(path) as image:

                return image.convert("RGB").copy()

        finally:

            try:

                os.unlink(path)

            except OSError:

                pass

    async def pointer(self, x, y, buttons=0):

        await asyncio.to_thread(self.client.mouseMove, x, y)

        for bit, button in ((1, 1), (2, 2), (4, 3)):

            if buttons & bit:

                await asyncio.to_thread(self.client.mousePress, button)

    async def key(self, key):

        await asyncio.to_thread(self.client.keyPress, "space" if key == " " else key)

    async def close(self):

        if self.client:

            await asyncio.to_thread(self.client.disconnect)
