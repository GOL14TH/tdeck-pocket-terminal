"""PRIVATE_APP gateway. HMAC authenticates source/session/id/kind and payload."""

from __future__ import annotations
from .protocol import *
from .commands import CommandExecutor
import asyncio, hashlib, hmac, struct, time

def seal(key, source, kind, session, msg, payload):
    header = struct.pack("<IBHI", source, int(kind), session, msg)
    return payload + hmac.digest(key.encode(), header + payload, "sha256")

def unseal(key, source, kind, session, msg, payload):
    if len(payload) < 32:
        raise ValueError("unsigned payload")
    body = payload[:-32]
    if not hmac.compare_digest(
        seal(key, source, kind, session, msg, body)[-32:], payload[-32:]
    ):
        raise ValueError("invalid signature")
    return body

class MeshCommandGateway:
    def __init__(self, interface, executor, key, allowed_nodes, loop=None):
        self.interface = interface
        self.executor = executor
        self.key = key
        self.allowed = set(allowed_nodes)
        self.loop = loop or asyncio.get_running_loop()
        self.rx = {}
        self.tasks = set()
        self.inflight = set()
        self.closed = False

    def on_packet(self, packet, interface=None):
        if not self.closed:
            self.loop.call_soon_threadsafe(self.ingest, packet)

    def ingest(self, packet):
        dec = packet.get("decoded") or {}
        source = int(packet.get("from", 0))
        if source not in self.allowed or dec.get("portnum") not in ("PRIVATE_APP", 256):
            return
        try:
            f = decode_frame(dec.get("payload") or b"")
            if f.kind != Kind.COMMAND_REQUEST:
                return
            now = time.monotonic()
            self.rx = {k: v for k, v in self.rx.items() if now - v[0] < 120}
            key = (source, f.session, f.message_id)
            if key not in self.rx:
                if len(self.rx) >= 16:
                    return
                self.rx[key] = (now, Reassembler())
            payload = self.rx[key][1].ingest(f)
            if payload is None:
                return
            self.rx.pop(key, None)
            payload = unseal(self.key, source, f.kind, f.session, f.message_id, payload)
            if key in self.inflight or len(self.inflight) >= 4:
                return
            self.inflight.add(key)
            task = asyncio.create_task(self._execute(source, packet, f, payload))
            self.tasks.add(task)

            def done(t):
                self.tasks.discard(t)
                self.inflight.discard(key)
                if not t.cancelled():
                    t.exception()

            task.add_done_callback(done)
        except (ValueError, TypeError, KeyError):
            return

    async def send(self, source, channel, f, kind, payload):
        payload = seal(self.key, source, kind, f.session, f.message_id, payload)
        for b in chunk_payload(kind, f.session, f.message_id, payload):
            await asyncio.to_thread(
                self.interface.sendData,
                b,
                destinationId=source,
                portNum="PRIVATE_APP",
                wantAck=True,
                channelIndex=channel,
            )

    async def _execute(self, source, packet, f, payload):
        command, args = decode_command_request(payload)
        channel = int(packet.get("channel", 0))
        await self.send(source, channel, f, Kind.COMMAND_ACK, b"")
        status, text, _ = await self.executor.execute(
            source, f.message_id, command, args, session=f.session
        )
        await self.send(
            source, channel, f, Kind.COMMAND_RESULT, encode_command_result(status, text)
        )

    async def close(self):
        self.closed = True
        from pubsub import pub

        pub.unsubscribe(self.on_packet, "meshtastic.receive")
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await asyncio.to_thread(self.interface.close)

async def start_gateway(settings):
    if not settings.mesh_key or not settings.mesh_allowed_nodes:
        raise ValueError("Mesh requires key and allowed nodes")
    if settings.mesh_serial and settings.mesh_tcp:
        raise ValueError("Select serial or TCP mesh connection")
    from pubsub import pub

    if settings.mesh_serial:
        from meshtastic.serial_interface import SerialInterface

        interface = await asyncio.to_thread(
            SerialInterface, devPath=settings.mesh_serial
        )
    else:
        from meshtastic.tcp_interface import TCPInterface

        interface = await asyncio.to_thread(TCPInterface, hostname=settings.mesh_tcp)
    gateway = MeshCommandGateway(
        interface,
        CommandExecutor(
            settings.state_db, settings.command_allowlist, settings.raw_shell_enabled
        ),
        settings.mesh_key,
        settings.mesh_allowed_nodes,
    )
    pub.subscribe(gateway.on_packet, "meshtastic.receive")
    return gateway
