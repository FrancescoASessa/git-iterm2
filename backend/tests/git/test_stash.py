from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.stash import list_stashes, push_stash, stash_entry_action
from tests.helpers import commit_file, git, write


async def test_push_and_list(repo: Path) -> None:
    write(repo, "README.md", "wip\n")
    await push_stash(repo, message="wip change")
    entries = await list_stashes(repo)
    assert len(entries) == 1
    assert entries[0].index == 0
    assert "wip change" in entries[0].message
    assert len(entries[0].sha) == 40
    assert (repo / "README.md").read_text() == "hello\n"


async def test_push_without_include_untracked_keeps_untracked_files(repo: Path) -> None:
    write(repo, "README.md", "wip\n")
    write(repo, "new.txt", "n\n")
    await push_stash(repo)
    assert (repo / "new.txt").exists()
    assert (repo / "README.md").read_text() == "hello\n"


async def test_push_include_untracked(repo: Path) -> None:
    write(repo, "new.txt", "n\n")
    await push_stash(repo, include_untracked=True)
    assert not (repo / "new.txt").exists()
    assert len(await list_stashes(repo)) == 1


async def test_apply_keeps_entry_and_pop_removes_it(repo: Path) -> None:
    write(repo, "README.md", "wip\n")
    await push_stash(repo)
    await stash_entry_action(repo, 0, "apply")
    assert (repo / "README.md").read_text() == "wip\n"
    assert len(await list_stashes(repo)) == 1
    git(repo, "checkout", "--", "README.md")
    await stash_entry_action(repo, 0, "pop")
    assert (repo / "README.md").read_text() == "wip\n"
    assert await list_stashes(repo) == []


async def test_drop(repo: Path) -> None:
    write(repo, "README.md", "wip\n")
    await push_stash(repo)
    await stash_entry_action(repo, 0, "drop")
    assert await list_stashes(repo) == []


async def test_apply_conflict(repo: Path) -> None:
    write(repo, "README.md", "stashed\n")
    await push_stash(repo)
    commit_file(repo, "README.md", "committed\n", "diverge")
    with pytest.raises(GitError) as info:
        await stash_entry_action(repo, 0, "apply")
    assert info.value.code is ErrorCode.CONFLICT


async def test_missing_entry(repo: Path) -> None:
    with pytest.raises(GitError):
        await stash_entry_action(repo, 3, "drop")
