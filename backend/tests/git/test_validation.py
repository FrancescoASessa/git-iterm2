from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.validation import (
    validate_branch_name,
    validate_repo_paths,
    validate_revision,
    validate_start_point,
)


def test_validate_repo_paths_normalizes() -> None:
    assert validate_repo_paths(["a.txt", "dir/b.txt", "./c", "d/../e"]) == [
        "a.txt",
        "dir/b.txt",
        "c",
        "e",
    ]


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a/../../x", "", "a\x00b", ".."])
def test_validate_repo_paths_rejects_escapes(bad: str) -> None:
    with pytest.raises(GitError) as info:
        validate_repo_paths([bad])
    assert info.value.code is ErrorCode.INVALID_PATH


def test_validate_repo_paths_rejects_empty_list() -> None:
    with pytest.raises(GitError) as info:
        validate_repo_paths([])
    assert info.value.code is ErrorCode.INVALID_ARGUMENT


async def test_validate_branch_name(repo: Path) -> None:
    assert await validate_branch_name(repo, "feature/x") == "feature/x"
    for bad in ["", "-rf", "bad..name", "with space"]:
        with pytest.raises(GitError) as info:
            await validate_branch_name(repo, bad)
        assert info.value.code is ErrorCode.INVALID_ARGUMENT


async def test_validate_start_point(repo: Path) -> None:
    assert await validate_start_point(repo, "main") == "main"
    for bad in ["", "--all", "does-not-exist"]:
        with pytest.raises(GitError) as info:
            await validate_start_point(repo, bad)
        assert info.value.code is ErrorCode.INVALID_ARGUMENT


def test_validate_revision() -> None:
    assert validate_revision("abc1234") == "abc1234"
    for bad in ["HEAD~1", "--all", "xyz", "abc"]:
        with pytest.raises(GitError) as info:
            validate_revision(bad)
        assert info.value.code is ErrorCode.INVALID_ARGUMENT
