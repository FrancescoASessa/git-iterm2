import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

_DRAIN_TIMEOUT = 2.0
"""Seconds `_stop_pump` waits for already-queued events to finish applying
before cancelling the pump unconditionally. Draining is best-effort;
shutdown is not — a hung handler must never block shutdown forever."""

PathHandler = Callable[[str | None, bool], Awaitable[None]]
"""`(path, has_session)`. `has_session` distinguishes "no active session at
all" (`False`) from "a session is active but its `path` variable is absent
or unreadable" (`True`, with `path is None`) -- the latter is what a missing
iTerm2 Shell Integration looks like; the former is not, since there is
simply nothing to report."""
SessionHandler = Callable[[Any | None], Awaitable[None]]
MonitorFactory = Callable[[Any], AsyncIterator[None]]
"""Given the app/connection, yields once per "something changed" event
(a focus change or a path change) — callers are expected to re-resolve
`current_session()` after each yield. Production code leaves this `None`
so `run()` builds the real iTerm2 monitors; tests inject a fake factory to
drive `run()`'s watch loop without a real iTerm2."""


class ActiveSessionTracker:
    """Feeds the active session's directory (and the session itself) to handlers.

    Events are serialized: the controller applies results in completion order,
    so a later focus change must never overtake an earlier one (spec §10).
    """

    def __init__(
        self,
        app: Any,
        on_path: PathHandler,
        on_session: SessionHandler | None = None,
        *,
        monitors: MonitorFactory | None = None,
    ) -> None:
        self._app = app
        self._on_path = on_path
        self._on_session = on_session
        self._monitors = monitors
        self._queue: asyncio.Queue[Any | None] = asyncio.Queue()

    def current_session(self) -> Any | None:
        window = getattr(self._app, "current_terminal_window", None)
        tab = getattr(window, "current_tab", None) if window is not None else None
        return getattr(tab, "current_session", None) if tab is not None else None

    async def enqueue(self, session: Any | None) -> None:
        await self._queue.put(session)

    async def handle_event(self, session: Any | None) -> None:
        path: str | None = None
        if session is not None:
            try:
                value = await session.async_get_variable("path")
            except Exception:
                logger.exception("could not read the session path")
                value = None
            path = value if isinstance(value, str) and value else None
        await self._on_path(path, session is not None)
        if self._on_session is not None:
            await self._on_session(session)

    async def pump(self) -> None:
        while True:
            session = await self._queue.get()
            try:
                await self.handle_event(session)
            except Exception:
                logger.exception("failed to apply a focus event")
            finally:
                self._queue.task_done()

    async def _stop_pump(self, pump: "asyncio.Task[None]") -> None:
        # Wait (best-effort, bounded) for every event already queued to be
        # applied — `put`/`get` on an unbounded queue can both complete
        # without truly suspending the caller, so cancelling immediately
        # could drop events that are sitting in the buffer but not yet
        # processed. `join()` blocks until `task_done()` has been called for
        # everything put so far. But draining is best-effort, not a
        # guarantee: a handler that hangs (blocked I/O in `on_path`/
        # `on_session`) must never block shutdown forever, so the wait is
        # bounded by `_DRAIN_TIMEOUT` and the cancel below is unconditional
        # regardless of whether the drain finished. `shield` keeps a
        # timed-out `join()` from turning a cancellation of this coroutine
        # itself into a stray, unawaited task.
        try:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(self._queue.join()), _DRAIN_TIMEOUT)
        finally:
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump

    async def run(self) -> None:
        """Watch iTerm2 for focus and path changes.

        With an injected `monitors` factory (tests only — production code
        leaves it `None`), the factory's async iterator drives the watch
        loop directly, with no dependency on `iterm2` at all: this is the
        seam that makes the watch-loop assembly itself testable.

        With no factory (the real, production path), this builds the real
        iTerm2 monitors, imported lazily so the module has no import-time
        dependency on `iterm2`. If `iterm2` is not installed, it degrades
        gracefully: applies the current session once (there is nothing to
        watch without the real library) and then idles, so an entry point
        can still drive this tracker without a real iTerm2 attached.
        """
        if self._monitors is not None:
            await self.enqueue(self.current_session())
            pump = asyncio.create_task(self.pump())
            try:
                async for _ in self._monitors(self._app):
                    await self.enqueue(self.current_session())
            finally:
                await self._stop_pump(pump)
            return

        try:
            import iterm2
        except ImportError:
            logger.warning("iterm2 is not installed; applying the active session once and idling")
            await self.handle_event(self.current_session())
            await asyncio.Event().wait()
            return

        await self.enqueue(self.current_session())
        pump = asyncio.create_task(self.pump())

        async def watch_focus() -> None:
            async with iterm2.FocusMonitor(self._app.connection) as monitor:
                while True:
                    await monitor.async_get_next_update()
                    await self.enqueue(self.current_session())

        async def watch_path() -> None:
            async with iterm2.VariableMonitor(
                self._app.connection, iterm2.VariableScopes.SESSION, "path", "active"
            ) as monitor:
                while True:
                    await monitor.async_get()
                    await self.enqueue(self.current_session())

        try:
            await asyncio.gather(watch_focus(), watch_path())
        finally:
            await self._stop_pump(pump)
