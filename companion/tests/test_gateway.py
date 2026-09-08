import asyncio, time
import pytest
from tdeck_companion.mesh_gateway import MeshCommandGateway, seal, unseal
from tdeck_companion.protocol import (
    Kind,
    chunk_payload,
    encode_command_request,
    decode_frame,
    Reassembler,
    decode_command_result,
)
from tdeck_companion.commands import CommandExecutor
import sys

class Radio:
    def __init__(self):
        self.sent = []

    def sendData(self, data, **kwargs):
        self.sent.append(data)

@pytest.mark.asyncio
async def test_mesh_signed_round_trip_reorder_and_replay(tmp_path):
    radio = Radio()
    executor = CommandExecutor(
        str(tmp_path / "db"), {"echo": [sys.executable, "-c", 'print("mesh works")']}
    )
    gateway = MeshCommandGateway(radio, executor, "k" * 32, [42])
    body = seal(
        "k" * 32,
        42,
        Kind.COMMAND_REQUEST,
        4,
        9,
        encode_command_request("echo", "a" * 200),
    )
    frames = chunk_payload(Kind.COMMAND_REQUEST, 4, 9, body)
    for raw in reversed(frames):
        gateway.ingest({"from": 42, "decoded": {"portnum": 256, "payload": raw}})
    await asyncio.gather(*list(gateway.tasks))
    reassembler = Reassembler()
    values = []
    for raw in radio.sent:
        f = decode_frame(raw)
        p = reassembler.ingest(f)
        if p is not None:
            p = unseal("k" * 32, 42, f.kind, f.session, f.message_id, p)
            if f.kind == Kind.COMMAND_RESULT:
                values.append(decode_command_result(p))
    assert values == [
        (0, "mesh works\r\n" if sys.platform == "win32" else "mesh works\n")
    ]
    before = len(radio.sent)
    for raw in frames:
        gateway.ingest({"from": 43, "decoded": {"portnum": 256, "payload": raw}})
    assert len(radio.sent) == before and not gateway.inflight

@pytest.mark.asyncio
async def test_unsigned_mesh_does_not_execute(tmp_path):
    radio = Radio()
    gateway = MeshCommandGateway(
        radio, CommandExecutor(str(tmp_path / "db"), {}), "k" * 32, [42]
    )
    for raw in chunk_payload(
        Kind.COMMAND_REQUEST, 1, 1, encode_command_request("raw", "bad")
    ):
        gateway.ingest({"from": 42, "decoded": {"portnum": 256, "payload": raw}})
    assert not gateway.tasks and not radio.sent

@pytest.mark.asyncio
async def test_abandoned_reservation_never_reexecutes(tmp_path):
    import sqlite3, hashlib, json

    path = str(tmp_path / "db")
    e = CommandExecutor(path, {"noop": [sys.executable, "-c", 'print("NO")']})
    digest = hashlib.sha256(json.dumps(["noop", ""]).encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO executions VALUES(?,?,?,?,?,?,?,?)",
            (42, 0, 9, digest, "pending", 125, "", time.time()),
        )
    status, out, cached = await e.execute(42, 9, "noop", "")
    assert status == 125 and cached and "will not execute again" in out
