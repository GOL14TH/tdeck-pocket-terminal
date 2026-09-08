import json, httpx
import os

async def chat_host(host, prompt: str) -> str:
    if host.ai_provider == "ollama":
        return await chat_ollama(host.ai_url, host.ai_model, prompt)
    headers = {}
    if host.ai_api_key_env:
        key = os.environ.get(host.ai_api_key_env)
        if not key:
            raise RuntimeError("Configured AI credential environment variable is missing")
        headers["Authorization"] = "Bearer " + key
    body = {"model": host.ai_model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "max_tokens": 256}
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5)) as client:
        response = await client.post(host.ai_url.rstrip("/") + "/chat/completions", json=body, headers=headers)
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])

async def stream_ollama(base_url: str, model: str, prompt: str):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "think": False,
        "options": {"num_ctx": 2048, "num_predict": 256},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5)) as client:
        async with client.stream(
            "POST", base_url.rstrip("/") + "/api/chat", json=body
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                obj = json.loads(line)
                text = (obj.get("message") or {}).get("content", "")
                if text:
                    yield text
                if obj.get("done"):
                    break

async def chat_ollama(base_url: str, model: str, prompt: str) -> str:
    """Non-streaming Ollama chat for low-complexity embedded HTTP clients."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_ctx": 2048, "num_predict": 256},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5)) as client:
        r = await client.post(base_url.rstrip("/") + "/api/chat", json=body)
        r.raise_for_status()
        obj = r.json()
        return str((obj.get("message") or {}).get("content", ""))
