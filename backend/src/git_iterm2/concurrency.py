"""Running sibling coroutines so that one ending never orphans the others."""

import asyncio
import contextlib
import logging
from collections.abc import Coroutine, Iterable
from typing import Any

logger = logging.getLogger(__name__)

_CLEANUP_TIMEOUT = 2.0
"""Seconds the cancelled siblings get to unwind before they are abandoned.
Matches `focus._DRAIN_TIMEOUT`, and for the same reason: releasing
resources cleanly is best-effort, shutting down is not."""


def _consume_cancellation(future: "asyncio.Future[Any]") -> None:
    """Retrieve an abandoned future's own cancellation, so asyncio does not
    report it as an unretrieved exception when the future is collected --
    noise in the log (and now the Script Console) for a case we have
    already logged deliberately."""
    if not future.cancelled():
        future.exception()


async def run_concurrently(coroutines: Iterable[Coroutine[Any, Any, None]]) -> None:
    """Run coroutines concurrently. As soon as one finishes -- by returning
    or raising -- cancel and await the rest, then re-raise that one's
    exception (if it had one).

    Plain `asyncio.gather` does not cancel siblings on an exception. Every
    long-lived pair in this package owns an OS- or iTerm2-level resource, so
    a surviving sibling is not merely a wasted task: `panel.run_panel`'s
    `controller.poll_forever()` would keep polling behind a server whose
    caller has already started unwinding, and `focus.run()`'s path watcher
    would keep polling an open `VariableMonitor` and enqueueing into a queue
    whose pump has already been cancelled -- forever, and invisibly.
    """
    tasks = [asyncio.ensure_future(coro) for coro in coroutines]
    # Bound before the `try`: if the caller cancels us while `asyncio.wait`
    # is still running, the `finally` below runs with nothing having been
    # assigned, and reading an unbound `done` there would raise
    # `UnboundLocalError` *in place of* the `CancelledError` -- turning a
    # clean teardown into a spurious crash that also swallows the cancel.
    done: set[asyncio.Task[None]] = set()
    results: list[Any] = []
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        # Shielded, so that a caller cancelling *us* (`run_panel` tearing
        # the panel down) cannot cut the siblings' own unwinding short:
        # that is where `VariableMonitor.__aexit__` and friends run, and a
        # monitor released after `runner.cleanup()` has begun is the orphan
        # this module exists to prevent. Bounded all the same -- a sibling
        # that will not unwind must not hold the panel open.
        cleanup = asyncio.gather(*tasks, return_exceptions=True)
        try:
            results = await asyncio.wait_for(asyncio.shield(cleanup), _CLEANUP_TIMEOUT)
        except asyncio.CancelledError:
            # The gather is shielded, so it is still running: give it the
            # rest of its bounded chance before re-raising the cancel.
            with contextlib.suppress(asyncio.CancelledError, TimeoutError):
                results = await asyncio.wait_for(cleanup, _CLEANUP_TIMEOUT)
            raise
        except TimeoutError:
            # Abandon them. Awaiting the cancelled gather is not an option:
            # its children are precisely the ones that will not unwind.
            cleanup.cancel()
            cleanup.add_done_callback(_consume_cancellation)
            logger.error(
                "a concurrently-run coroutine did not unwind within %.1fs of being cancelled",
                _CLEANUP_TIMEOUT,
            )
        # `results` is empty if the bounded wait above gave up, in which
        # case there is nothing to report and `strict=True` would raise.
        for task, result in zip(tasks, results, strict=True) if results else []:
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
