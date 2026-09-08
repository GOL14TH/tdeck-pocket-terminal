from fastapi.testclient import TestClient
import tdeck_companion.app as appmod
from tdeck_companion.config import Settings, HostProfile

def settings():
    return Settings(
        token="x" * 32,
        hosts=[HostProfile(id="pi", name="Pi", local_ip="192.168.1.50")],
        state_db="/tmp/tdeck-test.sqlite3",
    )

def test_health_and_hosts_auth():
    c = TestClient(appmod.create_app(settings()))
    assert c.get("/health").json() == {"ok": True, "hosts": 1}
    assert c.get("/api/hosts").status_code == 401
    r = c.get("/api/hosts", headers={"Authorization": "Bearer " + "x" * 32})
    assert r.status_code == 200 and r.json()[0]["id"] == "pi"

def test_embedded_ai_plaintext_endpoint(monkeypatch):
    async def fake_chat(base_url, model, prompt):
        assert base_url == "http://127.0.0.1:11434"
        assert model == "gemma3"
        return "answer: " + prompt

    monkeypatch.setattr("tdeck_companion.ai.chat_ollama", fake_chat)
    c = TestClient(appmod.create_app(settings()))
    hdr = {"Authorization": "Bearer " + "x" * 32}
    r = c.post("/api/v1/ai/pi", headers=hdr, content=b"hello deck")
    assert r.status_code == 200 and r.text == "answer: hello deck"
    assert c.post("/api/v1/ai/pi", headers=hdr, content=b"").status_code == 400

def test_embedded_terminal_unknown_session_is_404():
    c = TestClient(appmod.create_app(settings()))
    hdr = {"Authorization": "Bearer " + "x" * 32}
    assert (
        c.get("/api/v1/terminal/session/not-a-session/read", headers=hdr).status_code
        == 404
    )
