import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.runner import run_git, stream_git

RemoteOp = Literal["fetch", "pull", "push"]
REMOTE_OPS: tuple[RemoteOp, ...] = ("fetch", "pull", "push")
ProgressHandler = Callable[[str, int | None, str], Awaitable[None]]

_PROGRESS = re.compile(r"^(?:remote: )?([A-Za-z][A-Za-z ]*?):\s+(\d+)%")


def parse_progress(line: str) -> tuple[str, int | None]:
    match = _PROGRESS.match(line)
    if match is None:
        return "", None
    return match.group(1), int(match.group(2))


async def remote_args(root: Path, op: RemoteOp) -> list[str]:
    if op == "fetch":
        return ["fetch", "--all", "--prune", "--progress"]
    if op == "pull":
        return ["pull", "--progress"]
    upstream = await run_git(
        root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False
    )
    if upstream.returncode == 0:
        return ["push", "--progress"]
    branch = (await run_git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False)).stdout
    branch = branch.strip()
    if not branch:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "Cannot push a detached HEAD")
    remotes = (await run_git(root, "remote")).stdout.split()
    if "origin" in remotes:
        remote = "origin"
    elif len(remotes) == 1:
        remote = remotes[0]
    else:
        raise GitError(
            ErrorCode.INVALID_ARGUMENT, "No upstream configured and no single remote to push to"
        )
    return ["push", "--progress", "--set-upstream", remote, branch]


async def run_remote_op(root: Path, op: RemoteOp, on_progress: ProgressHandler) -> None:
    args = await remote_args(root, op)

    async def handle(line: str) -> None:
        phase, pct = parse_progress(line)
        await on_progress(phase, pct, line)

    await stream_git(root, *args, on_line=handle)
