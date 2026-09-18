from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.branches import (
    checkout_branch,
    create_branch,
    delete_branch,
    list_branches,
    parse_for_each_ref,
    rename_branch,
    set_upstream,
)
from tests.helpers import commit_file, git, write


def current_branch(repo: Path) -> str:
    return git(repo, "branch", "--show-current").strip()


def test_parse_for_each_ref() -> None:
    output = "\n".join(
        [
            "\x00".join(["refs/heads/main", "main", "*", "origin/main", "ahead 2, behind 1",
                         "aaaa", "subject one", "100"]),
            "\x00".join(["refs/heads/gone", "gone", " ", "origin/gone", "gone",
                         "bbbb", "subject two", "200"]),
            "\x00".join(["refs/remotes/origin/HEAD", "origin", " ", "", "", "aaaa", "s", "100"]),
            "\x00".join(["refs/remotes/origin/main", "origin/main", " ", "", "",
                         "cccc", "subject three", "300"]),
        ]
    )
    branches = parse_for_each_ref(output)
    assert [b.name for b in branches.local] == ["main", "gone"]
    main = branches.local[0]
    assert main.is_current and not main.is_remote
    assert (main.upstream, main.ahead, main.behind) == ("origin/main", 2, 1)
    gone = branches.local[1]
    assert (gone.upstream, gone.ahead, gone.behind) == ("origin/gone", None, None)
    assert [b.name for b in branches.remote] == ["origin/main"]
    assert branches.remote[0].is_remote
    assert branches.remote[0].last_commit_ts == 300


async def test_list_branches(remote_pair: tuple[Path, Path]) -> None:
    repo, _ = remote_pair
    git(repo, "branch", "feature")
    commit_file(repo, "b.txt", "b\n", "second")
    branches = await list_branches(repo)
    names = {b.name: b for b in branches.local}
    assert set(names) == {"main", "feature"}
    assert names["main"].is_current
    assert names["main"].upstream == "origin/main"
    assert (names["main"].ahead, names["main"].behind) == (1, 0)
    assert names["main"].last_commit_subject == "second"
    assert names["feature"].upstream is None
    assert [b.name for b in branches.remote] == ["origin/main"]


async def test_create_and_checkout(repo: Path) -> None:
    await create_branch(repo, "feature/x")
    assert current_branch(repo) == "feature/x"
    await checkout_branch(repo, "main")
    assert current_branch(repo) == "main"


async def test_create_from_start_point(repo: Path) -> None:
    first = git(repo, "rev-parse", "HEAD").strip()
    commit_file(repo, "b.txt", "b\n", "second")
    await create_branch(repo, "old", start_point=first)
    assert git(repo, "rev-parse", "HEAD").strip() == first


async def test_checkout_remote_branch_creates_tracking_branch(
    remote_pair: tuple[Path, Path],
) -> None:
    repo, _ = remote_pair
    git(repo, "push", "-q", "origin", "main:remote-only")
    git(repo, "fetch", "-q", "origin")
    await checkout_branch(repo, "origin/remote-only")
    assert current_branch(repo) == "remote-only"
    assert git(repo, "rev-parse", "--abbrev-ref", "@{upstream}").strip() == "origin/remote-only"


async def test_checkout_unknown_branch(repo: Path) -> None:
    with pytest.raises(GitError) as info:
        await checkout_branch(repo, "nope")
    assert info.value.code is ErrorCode.INVALID_ARGUMENT


async def test_checkout_with_conflicting_changes_is_dirty_tree(repo: Path) -> None:
    git(repo, "switch", "-q", "-c", "other")
    commit_file(repo, "README.md", "other\n", "other")
    git(repo, "switch", "-q", "main")
    write(repo, "README.md", "local edit\n")
    with pytest.raises(GitError) as info:
        await checkout_branch(repo, "other")
    assert info.value.code is ErrorCode.DIRTY_TREE


async def test_rename_and_delete(repo: Path) -> None:
    git(repo, "branch", "old")
    await rename_branch(repo, "old", "new")
    assert "new" in git(repo, "branch", "--format=%(refname:short)").split()
    await delete_branch(repo, "new")
    assert "new" not in git(repo, "branch", "--format=%(refname:short)").split()


async def test_delete_unmerged_requires_force(repo: Path) -> None:
    git(repo, "switch", "-q", "-c", "unmerged")
    commit_file(repo, "u.txt", "u\n", "unmerged work")
    git(repo, "switch", "-q", "main")
    with pytest.raises(GitError):
        await delete_branch(repo, "unmerged")
    await delete_branch(repo, "unmerged", force=True)
    assert "unmerged" not in git(repo, "branch", "--format=%(refname:short)").split()


async def test_set_upstream(remote_pair: tuple[Path, Path]) -> None:
    repo, _ = remote_pair
    git(repo, "branch", "feature")
    await set_upstream(repo, "feature", "origin/main")
    upstream = git(repo, "rev-parse", "--abbrev-ref", "feature@{upstream}").strip()
    assert upstream == "origin/main"


async def test_invalid_names_are_rejected(repo: Path) -> None:
    for call in (
        create_branch(repo, "-bad"),
        rename_branch(repo, "main", "bad..name"),
        delete_branch(repo, "--force"),
    ):
        with pytest.raises(GitError) as info:
            await call
        assert info.value.code is ErrorCode.INVALID_ARGUMENT
