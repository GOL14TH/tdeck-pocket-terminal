import asyncio, struct, sys
import pytest
from fastapi.testclient import TestClient
from tdeck_companion.app import create_app
from tdeck_companion.config import Settings, HostProfile, load_settings
from tdeck_companion.commands import CommandExecutor
from tdeck_companion.mesh_gateway import seal, unseal
from tdeck_companion.protocol import Kind

AUTH = {"Authorization": "Bearer " + "x" * 32}

def test_simulation_roundtrip(tmp_path):
    settings = Settings(
        token="x" * 32,
        simulation=True,
        hosts=[HostProfile(id="pi", name="Pi")],
        state_db=str(tmp_path / "state.db"),
    )
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/hosts").status_code == 401
        assert c.get("/api/hosts", headers=AUTH).json()[0]["simulation"] is True
        assert c.post("/api/v1/terminal/missing", headers=AUTH).status_code == 404
        sid = c.post("/api/v1/terminal/pi", headers=AUTH).text
        assert (
            "SIMULATION"
            in c.get(f"/api/v1/terminal/session/{sid}/read", headers=AUTH).text
        )
        assert (
            c.post(
                f"/api/v1/terminal/session/{sid}/write",
                headers=AUTH,
                content=b"whoami\r",
            ).status_code
            == 204
        )
        assert (
            "[simulated] whoami"
            in c.get(f"/api/v1/terminal/session/{sid}/read", headers=AUTH).text
        )
        jid = c.post("/api/v2/ai/pi", headers=AUTH, content="hello").text
        import time

        for _ in range(20):
            r = c.get(f"/api/v2/ai/job/{jid}", headers=AUTH)
            if r.status_code != 202:
                break
            time.sleep(0.01)
        assert r.status_code == 200 and "SIMULATION" in r.text
        assert (
            c.post("/api/v2/ai/pi", headers=AUTH, content=b"x" * 9000).status_code
            == 413
        )
        ds = c.post("/api/v2/desktop/pi", headers=AUTH).text
        frame = c.get(f"/api/v2/desktop/session/{ds}/frame", headers=AUTH).content
        magic, x, y, count = struct.unpack_from("<4sHHH", frame)
        assert magic == b"TDT2" and count == 60
        pos = 10
        for _ in range(count):
            tx, ty, w, h = struct.unpack_from("<HHHH", frame, pos)
            pos += 8 + w * h * 2
            assert tx + w <= 320 and ty + h <= 176
        assert pos == len(frame)
        second = c.get(f"/api/v2/desktop/session/{ds}/frame", headers=AUTH).content
        assert len(second) == 10
        assert (
            c.delete(f"/api/v1/terminal/session/{sid}", headers=AUTH).status_code == 204
        )
        assert (
            c.get(f"/api/v1/terminal/session/{sid}/read", headers=AUTH).status_code
            == 404
        )
        assert (
            c.delete(f"/api/v2/desktop/session/{ds}", headers=AUTH).status_code == 204
        )

@pytest.mark.asyncio
async def test_concurrent_retry_cannot_execute_twice(tmp_path):
    output = tmp_path / "effect.txt"
    script = (
        "import pathlib,time; p=pathlib.Path("
        + repr(str(output))
        + '); p.open("a").write("once\\n"); time.sleep(.1); print("done")'
    )
    e = CommandExecutor(str(tmp_path / "db"), {"run": [sys.executable, "-c", script]})
    results = await asyncio.gather(
        e.execute(42, 1, "run", ""), e.execute(42, 1, "run", "")
    )
    assert output.read_text() == "once\n"
    assert sorted(r[2] for r in results) == [False, True]
    assert (await e.execute(42, 1, "run", ""))[0] == 0
    assert (await e.execute(42, 1, "run", "changed"))[0] == 126

def test_mesh_mac_binds_identity():
    key = "x" * 32
    p = seal(key, 42, Kind.COMMAND_REQUEST, 7, 9, b"test")
    assert unseal(key, 42, Kind.COMMAND_REQUEST, 7, 9, p) == b"test"
    for source, session, msg in [(43, 7, 9), (42, 8, 9), (42, 7, 10)]:
        with pytest.raises(ValueError):
            unseal(key, source, Kind.COMMAND_REQUEST, session, msg, p)

def test_no_default_token(tmp_path, monkeypatch):
    monkeypatch.delenv("TDECK_COMPANION_TOKEN", raising=False)
    with pytest.raises(ValueError):
        load_settings(str(tmp_path / "missing.yaml"))
