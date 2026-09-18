from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.changes import commit, discard, stage, unstage
from tests.helpers import git, write


def porcelain(repo: Path) -> str:
    return git(repo, "status", "--porcelain")


async def test_stage_modified_and_deleted(repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    write(repo, "other.txt", "x\n")
    git(repo, "add", "other.txt")
    git(repo, "commit", "-q", "-m", "other")
    (repo / "other.txt").unlink()
    await stage(repo, ["README.md", "other.txt"])
    assert porcelain(repo) == "M  README.md\nD  other.txt\n"


async def test_unstage(repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    git(repo, "add", "README.md")
    await unstage(repo, ["README.md"])
    assert porcelain(repo) == " M README.md\n"


async def test_unstage_in_repo_without_commits(empty_repo: Path) -> None:
    write(empty_repo, "a.txt", "a\n")
    git(empty_repo, "add", "a.txt")
    await unstage(empty_repo, ["a.txt"])
    assert porcelain(empty_repo) == "?? a.txt\n"


async def test_discard_tracked_and_untracked(repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    write(repo, "junk.txt", "junk\n")
    await discard(repo, ["README.md", "junk.txt"])
    assert (repo / "README.md").read_text() == "hello\n"
    assert not (repo / "junk.txt").exists()
    assert porcelain(repo) == ""


async def test_commit(repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    git(repo, "add", "README.md")
    await commit(repo, "update readme")
    assert git(repo, "log", "-1", "--format=%s").strip() == "update readme"
    assert porcelain(repo) == ""


async def test_commit_rejects_empty_message(repo: Path) -> None:
    with pytest.raises(GitError) as info:
        await commit(repo, "   ")
    assert info.value.code is ErrorCode.INVALID_ARGUMENT


async def test_commit_with_nothing_staged_fails(repo: Path) -> None:
    with pytest.raises(GitError) as info:
        await commit(repo, "nothing")
    assert info.value.code is ErrorCode.INVALID_ARGUMENT
    assert info.value.message == "Nothing staged to commit"


async def test_amend_without_message_keeps_subject(repo: Path) -> None:
    write(repo, "README.md", "amended\n")
    git(repo, "add", "README.md")
    await commit(repo, "", amend=True)
    assert git(repo, "log", "-1", "--format=%s").strip() == "initial"
    assert git(repo, "rev-list", "--count", "HEAD").strip() == "1"
    assert git(repo, "show", "HEAD:README.md") == "amended\n"
