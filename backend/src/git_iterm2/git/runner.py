import asyncio
import contextlib
import os
import re
import signal
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from git_iterm2.errors import ErrorCode, GitError, classify_stderr

GIT_ENV_OVERRIDES = {
    "GIT_TERMINAL_PROMPT": "0",
    "LC_ALL": "C",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_EDITOR": "true",
    "GIT_LITERAL_PATHSPECS": "1",
}
# Neutralise user configuration that would change machine-parsed output. External diff
# drivers are disabled per invocation with --no-ext-diff: `-c diff.external=` makes git
# try to run an empty command instead of clearing the setting.
BASE_ARGS = (
    "-c",
    "color.ui=false",
    "-c",
    "color.diff=false",
    "-c",
    "color.status=false",
    "-c",
    "color.branch=false",
    "-c",
    "log.showSignature=false",
    "-c",
    "core.pager=cat",
    "-c",
    "core.quotepath=false",
)

LineHandler = Callable[[str], Awaitable[None]]

_LINE_SPLIT = re.compile(rb"[\r\n]")


@dataclass(frozen=True)
class GitResult:
    stdout: str
    stderr: str
    returncode: int


def git_env(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update(GIT_ENV_OVERRIDES)
    if overrides:
        env.update(overrides)
    return env


def _failure(args: tuple[str, ...], result: GitResult) -> GitError:
    code = classify_stderr(f"{result.stderr}\n{result.stdout}")
    stderr_lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    first = next(
        (line for line in stderr_lines if line.startswith(("fatal:", "error:"))),
        next(iter(stderr_lines + stdout_lines), ""),
    )
    message = first.removeprefix("fatal:").removeprefix("error:").strip() or f"git {args[0]} failed"
    return GitError(code, message, result.stderr)


async def run_git(
    cwd: Path,
    *args: str,
    check: bool = True,
    stdin: str | None = None,
    env: Mapping[str, str] | None = None,
) -> GitResult:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *BASE_ARGS,
        *args,
        cwd=cwd,
        env=git_env(env),
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    out, err = await proc.communicate(stdin.encode() if stdin is not None else None)
    assert proc.returncode is not None
    result = GitResult(
        out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), proc.returncode
    )
    if check and result.returncode != 0:
        raise _failure(args, result)
    return result


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    """Kill git and everything it spawned (ssh, credential helpers, hooks)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        with contextlib.suppress(ProcessLookupError):
            proc.kill()


async def stream_git(
    cwd: Path, *args: str, on_line: LineHandler, idle_timeout: float | None = None
) -> GitResult:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *BASE_ARGS,
        *args,
        cwd=cwd,
        env=git_env(),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    assert proc.stdout is not None and proc.stderr is not None
    stderr = proc.stderr
    stdout_task = asyncio.create_task(proc.stdout.read())
    tail: deque[str] = deque(maxlen=200)
    pending = b""

    async def emit(raw: bytes) -> None:
        if raw:
            line = raw.decode("utf-8", "replace")
            tail.append(line)
            await on_line(line)

    async def read_chunk() -> bytes:
        async with asyncio.timeout(idle_timeout):
            return await stderr.read(4096)

    try:
        while True:
            try:
                chunk = await read_chunk()
            except TimeoutError:
                raise GitError(
                    ErrorCode.GIT_FAILED, f"git {args[0]} timed out with no output"
                ) from None
            if not chunk:
                break
            pending += chunk
            *complete, pending = _LINE_SPLIT.split(pending)
            for raw in complete:
                await emit(raw)
        await emit(pending)
        stdout = await stdout_task
        returncode = await proc.wait()
    except BaseException:
        stdout_task.cancel()
        if proc.returncode is None:
            _kill_group(proc)
            await asyncio.shield(proc.wait())
        raise

    result = GitResult(stdout.decode("utf-8", "replace"), "\n".join(tail), returncode)
    if returncode != 0:
        raise _failure(args, result)
    return result
