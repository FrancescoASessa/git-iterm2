import hmac
import json
from typing import Any

from aiohttp import WSMessage, WSMsgType, web

from git_iterm2.api.keys import CONFIG_KEY, CONTROLLER_KEY
from git_iterm2.models import ServerMessage, SnapshotMessage

AUTH_TIMEOUT = 5.0
UNAUTHORIZED_CLOSE_CODE = 4401


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
    ws = web.WebSocketResponse(heartbeat=30.0)
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
    try:
        await send(SnapshotMessage(repo=controller.snapshot))
        async for _message in ws:
            pass
    finally:
        unsubscribe()
    return ws
