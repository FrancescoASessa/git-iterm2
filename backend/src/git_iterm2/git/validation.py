import os
import re
from collections.abc import Sequence
from pathlib import Path

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.runner import run_git

_REVISION = re.compile(r"[0-9a-f]{4,64}")


def validate_repo_paths(paths: Sequence[str]) -> list[str]:
    if not paths:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "No paths given")
    result: list[str] = []
    for raw in paths:
        if not raw or "\x00" in raw or os.path.isabs(raw):
            raise GitError(ErrorCode.INVALID_PATH, f"Invalid path: {raw!r}")
        normalized = os.path.normpath(raw)
        if normalized == ".." or normalized.startswith("../"):
            raise GitError(ErrorCode.INVALID_PATH, f"Path escapes the repository: {raw!r}")
        result.append(normalized)
    return result


async def validate_branch_name(cwd: Path, name: str) -> str:
    if not name or name.startswith("-"):
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Invalid branch name: {name!r}")
    result = await run_git(cwd, "check-ref-format", "--branch", name, check=False)
    if result.returncode != 0:
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Invalid branch name: {name!r}")
    return name


async def validate_start_point(cwd: Path, rev: str) -> str:
    if not rev or rev.startswith("-"):
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Invalid start point: {rev!r}")
    result = await run_git(
        cwd,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{rev}^{{commit}}",
        check=False,
    )
    if result.returncode != 0:
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Unknown start point: {rev!r}")
    return rev


def validate_revision(sha: str) -> str:
    if not _REVISION.fullmatch(sha):
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Invalid commit id: {sha!r}")
    return sha
