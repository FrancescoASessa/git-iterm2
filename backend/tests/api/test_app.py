"""Tests for the server's own lifecycle (`git_iterm2.api.app`)."""

import asyncio
import base64
import contextlib
import json
import secrets
import time
from pathlib import Path

import aiohttp
import pytest

from git_iterm2.api.app import create_app, start_server
from git_iterm2.api.keys import WEBSOCKETS_KEY, ServerConfig
from git_iterm2.core.controller import RepoController

TOKEN = "test-token"

PROMPT_BUDGET = 1.0
"""What "prompt" means for a *healthy* peer, in seconds (it is ~0.2s in
practice). Deliberately tighter than `_SHUTDOWN_TIMEOUT`: with the
`on_shutdown` hook removed, the handler never unwinds and shutdown falls
back to the runner's drain, which costs 2x `_SHUTDOWN_TIMEOUT`. A looser
bound let a suite stay green while the hook was deleted -- measured at 4.0s
against the original `< 5.0`."""

SUSPENDED_PEER_BUDGET = 3.0
"""The worst case, in seconds: a peer that never closes its end costs the
runner both drain phases, 2x `_SHUTDOWN_TIMEOUT`. Tight enough that losing
`shutdown_timeout` (aiohttp's default is 60s) fails here, which is the
change `PROMPT_BUDGET` cannot pin on its own."""


async def test_cleanup_is_prompt_with_a_live_websocket(repo: Path) -> None:
    """The toolbelt web view holds a websocket open for the panel's entire
    life, and `ws.py`'s `async for _message in ws` never returns on its own.
    Nothing closed those sockets on shutdown and `AppRunner` took aiohttp's
    default 60s `shutdown_timeout`, so stopping the script from the Script
    Console left the process -- and its listening socket -- alive for about
    a minute, swamping every other bound on this branch (2s drain, 5s
    startup apply).
    """
    controller = RepoController()
    await controller.set_active_path(repo)
    runner, port = await start_server(create_app(controller, ServerConfig(token=TOKEN)))

    async with aiohttp.ClientSession() as http:  # noqa: SIM117
        async with http.ws_connect(f"http://127.0.0.1:{port}/ws") as ws:
            await ws.send_str(json.dumps({"type": "auth", "token": TOKEN}))
            first = await ws.receive(timeout=5.0)
            assert json.loads(first.data)["type"] == "snapshot"

            started = time.monotonic()
            # `wait_for` so a regression fails in seconds rather than making
            # the suite sit through the whole 60s default.
            await asyncio.wait_for(runner.cleanup(), timeout=10.0)
            elapsed = time.monotonic() - started

    assert elapsed < PROMPT_BUDGET, f"cleanup with a live websocket took {elapsed:.1f}s"

    # And the listening socket is really gone, not merely abandoned.
    with pytest.raises(OSError):
        await asyncio.open_connection("127.0.0.1", port)


