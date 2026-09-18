import asyncio
import builtins
import contextlib
import sys
import types
from collections.abc import AsyncIterator

import pytest

from git_iterm2.iterm import focus as focus_module
from git_iterm2.iterm.focus import ActiveSessionTracker
from tests.iterm.fakes import FakeSession, app_with


async def test_reports_the_active_session_path() -> None:
    session = FakeSession(variables={"path": "/tmp/repo"})
    seen: list[str | None] = []

    tracker = ActiveSessionTracker(
        app_with(session), on_path=lambda path, has_session: _record(seen, path)
    )
    await tracker.handle_event(session)

    assert seen == ["/tmp/repo"]


async def test_reports_none_without_a_session_or_path() -> None:
    seen: list[str | None] = []
    tracker = ActiveSessionTracker(
        app_with(None), on_path=lambda path, has_session: _record(seen, path)
    )

    await tracker.handle_event(None)
    await tracker.handle_event(FakeSession(variables={}))

    assert seen == [None, None]


async def test_reports_whether_a_session_is_active() -> None:
    """`has_session` is what lets a caller (`panel.py`) tell "no session at
    all" (nothing to say about Shell Integration) apart from "a session with
    no readable `path` variable" (Shell Integration missing)."""
    seen: list[tuple[str | None, bool]] = []

    async def on_path(path: str | None, has_session: bool) -> None:
        seen.append((path, has_session))

    tracker = ActiveSessionTracker(app_with(None), on_path=on_path)

    await tracker.handle_event(None)
    await tracker.handle_event(FakeSession(variables={}))
    await tracker.handle_event(FakeSession(variable_error=RuntimeError("session went away")))
    await tracker.handle_event(FakeSession(variables={"path": "/tmp/repo"}))

    assert seen == [
        (None, False),
        (None, True),
        (None, True),
        ("/tmp/repo", True),
    ]


async def test_events_are_applied_in_order_even_when_a_handler_is_slow() -> None:
    order: list[str | None] = []
    first = asyncio.Event()

    async def slow(path: str | None, has_session: bool) -> None:
        if path == "/first":
            await first.wait()
        order.append(path)

    tracker = ActiveSessionTracker(app_with(None), on_path=slow)
    pump = asyncio.create_task(tracker.pump())
    try:
        await tracker.enqueue(FakeSession(variables={"path": "/first"}))
        await tracker.enqueue(FakeSession(variables={"path": "/second"}))
        await asyncio.sleep(0)
        assert order == []  # the first handler is still blocked
        first.set()
        await asyncio.sleep(0.05)
        assert order == ["/first", "/second"]
    finally:
        pump.cancel()


async def test_also_reports_the_session_for_theme_reads() -> None:
    session = FakeSession(variables={"path": "/tmp/repo"})
    sessions: list[object | None] = []

    tracker = ActiveSessionTracker(
        app_with(session),
        on_path=lambda path, has_session: _noop(),
        on_session=lambda value: _record(sessions, value),
    )
    await tracker.handle_event(session)

    assert sessions == [session]


async def test_handle_event_swallows_a_raising_variable_read() -> None:
    """A real iTerm2 RPC can fail (e.g. the session went away). `handle_event`
    must still report `on_path(None)` rather than propagating the error."""
    session = FakeSession(variable_error=RuntimeError("session went away"))
    seen: list[str | None] = []
    tracker = ActiveSessionTracker(
        app_with(session), on_path=lambda path, has_session: _record(seen, path)
    )

    await tracker.handle_event(session)  # must not raise

    assert seen == [None]


async def test_pump_applies_the_next_event_after_a_raising_one() -> None:
    """A raising session must not stop the pump from applying later events."""
    seen: list[str | None] = []
    applied_second = asyncio.Event()

    async def on_path(path: str | None, has_session: bool) -> None:
        seen.append(path)
        if path == "/second":
            applied_second.set()

    tracker = ActiveSessionTracker(app_with(None), on_path=on_path)
    pump = asyncio.create_task(tracker.pump())
    try:
        await tracker.enqueue(FakeSession(variable_error=RuntimeError("boom")))
        await tracker.enqueue(FakeSession(variables={"path": "/second"}))
        await asyncio.wait_for(applied_second.wait(), timeout=1)
        assert seen == [None, "/second"]
    finally:
        pump.cancel()


