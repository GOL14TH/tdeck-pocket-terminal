import hmac
from fastapi import HTTPException, WebSocket

def check_token(candidate: str | None, expected: str):
    if not candidate or not hmac.compare_digest(candidate, expected):
        raise HTTPException(401, "unauthorized")

def ws_token(ws: WebSocket) -> str | None:
    auth = ws.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return None

async def ws_auth(ws: WebSocket, expected: str):
    token = ws_token(ws)
    if not token or not hmac.compare_digest(token, expected):
        await ws.close(code=4401)
        return False
    return True
