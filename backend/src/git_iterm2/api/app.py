import socket
from pathlib import Path

from aiohttp import web

from git_iterm2.api.keys import CONFIG_KEY, CONTROLLER_KEY, ServerConfig
from git_iterm2.api.routes import add_api_routes
from git_iterm2.api.security import error_middleware, security_middleware
from git_iterm2.api.ws import websocket_handler
from git_iterm2.core.controller import RepoController


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
    add_api_routes(app)
    app.router.add_get("/ws", websocket_handler)
    _add_static_routes(app, config.static_dir)
    return app


async def start_server(
    app: web.Application, host: str = "127.0.0.1", port: int = 0
) -> tuple[web.AppRunner, int]:
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    site = web.SockSite(runner, sock)
    await site.start()
    return runner, int(sock.getsockname()[1])
