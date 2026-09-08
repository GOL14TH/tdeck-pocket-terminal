"""Durable at-most-once execution. A crash leaves an indeterminate reservation."""

from __future__ import annotations
import asyncio, hashlib, json, sqlite3, time, os, signal
from pathlib import Path

class CommandExecutor:
    def __init__(self, db_path, allowlist, raw_shell=False):
        self.db_path = db_path
        self.allowlist = allowlist
        self.raw_shell = raw_shell
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS executions (source INTEGER, session INTEGER, msg INTEGER, digest TEXT, state TEXT, status INTEGER, output TEXT, ts REAL, PRIMARY KEY(source,session,msg))"
            )

    async def execute(self, source, msg, command, args, session=0):
        if not msg:
            return 126, "invalid message ID", False
        digest = hashlib.sha256(json.dumps([command, args]).encode()).hexdigest()
        with sqlite3.connect(self.db_path, timeout=5) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT digest,state,status,output FROM executions WHERE source=? AND session=? AND msg=?",
                (source, session, msg),
            ).fetchone()
            if row:
                if row[0] != digest:
                    return 126, "message ID reused with different content", True
                if row[1] != "done":
                    return (
                        125,
                        "execution pending or interrupted; will not execute again",
                        True,
                    )
                return row[2], row[3], True
            if command == "raw" and self.raw_shell:
                argv = ["/bin/bash", "-lc", args]
            else:
                template = self.allowlist.get(command)
                if not template:
                    return 126, "command not allowed", False
                argv = [part.replace("{args}", args) for part in template]
            db.execute(
                "INSERT INTO executions VALUES(?,?,?,?,?,?,?,?)",
                (source, session, msg, digest, "pending", 125, "", time.time()),
            )
        output = bytearray()
        proc = None
        status = 125
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=(os.name != "nt"),
            )

            async def drain():
                while True:
                    chunk = await proc.stdout.read(1024)
                    if not chunk:
                        break
                    output.extend(chunk[: max(0, 3000 - len(output))])
                return await proc.wait()

            status = await asyncio.wait_for(drain(), 30)
        except asyncio.TimeoutError:
            status = 124
            output.extend(b"\ncommand timed out")
        except OSError as e:
            output.extend(str(e).encode()[:500])
        finally:
            if proc and proc.returncode is None:
                try:
                    if os.name == "nt":
                        proc.kill()
                    else:
                        os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await proc.wait()
        text = output.decode(errors="replace")
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE executions SET state=?,status=?,output=? WHERE source=? AND session=? AND msg=?",
                ("done", status, text, source, session, msg),
            )
        return status, text, False
