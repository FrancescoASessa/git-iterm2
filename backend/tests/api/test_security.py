import asyncio
import logging
from pathlib import Path

import aiohttp
import pytest
from aiohttp.test_utils import TestClient

from git_iterm2.api.app import create_app, start_server
from git_iterm2.api.keys import ServerConfig
from git_iterm2.core.controller import RepoController

TOKEN = "test-token"


@pytest.fixture
async def client(aiohttp_client, repo: Path) -> TestClient:  # type: ignore[no-untyped-def]
    controller = RepoController()
    await controller.set_active_path(repo)
    return await aiohttp_client(create_app(controller, ServerConfig(token=TOKEN)))


async def test_api_requires_token(client: TestClient) -> None:
    response = await client.get("/api/branches")
    assert response.status == 401
    assert (await response.json())["code"] == "UNAUTHORIZED"


async def test_api_rejects_wrong_token(client: TestClient) -> None:
    response = await client.get("/api/branches", headers={"X-Token": "wrong"})
    assert response.status == 401


async def test_api_accepts_token(client: TestClient) -> None:
    response = await client.get("/api/branches", headers={"X-Token": TOKEN})
    assert response.status == 200


async def test_foreign_origin_is_forbidden(client: TestClient) -> None:
    response = await client.get(
        "/api/branches", headers={"X-Token": TOKEN, "Origin": "https://evil.example"}
    )
    assert response.status == 403
    assert (await response.json())["code"] == "FORBIDDEN"


async def test_same_origin_is_allowed(client: TestClient) -> None:
    origin = f"http://127.0.0.1:{client.port}"
    response = await client.get("/api/branches", headers={"X-Token": TOKEN, "Origin": origin})
    assert response.status == 200


async def test_foreign_host_is_forbidden(client: TestClient) -> None:
    response = await client.get("/api/branches", headers={"X-Token": TOKEN, "Host": "evil.example"})
    assert response.status == 403


async def test_index_without_static_dir_has_csp(client: TestClient) -> None:
    response = await client.get("/")
    assert response.status == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


async def test_static_files_are_served(aiohttp_client, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>panel</html>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    client = await aiohttp_client(
        create_app(RepoController(), ServerConfig(token=TOKEN, static_dir=static))
    )
    index = await client.get("/")
    assert "panel" in await index.text()
    asset = await client.get("/assets/app.js")
    assert asset.status == 200


async def test_token_is_never_logged(repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    secret = "super-secret-token-value"
    controller = RepoController()
    await controller.set_active_path(repo)
    runner, port = await start_server(create_app(controller, ServerConfig(token=secret)))
    caplog.set_level(logging.DEBUG)
    canary = "canary: caplog is capturing git_iterm2 log records"
    try:
        async with aiohttp.ClientSession() as session:
            base = f"http://127.0.0.1:{port}"
            async with session.get(f"{base}/?t={secret}") as index:
                assert index.status == 200
                assert index.headers["Referrer-Policy"] == "no-referrer"
            async with session.get(f"{base}/api/branches", headers={"X-Token": secret}) as api:
                assert api.status == 200
                await api.read()
        # Positive control: none of the requests above happen to log
        # anything, so `secret not in caplog.text` alone would pass
        # vacuously (e.g. if `caplog.text` were empty for an unrelated
        # reason, such as `git_iterm2.propagate` having been left `False`
        # by another test). Prove `caplog` really is receiving records from
        # this codebase's logger hierarchy right now before trusting the
        # negative assertion below.
        logging.getLogger("git_iterm2.api.security").info(canary)
    finally:
        await runner.cleanup()
    assert canary in caplog.text
    assert secret not in caplog.text


async def test_non_utf8_token_is_unauthorized(client: TestClient) -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", client.port)
    writer.write(
        b"GET /api/branches HTTP/1.1\r\n"
        + f"Host: 127.0.0.1:{client.port}\r\n".encode()
        + b"X-Token: \xff\xfe\r\nConnection: close\r\n\r\n"
    )
    await writer.drain()
    status_line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    assert status_line.split()[1] == b"401"
