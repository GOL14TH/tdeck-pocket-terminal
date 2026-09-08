from __future__ import annotations

import asyncio, secrets, time

from dataclasses import dataclass, field

from .terminal import PtySession

@dataclass

class ManagedTerminal:

    session: PtySession

    created: float = field(default_factory=time.monotonic)

    touched: float = field(default_factory=time.monotonic)

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

class TerminalSessionManager:

    """Small bounded PTY registry for HTTP-polling embedded clients."""

    def __init__(

        self, max_sessions: int = 4, idle_timeout_s: int = 900, factory=PtySession

    ):

        self.max_sessions = max_sessions

        self.idle_timeout_s = idle_timeout_s

        self._sessions: dict[str, ManagedTerminal] = {}

        self._guard = asyncio.Lock()

        self.factory = factory

    async def create(self, target: str | None) -> str:

        async with self._guard:

            await self._reap_locked()

            if len(self._sessions) >= self.max_sessions:

                raise RuntimeError("terminal session limit reached")

            sid = secrets.token_urlsafe(18)

            self._sessions[sid] = ManagedTerminal(await self.factory(target).start())

            return sid

    async def write(self, sid: str, data: bytes) -> None:

        item = self._get(sid)

        async with item.lock:

            item.touched = time.monotonic()

            await item.session.write(data)

    async def read(self, sid: str, n: int = 4096) -> bytes:

        item = self._get(sid)

        async with item.lock:

            item.touched = time.monotonic()

            return await item.session.read(n)

    async def close(self, sid: str) -> None:

        async with self._guard:

            item = self._sessions.pop(sid, None)

        if item:

            async with item.lock:

                await item.session.close()

    async def close_all(self) -> None:

        async with self._guard:

            items = list(self._sessions.values())

            self._sessions.clear()

        for item in items:

            await item.session.close()

    def _get(self, sid: str) -> ManagedTerminal:

        item = self._sessions.get(sid)

        if not item:

            raise KeyError(sid)

        return item

    async def reap(self):

        async with self._guard:

            await self._reap_locked()

    async def _reap_locked(self) -> None:

        now = time.monotonic()

        stale = [

            sid

            for sid, item in self._sessions.items()

            if now - item.touched > self.idle_timeout_s

        ]

        for sid in stale:

            item = self._sessions.pop(sid)

            await item.session.close()
