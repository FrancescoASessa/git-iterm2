import asyncio
import logging
import socket
from pathlib import Path

from aiohttp import WSCloseCode, web

from git_iterm2.api.keys import CONFIG_KEY, CONTROLLER_KEY, WEBSOCKETS_KEY, ServerConfig
from git_iterm2.api.routes import add_api_routes
from git_iterm2.api.security import error_middleware, security_middleware
from git_iterm2.api.ws import CLOSE_TIMEOUT, websocket_handler
from git_iterm2.core.controller import RepoController

logger = logging.getLogger(__name__)

_SHUTDOWN_TIMEOUT = 1.0
"""Seconds `AppRunner.cleanup()` gives connections to finish once every
websocket has been closed, before dropping them. aiohttp's default is 60s,
and the toolbelt web view keeps a websocket open for the panel's entire
life: with the default, stopping the script from the iTerm2 Script Console
left the process -- and its listening socket -- alive for about a minute.

aiohttp spends this twice (a graceful phase, then a forced one), so it is
also half the worst case: a suspended peer that never closes its end of the
TCP connection costs 2x this, and nothing more."""


async def _close_websockets(app: web.Application) -> None:
    """`ws.py`'s `async for _message in ws` only ends when the socket does,
    so shutdown has to end it from this side; closing makes that loop return
    and the handler unwind.

    Concurrently, bounded, and swallowing per-socket failures, because this
    runs as an `on_shutdown` receiver and aiohttp's `BaseRunner.cleanup()`
    fires those *before* `self._server.shutdown(self._shutdown_timeout)` --
    so `_SHUTDOWN_TIMEOUT` does not cover this function at all, and
    `aiohttp.Signal` gives its receivers no error isolation. An exception
    escaping here would abort `cleanup()` before the server is shut down and
    the socket released: the listening port would outlive the panel, which
    is the very failure this handler exists to prevent. It would also mask
    whatever exception `run_panel`'s `finally: await runner.cleanup()` was
    already unwinding.
    """
    live: set[web.WebSocketResponse] = app[WEBSOCKETS_KEY]
    if not live:
        return

    async def close(ws: web.WebSocketResponse) -> None:
        # `close()` is bounded internally by `CLOSE_TIMEOUT` only while it
        # waits for the peer's answering CLOSE; the `writer.drain()` before
        # that is not bounded at all. This wait_for is the actual guarantee.
        await asyncio.wait_for(
            ws.close(code=WSCloseCode.GOING_AWAY, message=b"panel shutting down"),
            CLOSE_TIMEOUT,
        )

    results = await asyncio.gather(*(close(ws) for ws in list(live)), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
            logger.warning("could not close a websocket during shutdown", exc_info=result)


def _add_static_routes(app: web.Application, static_dir: Path | None) -> None:
    async def index(request: web.Request) -> web.StreamResponse:
        if static_dir is None or not (static_dir / "index.html").is_file():
            return web.Response(text="git-iterm2: web UI not built", content_type="text/plain")
        return web.FileResponse(static_dir / "index.html")

    app.router.add_get("/", index)
    if static_dir is not None and (static_dir / "assets").is_dir():
        app.router.add_static("/assets", static_dir / "assets", follow_symlinks=False)


def create_app(controller: RepoController, config: ServerConfig) -> web.Application:
    app = web.Application(middlewares=[security_middleware, error_middleware])
    app[CONTROLLER_KEY] = controller
    app[CONFIG_KEY] = config
    app[WEBSOCKETS_KEY] = set()
    app.on_shutdown.append(_close_websockets)
    add_api_routes(app)
    app.router.add_get("/ws", websocket_handler)
    _add_static_routes(app, config.static_dir)
    return app


async def start_server(
    app: web.Application, host: str = "127.0.0.1", port: int = 0
) -> tuple[web.AppRunner, int]:
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=_SHUTDOWN_TIMEOUT)
    await runner.setup()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    site = web.SockSite(runner, sock)
    await site.start()
    return runner, int(sock.getsockname()[1])
