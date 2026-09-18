"""Tests for `git_iterm2.concurrency.run_concurrently`.

Shared by `panel.run_panel` (server + focus tracker) and `focus.run()`
(focus watcher + path watcher); `focus.py` must not import `panel.py` to
get it.
"""

import asyncio
import contextlib
import logging

import pytest

import git_iterm2.concurrency as concurrency_module
from git_iterm2.concurrency import run_concurrently


async def test_run_concurrently_cancels_the_sibling_when_one_raises() -> None:
    """Plain `asyncio.gather` does not cancel siblings on an exception: if
    `poll_forever` raised while `tracker.run()` kept going, the tracker (and
    its iTerm2 monitors) would run forever behind a server that already
    unwound via `runner.cleanup()`. `_run_concurrently` must cancel and await
    whichever coroutine is still running as soon as the other ends."""
    sibling_cancelled = asyncio.Event()

    async def raises() -> None:
        await asyncio.sleep(0)
        raise RuntimeError("boom")

    async def forever() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            sibling_cancelled.set()
            raise

    with pytest.raises(RuntimeError, match="boom"):
        await run_concurrently([raises(), forever()])

    assert sibling_cancelled.is_set()


async def test_run_concurrently_logs_if_the_cancelled_sibling_raises_something_else(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`asyncio.gather(..., return_exceptions=True)`'s result was never
    inspected: if the sibling being cancelled raised something other than
    `CancelledError` (e.g. a bug in its own cancellation handling, or a
    genuine race where it fails in the same tick it's cancelled), that
    exception vanished with no log line at all."""

    async def raises() -> None:
        await asyncio.sleep(0)
        raise RuntimeError("boom")

    async def misbehaves_on_cancel() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise RuntimeError("cleanup blew up") from None

    caplog.set_level(logging.ERROR, logger="git_iterm2.concurrency")
    with pytest.raises(RuntimeError, match="boom"):
        await run_concurrently([raises(), misbehaves_on_cancel()])

    assert "cleanup blew up" in caplog.text


async def test_siblings_finish_unwinding_before_a_cancelled_caller_returns() -> None:
    """`run_panel` cancels `tracker.run()`, and `tracker.run()` is itself a
    `run_concurrently` over two iTerm2 monitors. If the inner cleanup gather
    re-raises `CancelledError` before its siblings have unwound, a real
    `VariableMonitor.__aexit__` may not have run by the time
    `runner.cleanup()` starts -- an iTerm2 monitor outliving the panel,
    which is the whole point of the sibling-cancellation fix.
    """
    released = asyncio.Event()

    async def holds_a_resource() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.05)  # `__aexit__` doing real work
            released.set()
            raise

    async def forever() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(run_concurrently([holds_a_resource(), forever()]))
    await asyncio.sleep(0.01)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert released.is_set(), "the caller returned before a sibling had released its resource"


async def test_a_sibling_that_refuses_to_unwind_is_abandoned(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Letting siblings unwind is best-effort; shutting down is not. A
    coroutine that swallows its cancellation must not hold the panel open,
    and must not lose the exception that started the teardown."""
    monkeypatch.setattr(concurrency_module, "_CLEANUP_TIMEOUT", 0.05)

    async def raises() -> None:
        await asyncio.sleep(0)
        raise RuntimeError("boom")

    async def never_unwinds() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.Event().wait()  # ignores the cancel forever

    caplog.set_level(logging.ERROR, logger="git_iterm2.concurrency")
    with pytest.raises(RuntimeError, match="boom"):
        await asyncio.wait_for(run_concurrently([raises(), never_unwinds()]), timeout=2.0)

    assert "did not unwind" in caplog.text


async def test_a_second_cancel_cannot_cut_the_unwinding_short() -> None:
    """One cancel is delivered once, so the `finally`'s own awaits survive
    it. A *second* cancel -- a supervisor that cancels, waits, and cancels
    again, or a loop tearing every task down -- lands while the siblings are
    still unwinding, and an unshielded wait there would abandon a live
    `VariableMonitor` mid-`__aexit__`.
    """
    released = asyncio.Event()
    unwinding = asyncio.Event()

    async def holds_a_resource() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            unwinding.set()  # we are provably inside the cleanup now
            await asyncio.sleep(0.05)  # `__aexit__` doing real work
            released.set()
            raise

    async def forever() -> None:
        await asyncio.Event().wait()

    task = asyncio.create_task(run_concurrently([holds_a_resource(), forever()]))
    await asyncio.sleep(0.01)
    task.cancel()
    await asyncio.wait_for(unwinding.wait(), timeout=1.0)
    task.cancel()  # lands squarely in the middle of the sibling's unwind
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert released.is_set(), "a second cancel abandoned a sibling mid-unwind"
