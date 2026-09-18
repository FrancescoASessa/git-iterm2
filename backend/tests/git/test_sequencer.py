from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.repo import detect_state, find_repo
from git_iterm2.git.sequencer import abort_sequence, continue_sequence
from tests.helpers import git, make_conflict, write


async def test_abort_merge(repo: Path) -> None:
    make_conflict(repo)
    paths = await find_repo(repo)
    assert paths is not None
    await abort_sequence(paths)
    assert detect_state(paths.git_dir) == "clean"
    assert (repo / "README.md").read_text() == "main\n"


async def test_continue_merge(repo: Path) -> None:
    make_conflict(repo)
    write(repo, "README.md", "resolved\n")
    git(repo, "add", "README.md")
    paths = await find_repo(repo)
    assert paths is not None
    await continue_sequence(paths)
    assert detect_state(paths.git_dir) == "clean"
    assert len(git(repo, "log", "-1", "--format=%P").split()) == 2


async def test_continue_without_operation_fails(repo: Path) -> None:
    paths = await find_repo(repo)
    assert paths is not None
    with pytest.raises(GitError) as info:
        await continue_sequence(paths)
    assert info.value.code is ErrorCode.INVALID_ARGUMENT
