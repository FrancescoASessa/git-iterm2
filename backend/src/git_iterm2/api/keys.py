from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from aiohttp import web

from git_iterm2.core.controller import RepoController
from git_iterm2.git.repo import RepoPaths

SplitOpener = Callable[[RepoPaths, str, bool], Awaitable[None]]


@dataclass(frozen=True)
class ServerConfig:
    token: str
    static_dir: Path | None = None
    open_diff_split: SplitOpener | None = None


CONTROLLER_KEY = web.AppKey("controller", RepoController)
CONFIG_KEY = web.AppKey("config", ServerConfig)