async def test_stop_pump_does_not_hang_forever_on_a_stuck_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Draining is best-effort, not a guarantee: a handler that never
    returns (e.g. blocked I/O in `on_path`) must not block `_stop_pump`
    forever, and the pump must still end up cancelled once the bounded
    drain wait times out."""
    monkeypatch.setattr(focus_module, "_DRAIN_TIMEOUT", 0.05)
    stuck = asyncio.Event()  # deliberately never set

    async def hangs(path: str | None, has_session: bool) -> None:
        await stuck.wait()

    tracker = ActiveSessionTracker(app_with(None), on_path=hangs)
    pump = asyncio.create_task(tracker.pump())
    await tracker.enqueue(FakeSession(variables={"path": "/hung"}))
    await asyncio.sleep(0)  # let the pump pick up the event and block inside `hangs`

    await asyncio.wait_for(tracker._stop_pump(pump), timeout=1)  # must not hang

    assert pump.cancelled()


async def test_run_drives_the_watch_loop_via_an_injected_monitor_factory() -> None:
    """The real watch-loop assembly (apply once, then re-resolve and enqueue
    the current session on every "something changed" event, pump running
    alongside, joined at the end) is otherwise untestable without a real
    iTerm2. An injected `MonitorFactory` proves it end to end."""
    first = FakeSession(session_id="first", variables={"path": "/first"})
    second = FakeSession(session_id="second", variables={"path": "/second"})
    app = app_with(first)
    seen: list[str | None] = []

    async def fake_monitors(watched_app: object) -> AsyncIterator[None]:
        assert watched_app is app
        yield None  # first "something changed" event: session is still `first`
        assert app.current_terminal_window is not None
        assert app.current_terminal_window.current_tab is not None
        app.current_terminal_window.current_tab.current_session = second
        yield None  # second event: session is now `second`
        # then the factory's iterator ends

    tracker = ActiveSessionTracker(
        app, on_path=lambda path, has_session: _record(seen, path), monitors=fake_monitors
    )

    task = asyncio.create_task(tracker.run())
    await asyncio.wait_for(task, timeout=1)  # deterministic: waits for run() to finish itself

    assert task.done()  # run() returned once the factory's iterator ended
    assert seen == ["/first", "/first", "/second"]


async def test_run_degrades_without_iterm2_by_applying_once_then_idling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run()` must not blow up when `iterm2` is not installed.

    Task 4's entry point needs to exercise `run()` without a real iTerm2, so
    this forces the lazy `import iterm2` inside `run()` to fail regardless of
    whether the `iterm2` package happens to be installed in the test
    environment, and asserts the documented fallback: apply the current
    session once, then idle (the task never completes on its own).
    """
    session = FakeSession(variables={"path": "/tmp/repo"})
    seen: list[str | None] = []
    tracker = ActiveSessionTracker(
        app_with(session), on_path=lambda path, has_session: _record(seen, path)
    )

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "iterm2":
            raise ImportError("iterm2 is not installed")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)

    task = asyncio.create_task(tracker.run())
    await asyncio.sleep(0.05)

    assert seen == ["/tmp/repo"]
    assert not task.done()  # idles rather than returning

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def _record(sink: list, value: object) -> None:  # type: ignore[type-arg]
    sink.append(value)


async def _noop() -> None:
    return None


class _FakeFocusMonitor:
    """Raises from `async_get_next_update`, the way a real `FocusMonitor`
    does when its connection drops."""

    def __init__(self, connection: object) -> None:
        self.connection = connection

    async def __aenter__(self) -> "_FakeFocusMonitor":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def async_get_next_update(self) -> None:
        raise RuntimeError("focus monitor died")


class _FakeVariableMonitor:
    """Polls forever, and records whether it was cancelled and closed."""

    cancelled = asyncio.Event()
    exited = asyncio.Event()

    def __init__(self, connection: object, scope: object, name: str, target: str) -> None:
        self.connection = connection

    async def __aenter__(self) -> "_FakeVariableMonitor":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        type(self).exited.set()
        return False

    async def async_get(self) -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            type(self).cancelled.set()
            raise


async def test_run_cancels_the_path_watcher_when_the_focus_monitor_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run()`'s production branch used a plain `asyncio.gather`, which does
    not cancel its sibling when one child raises. With `FocusMonitor` dead,
    `watch_path` kept polling and enqueueing into a queue whose pump had
    already been cancelled in the `finally` -- an orphan task holding an
    open `VariableMonitor` for the rest of the process's life.

    Stubs `iterm2` in `sys.modules` so `run()` takes the real production
    branch (the injected-`monitors` seam would not exercise it).
    """
    _FakeVariableMonitor.cancelled = asyncio.Event()
    _FakeVariableMonitor.exited = asyncio.Event()
    fake_iterm2 = types.SimpleNamespace(
        FocusMonitor=_FakeFocusMonitor,
        VariableMonitor=_FakeVariableMonitor,
        VariableScopes=types.SimpleNamespace(SESSION="session"),
    )
    monkeypatch.setitem(sys.modules, "iterm2", fake_iterm2)

    session = FakeSession(variables={"path": "/tmp/repo"})
    app = app_with(session)
    app.connection = object()  # type: ignore[attr-defined]
    tracker = ActiveSessionTracker(app, on_path=lambda path, has_session: _noop())

    before = asyncio.all_tasks()
    with pytest.raises(RuntimeError, match="focus monitor died"):
        await tracker.run()

    assert _FakeVariableMonitor.cancelled.is_set(), "the path watcher was left running"
    assert _FakeVariableMonitor.exited.is_set(), "the VariableMonitor was never closed"
    await asyncio.sleep(0)
    leftover = asyncio.all_tasks() - before - {asyncio.current_task()}  # type: ignore[arg-type]
    assert not [task for task in leftover if not task.done()], "a task was left pending"
