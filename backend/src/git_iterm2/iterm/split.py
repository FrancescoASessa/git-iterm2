import logging
import shlex
from collections.abc import Awaitable, Callable
from typing import Any

from git_iterm2.git.repo import RepoPaths

logger = logging.getLogger(__name__)

SplitOpener = Callable[[RepoPaths, str, bool], Awaitable[None]]


def build_diff_command(rel_path: str, staged: bool) -> str:
    parts = ["git", "diff", "--no-ext-diff"]
    if staged:
        parts.append("--cached")
    parts.extend(["--", shlex.quote(rel_path)])
    return " ".join(parts)


def _current_session(app: Any) -> Any | None:
    window = getattr(app, "current_terminal_window", None)
    tab = getattr(window, "current_tab", None) if window is not None else None
    return getattr(tab, "current_session", None) if tab is not None else None


def make_split_opener(app: Any) -> SplitOpener:
    async def open_diff_split(paths: RepoPaths, rel: str, staged: bool) -> None:
        session = _current_session(app)
        if session is None:
            logger.warning("no active session to split")
            return
        new_session = await session.async_split_pane(vertical=True)
        command = f"cd {shlex.quote(str(paths.root))} && {build_diff_command(rel, staged)}\n"
        await new_session.async_send_text(command)

    return open_diff_split
