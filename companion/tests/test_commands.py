import pytest
from tdeck_companion.commands import CommandExecutor

@pytest.mark.asyncio
async def test_command_idempotency(tmp_path):
    e = CommandExecutor(
        str(tmp_path / "state.db"),
        {
            "echo": [
                __import__("sys").executable,
                "-c",
                "import sys;print(sys.argv[1])",
                "{args}",
            ]
        },
        False,
    )
    status, out, cached = await e.execute(42, 1001, "echo", "hello")
    assert status == 0 and out.strip() == "hello" and cached is False
    status2, out2, cached2 = await e.execute(42, 1001, "echo", "hello")
    assert (status2, out2, cached2) == (status, out, True)

@pytest.mark.asyncio
async def test_disallowed_command_not_executed(tmp_path):
    e = CommandExecutor(str(tmp_path / "state.db"), {}, False)
    status, out, cached = await e.execute(1, 2, "raw", "touch /tmp/should-not-exist")
    assert status == 126 and "not allowed" in out and cached is False
