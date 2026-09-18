import json
from pathlib import Path

import pytest
from aiohttp import WSMsgType, WSServerHandshakeError, web
from aiohttp.test_utils import TestClient

from git_iterm2.api.app import create_app
from git_iterm2.api.keys import CONTROLLER_KEY, ServerConfig
from git_iterm2.core.controller import RepoController
from tests.helpers import write

TOKEN = "test-token"


@pytest.fixture
async def client(aiohttp_client, repo: Path) -> TestClient:  # type: ignore[no-untyped-def]
    controller = RepoController()
    await controller.set_active_path(repo)
    return await aiohttp_client(create_app(controller, ServerConfig(token=TOKEN)))


async def test_ws_sends_snapshot_after_auth(client: TestClient, repo: Path) -> None:
    ws = await client.ws_connect("/ws")
    await ws.send_str(json.dumps({"type": "auth", "token": TOKEN}))
    message = json.loads((await ws.receive(timeout=5)).data)
    assert message["type"] == "snapshot"
    assert message["repo"]["root"] == str(repo.resolve())
    await ws.close()


async def test_ws_rejects_bad_token(client: TestClient) -> None:
    ws = await client.ws_connect("/ws")
    await ws.send_str(json.dumps({"type": "auth", "token": "wrong"}))
    message = await ws.receive(timeout=5)
    assert message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING)
    assert ws.close_code == 4401


async def test_ws_pushes_snapshot_after_action(client: TestClient, repo: Path) -> None:
    ws = await client.ws_connect("/ws")
    await ws.send_str(json.dumps({"type": "auth", "token": TOKEN}))
    await ws.receive(timeout=5)

    write(repo, "new.txt", "n\n")
    response = await client.post(
        "/api/stage", json={"paths": ["new.txt"]}, headers={"X-Token": TOKEN}
    )
    assert response.status == 204

    message = json.loads((await ws.receive(timeout=5)).data)
    assert message["type"] == "snapshot"
    assert [change["path"] for change in message["repo"]["staged"]] == ["new.txt"]
    await ws.close()


async def test_ws_rejects_foreign_origin(client: TestClient) -> None:
    with pytest.raises(WSServerHandshakeError) as info:
        await client.ws_connect("/ws", headers={"Origin": "https://evil.example"})
    assert info.value.status == 403


async def test_ws_closes_when_auth_never_arrives(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("git_iterm2.api.ws.AUTH_TIMEOUT", 0.2)
    ws = await client.ws_connect("/ws")
    message = await ws.receive(timeout=5)
    assert message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING)
    assert ws.close_code == 4401


async def test_ws_subscribes_before_initial_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = client.app[CONTROLLER_KEY]
    events: list[str] = []
    original_subscribe = controller.subscribe

    def subscribe(listener):  # type: ignore[no-untyped-def]
        events.append("subscribe")
        return original_subscribe(listener)

    original_send_str = web.WebSocketResponse.send_str

    async def send_str(self, data, compress=None):  # type: ignore[no-untyped-def]
        events.append("send")
        await original_send_str(self, data, compress=compress)

    monkeypatch.setattr(controller, "subscribe", subscribe)
    monkeypatch.setattr(web.WebSocketResponse, "send_str", send_str)
    ws = await client.ws_connect("/ws")
    await ws.send_str(json.dumps({"type": "auth", "token": TOKEN}))
    await ws.receive(timeout=5)
    await ws.close()
    assert events[:2] == ["subscribe", "send"]