async def _raw_peer(port: int, token: str) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """A websocket client that completes the handshake, authenticates, and
    then never reads another byte -- the toolbelt web view on a laptop that
    went to sleep.

    Hand-rolled rather than driven with `aiohttp`'s client: that client only
    parses frames (and only answers a CLOSE) inside `receive()`, and relying
    on when it does or doesn't ack would be testing its internals instead of
    the hazard. A raw socket simply never answers, which is the point.
    """
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    key = base64.b64encode(secrets.token_bytes(16)).decode()
    writer.write(
        f"GET /ws HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n".encode()
    )
    await writer.drain()
    status = await asyncio.wait_for(reader.readline(), timeout=5.0)
    assert status.startswith(b"HTTP/1.1 101"), status
    while (await asyncio.wait_for(reader.readline(), timeout=5.0)).strip():
        pass

    payload = json.dumps({"type": "auth", "token": token}).encode()
    mask = secrets.token_bytes(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    writer.write(bytes([0x81, 0x80 | len(payload)]) + mask + masked)
    await writer.drain()
    return reader, writer


async def test_a_suspended_peer_cannot_extend_shutdown(repo: Path) -> None:
    """The laptop sleeps with the toolbelt web view suspended, then the user
    stops the script from the Script Console.

    The peer never answers the CLOSE frame, so `WebSocketResponse.close()`
    sits on its own close timeout (10s by default, with an unbounded
    `writer.drain()` before it). `_SHUTDOWN_TIMEOUT` does not cover that:
    aiohttp's `BaseRunner.cleanup()` fires `on_shutdown` *first* and only
    then passes that timeout to `self._server.shutdown(...)`. An unbounded
    close handler reintroduces exactly the hang this fix exists to remove.
    """
    controller = RepoController()
    await controller.set_active_path(repo)
    runner, port = await start_server(create_app(controller, ServerConfig(token=TOKEN)))
    _reader, writer = await _raw_peer(port, TOKEN)

    try:
        started = time.monotonic()
        await asyncio.wait_for(runner.cleanup(), timeout=30.0)
        elapsed = time.monotonic() - started
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()

    assert elapsed < SUSPENDED_PEER_BUDGET, f"a suspended peer held shutdown for {elapsed:.1f}s"

    with pytest.raises(OSError):
        await asyncio.open_connection("127.0.0.1", port)


class _StuckWebSocket:
    """A websocket whose `close()` never returns -- the unbounded part of
    the real thing (`writer.drain()` against a peer whose receive window is
    full, and the wait for an answering CLOSE that a suspended peer never
    sends)."""

    closed = False

    async def close(self, *, code: int = 1000, message: bytes = b"") -> bool:
        await asyncio.Event().wait()
        return True


class _RaisingWebSocket:
    """A websocket whose `close()` raises, which a real one does on a
    connection already gone."""

    closed = False

    async def close(self, *, code: int = 1000, message: bytes = b"") -> bool:
        raise ConnectionResetError("peer vanished")


async def test_a_websocket_that_will_not_close_cannot_hold_shutdown(repo: Path) -> None:
    """`_close_websockets` runs as an `on_shutdown` receiver, which
    `BaseRunner.cleanup()` fires *before* `self._server.shutdown(
    self._shutdown_timeout)`. So `_SHUTDOWN_TIMEOUT` does not bound it, and
    a socket that will not close must be dropped on this function's own
    bound instead of stalling shutdown for as long as it likes.
    """
    controller = RepoController()
    await controller.set_active_path(repo)
    app = create_app(controller, ServerConfig(token=TOKEN))
    runner, port = await start_server(app)
    app[WEBSOCKETS_KEY].add(_StuckWebSocket())  # type: ignore[arg-type]

    started = time.monotonic()
    await asyncio.wait_for(runner.cleanup(), timeout=30.0)
    elapsed = time.monotonic() - started

    assert elapsed < SUSPENDED_PEER_BUDGET, f"a stuck websocket held shutdown for {elapsed:.1f}s"
    with pytest.raises(OSError):
        await asyncio.open_connection("127.0.0.1", port)


async def test_a_websocket_that_fails_to_close_still_releases_the_port(repo: Path) -> None:
    """`aiohttp.Signal` has no per-receiver error isolation: an exception
    escaping `_close_websockets` aborts `cleanup()` before
    `self._server.shutdown()` and `_cleanup_server()`, leaving the listening
    port alive -- the exact failure the handler exists to prevent. It would
    also mask whatever exception `run_panel`'s `finally: await
    runner.cleanup()` was unwinding.
    """
    controller = RepoController()
    await controller.set_active_path(repo)
    app = create_app(controller, ServerConfig(token=TOKEN))
    runner, port = await start_server(app)
    app[WEBSOCKETS_KEY].add(_RaisingWebSocket())  # type: ignore[arg-type]

    await asyncio.wait_for(runner.cleanup(), timeout=30.0)  # must not raise

    with pytest.raises(OSError):
        await asyncio.open_connection("127.0.0.1", port)


async def test_a_peer_that_never_acks_a_rejection_is_dropped_promptly(repo: Path) -> None:
    """The close timeout matters outside shutdown too.

    `ws.py` closes the socket itself when authentication fails or never
    arrives. With aiohttp's default 10s close timeout, a peer that never
    answers that CLOSE pins the handler -- and the connection -- for ten
    seconds per attempt; `_close_websockets`'s own bound does not apply,
    since this socket was never registered (it is closed before it could
    be). `CLOSE_TIMEOUT` is what bounds it.
    """
    controller = RepoController()
    await controller.set_active_path(repo)
    runner, port = await start_server(create_app(controller, ServerConfig(token=TOKEN)))
    reader, writer = await _raw_peer(port, "wrong-token")

    try:
        started = time.monotonic()
        # The server sends CLOSE; we never answer. Read to EOF: the server
        # gives up waiting and drops the connection.
        while await asyncio.wait_for(reader.read(4096), timeout=30.0):
            pass
        elapsed = time.monotonic() - started
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        await runner.cleanup()

    assert elapsed < PROMPT_BUDGET * 3, f"a rejected peer held its handler for {elapsed:.1f}s"
