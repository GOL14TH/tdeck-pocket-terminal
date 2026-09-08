from __future__ import annotations
import argparse, asyncio, contextlib, secrets, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, Request, HTTPException
from fastapi.responses import PlainTextResponse, Response
from .config import load_settings
from .security import check_token
from .ai import chat_host
from .terminal_http import TerminalSessionManager
from .desktop_http import DesktopManager
from .simulation import SimTerminal

async def bounded_body(request, limit=8192):
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, "request too large")
        data.extend(chunk)
    return bytes(data)

def create_app(settings=None):
    s = settings or load_settings()
    terms = TerminalSessionManager(**({"factory": SimTerminal} if s.simulation else {}))
    desktops = DesktopManager(s.simulation)
    jobs = {}
    gateway = None

    async def reap():
        while True:
            await asyncio.sleep(10)
            await terms.reap()
            await desktops.reap()
            for jid, item in list(jobs.items()):
                if time.monotonic() - item["created"] > 180:
                    item["task"].cancel()
                    jobs.pop(jid, None)

    @asynccontextmanager
    async def lifespan(app):
        nonlocal gateway
        if s.mesh_serial or s.mesh_tcp:
            from .mesh_gateway import start_gateway

            gateway = await start_gateway(s)
        task = asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            running = [item["task"] for item in jobs.values()]
            for job in running:
                job.cancel()
            await asyncio.gather(*running, return_exceptions=True)
            await terms.close_all()
            await desktops.close_all()
            if gateway:
                await gateway.close()

    app = FastAPI(title="T-Deck Companion", lifespan=lifespan)
    app.state.terminals = terms
    app.state.desktops = desktops

    def auth(header):
        token = header[7:] if header and header.lower().startswith("bearer ") else None
        check_token(token, s.token)

    def host(hid):
        try:
            return s.host(hid)
        except KeyError:
            raise HTTPException(404, "unknown host")

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return PlainTextResponse("unknown session", status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return PlainTextResponse(str(exc), status_code=400)

    @app.exception_handler(RuntimeError)
    async def unavailable(request, exc):
        return PlainTextResponse(str(exc), status_code=503)

    @app.exception_handler(TimeoutError)
    async def timeout(request, exc):
        return PlainTextResponse("backend timed out", status_code=504)

    @app.get("/health")
    async def health():
        return {"ok": True, "hosts": len(s.hosts)}

    @app.get("/api/hosts")
    async def hosts(authorization: str | None = Header(None)):
        auth(authorization)
        return [
            {
                "id": h.id,
                "name": h.name,
                "hostname": h.hostname,
                "local_ip": h.local_ip,
                "simulation": s.simulation,
            }
            for h in s.hosts
        ]

    async def answer(h, prompt):
        if s.simulation:
            return "[SIMULATION - no model loaded] Received: " + prompt
        return await asyncio.wait_for(chat_host(h, prompt), 95)

    @app.post("/api/v1/ai/{host_id}", response_class=PlainTextResponse)
    async def ai(
        host_id: str, request: Request, authorization: str | None = Header(None)
    ):
        auth(authorization)
        h = host(host_id)
        prompt = (await bounded_body(request)).decode("utf-8", "replace").strip()
        if not prompt:
            raise HTTPException(400, "empty prompt")
        return await answer(h, prompt)

    @app.post("/api/v2/ai/{host_id}", response_class=PlainTextResponse, status_code=202)
    async def ai_start(
        host_id: str, request: Request, authorization: str | None = Header(None)
    ):
        auth(authorization)
        h = host(host_id)
        prompt = (await bounded_body(request)).decode("utf-8", "replace").strip()
        if not prompt:
            raise HTTPException(400, "empty prompt")
        if (
            sum(not item["task"].done() for item in jobs.values()) >= 1
            or len(jobs) >= 8
        ):
            raise HTTPException(429, "AI busy; try again shortly")
        jid = secrets.token_hex(12)
        jobs[jid] = {
            "task": asyncio.create_task(answer(h, prompt)),
            "created": time.monotonic(),
        }
        return jid

    @app.get("/api/v2/ai/job/{jid}", response_class=PlainTextResponse)
    async def ai_poll(jid: str, authorization: str | None = Header(None)):
        auth(authorization)
        item = jobs[jid]
        if not item["task"].done():
            return PlainTextResponse("Working...", status_code=202)
        try:
            return str(item["task"].result())[:8192]
        except Exception:
            return PlainTextResponse(
                "AI backend unavailable or timed out", status_code=502
            )

    @app.delete("/api/v2/ai/job/{jid}", status_code=204)
    async def ai_close(jid: str, authorization: str | None = Header(None)):
        auth(authorization)
        item = jobs.pop(jid, None)
        if item:
            item["task"].cancel()
            await asyncio.gather(item["task"], return_exceptions=True)
        return Response(status_code=204)

    @app.post("/api/v1/terminal/{host_id}", response_class=PlainTextResponse)
    async def terminal_create(host_id: str, authorization: str | None = Header(None)):
        auth(authorization)
        return await terms.create(host(host_id).terminal_target)

    @app.get("/api/v1/terminal/session/{sid}/read")
    async def terminal_read(sid: str, authorization: str | None = Header(None)):
        auth(authorization)
        return Response(await terms.read(sid), media_type="application/octet-stream")

    @app.post("/api/v1/terminal/session/{sid}/write", status_code=204)
    async def terminal_write(
        sid: str, request: Request, authorization: str | None = Header(None)
    ):
        auth(authorization)
        await terms.write(sid, await bounded_body(request))
        return Response(status_code=204)

    @app.delete("/api/v1/terminal/session/{sid}", status_code=204)
    async def terminal_close(sid: str, authorization: str | None = Header(None)):
        auth(authorization)
        await terms.close(sid)
        return Response(status_code=204)

    @app.post("/api/v2/desktop/{host_id}", response_class=PlainTextResponse)
    async def desktop_create(host_id: str, authorization: str | None = Header(None)):
        auth(authorization)
        return await desktops.create(host(host_id))

    @app.get("/api/v2/desktop/session/{sid}/frame")
    async def desktop_frame(
        sid: str,
        x: int = 0,
        y: int = 0,
        reset: bool = False,
        authorization: str | None = Header(None),
    ):
        auth(authorization)
        return Response(
            await desktops.frame(sid, x, y, reset),
            media_type="application/octet-stream",
        )

    @app.post("/api/v2/desktop/session/{sid}/input", status_code=204)
    async def desktop_input(
        sid: str, request: Request, authorization: str | None = Header(None)
    ):
        import json

        auth(authorization)
        event = json.loads(await bounded_body(request, 512))
        if not isinstance(event, dict):
            raise HTTPException(400, "expected object")
        await desktops.input(sid, event)
        return Response(status_code=204)

    @app.delete("/api/v2/desktop/session/{sid}", status_code=204)
    async def desktop_close(sid: str, authorization: str | None = Header(None)):
        auth(authorization)
        await desktops.close(sid)
        return Response(status_code=204)

    return app

def main():
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    s = load_settings(a.config)
    if bool(s.tls_cert) != bool(s.tls_key):
        raise SystemExit("tls_cert and tls_key must be configured together")
    uvicorn.run(
        create_app(s),
        host=s.bind_host,
        port=s.bind_port,
        ssl_certfile=s.tls_cert,
        ssl_keyfile=s.tls_key,
    )

if __name__ == "__main__":
    main()
