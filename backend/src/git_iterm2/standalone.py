"""Run the API for a fixed repository without iTerm2 (development and end-to-end tests)."""

import argparse
import asyncio
import contextlib
import logging
import secrets
from collections.abc import Sequence
from pathlib import Path

from git_iterm2.api.app import create_app, start_server
from git_iterm2.api.keys import ServerConfig
from git_iterm2.core.controller import RepoController


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m git_iterm2.standalone")
    parser.add_argument("--repo", type=Path, required=True, help="repository to serve")
    parser.add_argument("--port", type=int, default=0, help="port (default: random)")
    parser.add_argument("--token", default=None, help="API token (default: random)")
    parser.add_argument("--static", type=Path, default=None, help="built web UI directory")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    return parser.parse_args(argv)


async def serve(args: argparse.Namespace) -> None:
    token = args.token or secrets.token_urlsafe(32)
    controller = RepoController(poll_interval=args.poll_interval)
    await controller.set_active_path(args.repo.resolve())
    app = create_app(controller, ServerConfig(token=token, static_dir=args.static))
    runner, port = await start_server(app, port=args.port)
    print(f"git-iterm2 standalone: http://127.0.0.1:{port}/?t={token}", flush=True)
    try:
        await controller.poll_forever()
    finally:
        await runner.cleanup()


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve(parse_args(argv)))


if __name__ == "__main__":
    main()
