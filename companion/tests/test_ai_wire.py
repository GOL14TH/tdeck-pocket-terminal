import asyncio, json
import httpx, pytest
from tdeck_companion.app import create_app
from tdeck_companion.config import Settings, HostProfile

@pytest.mark.asyncio
async def test_real_ai_http_proxy_without_model():
    seen = []

    async def ollama(reader, writer):
        headers = await reader.readuntil(b"\r\n\r\n")
        size = next(
            int(line.split(b":", 1)[1])
            for line in headers.split(b"\r\n")
            if line.lower().startswith(b"content-length:")
        )
        body = json.loads(await reader.readexactly(size))
        seen.append(body)
        payload = json.dumps(
            {"message": {"content": "RFB and AI protocol test reply"}, "done": True}
        ).encode()
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(payload)).encode()
            + b"\r\nConnection: close\r\n\r\n"
            + payload
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(ollama, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    app = create_app(
        Settings(
            token="x" * 32,
            hosts=[
                HostProfile(
                    id="pi",
                    name="Pi",
                    ai_url=f"http://127.0.0.1:{port}",
                    ai_model="test-model",
                )
            ],
        )
    )
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": "Bearer " + "x" * 32},
            ) as c:
                start = await c.post("/api/v2/ai/pi", content="test prompt")
                assert start.status_code == 202
                jid = start.text
                for _ in range(100):
                    result = await c.get("/api/v2/ai/job/" + jid)
                    if result.status_code != 202:
                        break
                    await asyncio.sleep(0.01)
                assert (
                    result.status_code == 200
                    and result.text == "RFB and AI protocol test reply"
                )
                assert (
                    seen[0]["think"] is False
                    and seen[0]["options"]["num_predict"] == 256
                )
                assert seen[0]["messages"] == [
                    {"role": "user", "content": "test prompt"}
                ]
    finally:
        server.close()
        await server.wait_closed()
