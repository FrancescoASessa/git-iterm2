import hmac
import json
from typing import Any

from aiohttp import WSMessage, WSMsgType, web

from git_iterm2.api.keys import CONFIG_KEY, CONTROLLER_KEY, WEBSOCKETS_KEY
from git_iterm2.models import ServerMessage

AUTH_TIMEOUT = 5.0
UNAUTHORIZED_CLOSE_CODE = 4401

CLOSE_TIMEOUT = 1.0
"""Seconds `WebSocketResponse.close()` waits for the peer to answer our
CLOSE frame. aiohttp's default is 10s, and the peer here is a toolbelt web
view that may be suspended (a sleeping laptop) and never answer at all --
at shutdown we would rather drop it than wait. Kept well inside the panel's
other bounds; on loopback a live peer answers in milliseconds."""


def _is_valid_auth(message: WSMessage, token: str) -> bool:
    if message.type != WSMsgType.TEXT:
        return False
    try:
        data: Any = json.loads(message.data)
    except ValueError:
        return False
    if not isinstance(data, dict):
        return False
    provided = data.get("token")
    return (
        data.get("type") == "auth"
        and isinstance(provided, str)
        and hmac.compare_digest(provided.encode(), token.encode())
    )


async def websocket_handler(request: web.Request) -> web.StreamResponse:
    controller = request.app[CONTROLLER_KEY]
    token = request.app[CONFIG_KEY].token
    ws = web.WebSocketResponse(heartbeat=30.0, timeout=CLOSE_TIMEOUT)
    await ws.prepare(request)

    try:
        first = await ws.receive(timeout=AUTH_TIMEOUT)
    except TimeoutError:
        await ws.close(code=UNAUTHORIZED_CLOSE_CODE, message=b"auth timeout")
        return ws
    if not _is_valid_auth(first, token):
        await ws.close(code=UNAUTHORIZED_CLOSE_CODE, message=b"unauthorized")
        return ws

    async def send(message: ServerMessage) -> None:
        if not ws.closed:
            await ws.send_str(message.model_dump_json())

    # Subscribe first so no update published while the snapshot is sent can be missed.
    unsubscribe = controller.subscribe(send)
    # Registered only once authenticated: an unauthenticated socket is
    # already closed by the time it gets here, and shutdown has nothing to
    # do for it.
    request.app[WEBSOCKETS_KEY].add(ws)
    try:
        await send(controller.snapshot_message())
        async for _message in ws:
            pass
    finally:
        unsubscribe()
        request.app[WEBSOCKETS_KEY].discard(ws)
    return ws
