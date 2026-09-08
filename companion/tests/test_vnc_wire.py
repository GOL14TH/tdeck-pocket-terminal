"""Real RFB wire round trip against a minimal local test server, not a desktop mock."""

import asyncio, struct
import pytest
from tdeck_companion.desktop import VncBackend

@pytest.mark.asyncio
async def test_vnc_adapter_wire_roundtrip():
    inputs = []
    connections = set()

    async def serve(reader, writer):
        connections.add(writer)
        try:
            writer.write(b"RFB 003.008\n")
            await writer.drain()
            await reader.readexactly(12)
            writer.write(b"\x01\x01")
            await writer.drain()
            await reader.readexactly(1)
            writer.write(b"\0" * 4)
            await writer.drain()
            await reader.readexactly(1)
            fmt = struct.pack(">BBBBHHHBBB3x", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
            writer.write(
                struct.pack(">HH", 64, 48) + fmt + struct.pack(">I", 4) + b"Test"
            )
            await writer.drain()
            while True:
                kind = (await reader.readexactly(1))[0]
                if kind == 0:
                    raw = await reader.readexactly(19)
                    fmt = raw[3:]
                elif kind == 2:
                    raw = await reader.readexactly(3)
                    count = struct.unpack_from(">H", raw, 1)[0]
                    await reader.readexactly(4 * count)
                elif kind == 3:
                    await reader.readexactly(9)
                    bpp, depth, bigend, truecolor, rmax, gmax, bmax, rs, gs, bs = (
                        struct.unpack(">BBBBHHHBBB3x", fmt)
                    )
                    pixel = (rmax << rs).to_bytes(
                        bpp // 8, "big" if bigend else "little"
                    )
                    writer.write(
                        struct.pack(">BBHHHHHi", 0, 0, 1, 0, 0, 64, 48, 0)
                        + pixel * (64 * 48)
                    )
                    await writer.drain()
                elif kind == 4:
                    inputs.append(("key", await reader.readexactly(7)))
                elif kind == 5:
                    inputs.append(("pointer", await reader.readexactly(5)))
                elif kind == 6:
                    raw = await reader.readexactly(7)
                    await reader.readexactly(struct.unpack_from(">I", raw, 3)[0])
                else:
                    raise AssertionError(f"unexpected RFB message {kind}")
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()
            connections.discard(writer)

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    backend = VncBackend("127.0.0.1", server.sockets[0].getsockname()[1])
    try:
        await backend.connect()
        image = await asyncio.wait_for(backend.snapshot(), 12)
        assert image.size == (64, 48) and image.getpixel((0, 0)) == (255, 0, 0)
        await backend.pointer(10, 12, 1)
        await backend.key("a")
        await asyncio.sleep(0.05)
        assert any(x[0] == "pointer" for x in inputs) and any(
            x[0] == "key" for x in inputs
        )
    finally:
        await backend.close()
        server.close()
        await server.wait_closed()
        for writer in list(connections):
            writer.close()
