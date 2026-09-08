import importlib.util, hashlib, sys

from pathlib import Path

from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]

def module():

    spec = importlib.util.spec_from_file_location(

        "flash_verified", ROOT / "tools/flash_verified.py"

    )

    m = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(m)

    return m

def invoke(tmp_path, monkeypatch, write=False, bad_hash=False, bad_mac=False):

    m = module()

    data = b"\xe9" + b"\0" * 31

    image = tmp_path / "app.bin"

    image.write_bytes(data)

    calls = []

    def run(argv, **kwargs):

        calls.append(argv)

        result = (

            "MAC: 11:22:33:44:55:66\nMAC: 11:22:33:44:55:66"

            if "read_mac" in argv

            else (

                "Detected flash size: 16MB"

                if "flash_id" in argv

                else "Hash of data verified."

            )

        )

        return SimpleNamespace(returncode=0, stdout=result, stderr="")

    monkeypatch.setattr(m.subprocess, "run", run)

    argv = [

        "flash_verified",

        "--port",

        "FAKE",

        "--expected-mac",

        "00:00:00:00:00:00" if bad_mac else "11:22:33:44:55:66",

        "--image",

        str(image),

        "--sha256",

        "bad" if bad_hash else hashlib.sha256(data).hexdigest(),

    ]

    if write:

        argv.append("--confirm-app-write")

    monkeypatch.setattr(sys, "argv", argv)

    return m, calls

def test_inspection_never_writes(tmp_path, monkeypatch):

    m, calls = invoke(tmp_path, monkeypatch)

    m.main()

    assert len(calls) == 2 and all("write_flash" not in call for call in calls)

def test_bad_hash_never_touches_device(tmp_path, monkeypatch):

    m, calls = invoke(tmp_path, monkeypatch, bad_hash=True)

    with pytest.raises(SystemExit):

        m.main()

    assert not calls

def test_wrong_mac_refuses_write(tmp_path, monkeypatch):

    m, calls = invoke(tmp_path, monkeypatch, write=True, bad_mac=True)

    with pytest.raises(SystemExit):

        m.main()

    assert len(calls) == 1

def test_approved_path_only_writes_app(tmp_path, monkeypatch):

    m, calls = invoke(tmp_path, monkeypatch, write=True)

    m.main()

    assert calls[-1][-3:-1] == ["write_flash", "0x10000"]

    assert all("erase_flash" not in call for call in calls)
