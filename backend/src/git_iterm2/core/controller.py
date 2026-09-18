import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

from git_iterm2.core.fingerprint import Fingerprint, repo_fingerprint
from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.remote import RemoteOp, run_remote_op
from git_iterm2.git.repo import RepoPaths, find_repo
from git_iterm2.git.status import read_snapshot
from git_iterm2.models import (
    ErrorBody,
    OpDoneMessage,
    OpProgressMessage,
    RepoSnapshot,
    ServerMessage,
    SnapshotMessage,
    Theme,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
Listener = Callable[[ServerMessage], Awaitable[None]]


class RepoController:
    def __init__(self, poll_interval: float = 1.0, status_interval: float = 2.0) -> None:
        self._poll_interval = poll_interval
        self._status_interval = status_interval
        self._paths: RepoPaths | None = None
        self._theme: Theme | None = None
        self._snapshot: RepoSnapshot | None = None
        self._listeners: list[Listener] = []
        self._locks: dict[Path, asyncio.Lock] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def paths(self) -> RepoPaths | None:
        return self._paths

    @property
    def snapshot(self) -> RepoSnapshot | None:
        return self._snapshot

    @property
    def listener_count(self) -> int:
        return len(self._listeners)

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    async def _emit(self, message: ServerMessage) -> None:
        for listener in list(self._listeners):
            try:
                await listener(message)
            except Exception:
                logger.exception("listener failed")

    async def set_active_path(self, path: Path | None) -> None:
        paths = await find_repo(path) if path is not None else None
        if paths == self._paths:
            return
        self._paths = paths
        await self.refresh(force=True)

    async def set_theme(self, theme: Theme | None) -> None:
        if theme == self._theme:
            return
        self._theme = theme
        await self.refresh(force=True)

    async def refresh(self, force: bool = False) -> None:
        paths = self._paths
        snapshot: RepoSnapshot | None = None
        if paths is not None:
            try:
                snapshot = await read_snapshot(paths, self._theme)
            except (GitError, OSError):
                logger.warning("could not read snapshot for %s", paths.root, exc_info=True)
        if paths is not self._paths:
            return
        if force or snapshot != self._snapshot:
            self._snapshot = snapshot
            await self._emit(SnapshotMessage(repo=snapshot))

    def require_paths(self) -> RepoPaths:
        if self._paths is None:
            raise GitError(
                ErrorCode.NOT_A_REPO, "The active session is not inside a git repository"
            )
        return self._paths

    def _lock(self, paths: RepoPaths) -> asyncio.Lock:
        return self._locks.setdefault(paths.common_dir, asyncio.Lock())

    async def query(self, fn: Callable[[RepoPaths], Awaitable[T]]) -> T:
        return await fn(self.require_paths())

    async def action(self, fn: Callable[[RepoPaths], Awaitable[T]]) -> T:
        paths = self.require_paths()
        async with self._lock(paths):
            try:
                return await fn(paths)
            finally:
                await self.refresh()

    def start_remote_op(self, op: RemoteOp) -> str:
        paths = self.require_paths()
        op_id = uuid.uuid4().hex

        async def progress(phase: str, pct: int | None, line: str) -> None:
            await self._emit(OpProgressMessage(op_id=op_id, phase=phase, pct=pct, line=line))

        async def run() -> None:
            error: ErrorBody | None = None
            async with self._lock(paths):
                try:
                    await run_remote_op(paths.root, op, progress)
                except GitError as git_error:
                    error = ErrorBody.from_error(git_error)
                except Exception as unexpected:
                    logger.exception("remote %s failed", op)
                    error = ErrorBody(
                        code=ErrorCode.GIT_FAILED,
                        message=str(unexpected) or type(unexpected).__name__,
                    )
                finally:
                    await self.refresh()
            await self._emit(OpDoneMessage(op_id=op_id, ok=error is None, error=error))

        task = asyncio.create_task(run())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return op_id

    async def wait_for_ops(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks)

    async def poll_forever(self) -> None:
        last_fingerprint: Fingerprint | None = None
        since_status = 0.0
        while True:
            await asyncio.sleep(self._poll_interval)
            try:
                paths = self._paths
                if paths is None or not self._listeners:
                    last_fingerprint = None
                    continue
                if self._lock(paths).locked():
                    continue
                fingerprint = repo_fingerprint(paths)
                since_status += self._poll_interval
                if fingerprint != last_fingerprint or since_status >= self._status_interval:
                    last_fingerprint = fingerprint
                    since_status = 0.0
                    await self.refresh()
            except Exception:
                logger.exception("poll iteration failed")
