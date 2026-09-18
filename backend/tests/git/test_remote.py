from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.remote import parse_progress, remote_args, run_remote_op
from tests.helpers import commit_file, git


async def ignore(phase: str, pct: int | None, line: str) -> None:
    return None


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Receiving objects:  45% (9/20)", ("Receiving objects", 45)),
        ("remote: Counting objects: 100% (3/3), done.", ("Counting objects", 100)),
        ("From /tmp/remote", ("", None)),
    ],
)
def test_parse_progress(line: str, expected: tuple[str, int | None]) -> None:
    assert parse_progress(line) == expected


async def test_push(remote_pair: tuple[Path, Path]) -> None:
    repo, bare = remote_pair
    sha = commit_file(repo, "b.txt", "b\n", "second")
    await run_remote_op(repo, "push", ignore)
    assert git(bare, "rev-parse", "main").strip() == sha


async def test_push_new_branch_sets_upstream(remote_pair: tuple[Path, Path]) -> None:
    repo, bare = remote_pair
    git(repo, "switch", "-q", "-c", "feature")
    assert await remote_args(repo, "push") == [
        "push", "--progress", "--set-upstream", "origin", "feature",
    ]
    await run_remote_op(repo, "push", ignore)
    assert git(repo, "rev-parse", "--abbrev-ref", "@{upstream}").strip() == "origin/feature"
    assert git(bare, "branch", "--format=%(refname:short)").split() == ["feature", "main"]


async def test_push_rejected_is_non_fast_forward(
    tmp_path: Path, remote_pair: tuple[Path, Path]
) -> None:
    repo, bare = remote_pair
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(bare), str(other))
    commit_file(other, "o.txt", "o\n", "other side")
    git(other, "push", "-q")
    commit_file(repo, "l.txt", "l\n", "local side")
    with pytest.raises(GitError) as info:
        await run_remote_op(repo, "push", ignore)
    assert info.value.code is ErrorCode.NON_FAST_FORWARD


async def test_fetch_and_pull(tmp_path: Path, remote_pair: tuple[Path, Path]) -> None:
    repo, bare = remote_pair
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(bare), str(other))
    sha = commit_file(other, "o.txt", "o\n", "other side")
    git(other, "push", "-q")

    lines: list[str] = []

    async def record(phase: str, pct: int | None, line: str) -> None:
        lines.append(line)

    await run_remote_op(repo, "fetch", record)
    assert git(repo, "rev-parse", "origin/main").strip() == sha
    await run_remote_op(repo, "pull", ignore)
    assert git(repo, "rev-parse", "HEAD").strip() == sha


async def test_push_without_remote_fails(repo: Path) -> None:
    with pytest.raises(GitError) as info:
        await run_remote_op(repo, "push", ignore)
    assert info.value.code is ErrorCode.INVALID_ARGUMENT
