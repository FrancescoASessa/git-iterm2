"""AutoLaunch entry point: the git panel inside the iTerm2 toolbelt."""

import asyncio
import logging
import secrets
from collections.abc import Coroutine, Iterable
from pathlib import Path
from typing import Any

from git_iterm2.api.app import create_app, start_server
from git_iterm2.api.keys import ServerConfig
from git_iterm2.core.controller import RepoController
from git_iterm2.iterm.focus import ActiveSessionTracker
from git_iterm2.iterm.panel import register_panel
from git_iterm2.iterm.split import make_split_opener
from git_iterm2.iterm.theme import theme_from_session
from git_iterm2.logging_setup import DEFAULT_LOG_DIR, configure_logging

logger = logging.getLogger(__name__)

LOG_DIR = DEFAULT_LOG_DIR
DEFAULT_STATIC_DIR = Path(__file__).resolve().parent / "web"

_STARTUP_APPLY_TIMEOUT = 5.0
"""Seconds `run_panel` waits for the session that is active right now to be
applied (its path and theme) before registering the panel anyway. Bounded
because the iTerm2 RPCs involved (`async_get_variable`, then
`async_get_profile` inside `theme_from_session`) can stall -- iTerm2 busy or
modal, or the session closing mid-request -- and a stall here must not mean
the user never sees a panel at all. A 409 from a not-yet-applied session
self-heals on the next focus event or poll; an unregistered panel does not."""


async def get_app(connection: Any) -> Any:
    import iterm2

    return await iterm2.async_get_app(connection)


async def _run_concurrently(coroutines: Iterable[Coroutine[Any, Any, None]]) -> None:
    """Run coroutines concurrently. As soon as one finishes -- by returning
    or raising -- cancel and await the rest, then re-raise that one's
    exception (if it had one).

    Plain `asyncio.gather` does not cancel siblings on an exception: if
    `controller.poll_forever()` crashed while `tracker.run()` kept going,
    the tracker (and the iTerm2 monitors it owns) would run forever behind
    a server whose caller has already started unwinding, and vice versa.
    """
    tasks = [asyncio.ensure_future(coro) for coro in coroutines]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for task, result in zip(tasks, results, strict=True):
            # `done`'s own exception (if any) is re-raised below; this is
            # only about the *other* task(s), which we just cancelled. A
            # well-behaved coroutine raises `CancelledError` in response;
            # anything else (a bug in its own cancellation handling, or a
            # genuine race where it fails in the same tick it's cancelled)
            # must not vanish silently just because `return_exceptions=True`
            # turned it into a plain value here.
            if (
                task not in done
                and isinstance(result, BaseException)
                and not isinstance(result, asyncio.CancelledError)
            ):
                logger.error(
                    "a concurrently-run coroutine failed while being cancelled", exc_info=result
                )
    for task in done:
        task.result()


async def run_panel(connection: Any, *, static_dir: Path | None = DEFAULT_STATIC_DIR) -> None:
    token = secrets.token_urlsafe(32)
    configure_logging(token, LOG_DIR)

    app = await get_app(connection)
    controller = RepoController()
    config = ServerConfig(
        token=token,
        static_dir=static_dir if static_dir is not None and static_dir.is_dir() else None,
        open_diff_split=make_split_opener(app),
    )
    runner, port = await start_server(create_app(controller, config))
    try:
        url = f"http://127.0.0.1:{port}/?t={token}"
        logger.info("panel listening on port %s", port)

        async def on_path(path: str | None, has_session: bool) -> None:
            await controller.set_active_path(Path(path) if path is not None else None)
            # A session with no readable `path` variable means Shell
            # Integration is missing; no session at all has nothing to say,
            # so the flag stays at its default (True).
            await controller.set_shell_integration(path is not None or not has_session)

        async def on_session(session: Any | None) -> None:
            if session is None:
                await controller.set_theme(None)
                return
            try:
                await controller.set_theme(await theme_from_session(session))
            except Exception:
                logger.exception("could not read the session theme")

        tracker = ActiveSessionTracker(app, on_path=on_path, on_session=on_session)
        # Apply the session that is active right now before registering the
        # panel, so the toolbelt never shows a URL that serves stale (or no)
        # repository state for the window it opens in. Bounded by
        # `_STARTUP_APPLY_TIMEOUT`: `tracker.run()` still re-applies the
        # current session as its own first step and then keeps watching for
        # focus/path changes, so a timeout here only means the panel opens
        # to a stale/empty view for one extra cycle, not that it never
        # opens at all.
        try:
            await asyncio.wait_for(
                tracker.handle_event(tracker.current_session()), _STARTUP_APPLY_TIMEOUT
            )
        except TimeoutError:
            logger.warning(
                "applying the initial session timed out after %.1fs; registering anyway",
                _STARTUP_APPLY_TIMEOUT,
            )
        await register_panel(connection, url)
        logger.info("panel registered in the toolbelt")

        await _run_concurrently([controller.poll_forever(), tracker.run()])
    finally:
        await runner.cleanup()


def main() -> None:
    import iterm2

    iterm2.run_forever(run_panel)


if __name__ == "__main__":
    main()
