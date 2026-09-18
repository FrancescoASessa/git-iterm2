from collections.abc import Sequence
from pathlib import Path

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.repo import has_head
from git_iterm2.git.runner import run_git
from git_iterm2.git.validation import validate_repo_paths


def _split_z(output: str) -> list[str]:
    return [item for item in output.split("\0") if item]


async def stage(root: Path, paths: Sequence[str]) -> None:
    rels = validate_repo_paths(paths)
    await run_git(root, "add", "-A", "--", *rels)


async def unstage(root: Path, paths: Sequence[str]) -> None:
    rels = validate_repo_paths(paths)
    if await has_head(root):
        await run_git(root, "restore", "--staged", "--", *rels)
    else:
        await run_git(root, "rm", "--cached", "-r", "-q", "--", *rels)


async def discard(root: Path, paths: Sequence[str]) -> None:
    rels = validate_repo_paths(paths)
    untracked_result = await run_git(
        root, "ls-files", "--others", "--exclude-standard", "-z", "--", *rels
    )
    untracked = _split_z(untracked_result.stdout)
    if untracked:
        await run_git(root, "clean", "-f", "-q", "--", *untracked)
    untracked_set = set(untracked)
    remaining = [rel for rel in rels if rel not in untracked_set]
    if not remaining:
        return
    tracked = _split_z((await run_git(root, "ls-files", "-z", "--", *remaining)).stdout)
    if tracked:
        await run_git(root, "restore", "--worktree", "--", *tracked)


async def commit(root: Path, message: str, amend: bool = False) -> None:
    has_message = bool(message.strip())
    if not has_message and not amend:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "Commit message is empty")
    if not amend:
        staged = await run_git(root, "diff", "--cached", "--quiet", check=False)
        if staged.returncode == 0:
            raise GitError(ErrorCode.INVALID_ARGUMENT, "Nothing staged to commit")
    args = ["commit"]
    if amend:
        args.append("--amend")
    if has_message:
        await run_git(root, *args, "-F", "-", stdin=message)
    else:
        await run_git(root, *args, "--no-edit")
