import re
from pathlib import Path
from typing import Literal

from git_iterm2.git.runner import run_git
from git_iterm2.models import StashEntry

StashAction = Literal["apply", "pop", "drop"]

_STASH_REF = re.compile(r"stash@\{(\d+)\}")


async def list_stashes(root: Path) -> list[StashEntry]:
    result = await run_git(
        root, "stash", "list", "--format=%gd%x00%H%x00%ct%x00%gs", check=False
    )
    if result.returncode != 0:
        return []
    entries: list[StashEntry] = []
    for line in result.stdout.splitlines():
        ref, sha, timestamp, message = line.split("\x00", 3)
        match = _STASH_REF.fullmatch(ref)
        if match:
            entries.append(
                StashEntry(
                    index=int(match.group(1)), message=message, sha=sha, timestamp=int(timestamp)
                )
            )
    return entries


async def push_stash(root: Path, message: str = "", include_untracked: bool = False) -> None:
    args = ["stash", "push"]
    if include_untracked:
        args.append("--include-untracked")
    if message:
        args.extend(["-m", message])
    # stash -u cleans with pathspec magic, which GIT_LITERAL_PATHSPECS=1 disables
    env = {"GIT_LITERAL_PATHSPECS": "0"} if include_untracked else None
    await run_git(root, *args, env=env)


async def stash_entry_action(root: Path, index: int, action: StashAction) -> None:
    await run_git(root, "stash", action, f"stash@{{{index}}}")
