from __future__ import annotations
import asyncio, os, signal

class PtySession:
    def __init__(self, target: str | None):
        self.target = target
        self.master = None
        self.proc = None

    async def start(self):
        import pty, fcntl, termios, struct

        master, slave = pty.openpty()
        self.master = master
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 12, 50, 0, 0))
        argv = ["/bin/bash", "-l"] if not self.target else ["ssh", "-tt", self.target]
        env = dict(os.environ, TERM="dumb", PS1="$ ")
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,
                env=env,
            )
        except BaseException:
            os.close(slave)
            os.close(master)
            self.master = None
            raise
        os.close(slave)
        os.set_blocking(master, False)
        return self

    async def read(self, n=4096):
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, os.read, self.master, n)
        except BlockingIOError:
            await asyncio.sleep(0.02)
            return b""
        except OSError:
            return b""

    async def write(self, data: bytes):
        while data and self.master is not None:
            try:
                data = data[os.write(self.master, data) :]
            except BlockingIOError:
                await asyncio.sleep(0.01)

    async def close(self):
        if self.proc and self.proc.returncode is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.proc.wait(), 2)
            except asyncio.TimeoutError:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await self.proc.wait()
        if self.master is not None:
            try:
                os.close(self.master)
            except OSError:
                pass
            self.master = None
