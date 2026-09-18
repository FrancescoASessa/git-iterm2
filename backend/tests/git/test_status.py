from pathlib import Path

from git_iterm2.git.repo import detect_state, find_repo, has_head
from git_iterm2.git.status import parse_porcelain_v2, read_snapshot
from git_iterm2.models import FileChange
from tests.helpers import commit_file, git, make_conflict, write

SAMPLE = "\0".join(
    [
        "# branch.oid 1111111111111111111111111111111111111111",
        "# branch.head main",
        "# branch.upstream origin/main",
        "# branch.ab +2 -1",
        "1 M. N... 100644 100644 100644 aaaa bbbb staged.txt",
        "1 .M N... 100644 100644 100644 aaaa aaaa unstaged.txt",
        "1 MM N... 100644 100644 100644 aaaa bbbb both.txt",
        "2 R. N... 100644 100644 100644 aaaa aaaa R100 new name.txt",
        "old name.txt",
        "u UU N... 100644 100644 100644 100644 aaaa bbbb cccc conflict.txt",
        "? untracked dir/file.txt",
    ]
) + "\0"


def test_parse_porcelain_v2() -> None:
    parsed = parse_porcelain_v2(SAMPLE)
    assert parsed.oid == "1111111111111111111111111111111111111111"
    assert parsed.head == "main"
    assert parsed.upstream == "origin/main"
    assert (parsed.ahead, parsed.behind) == (2, 1)
    assert parsed.staged == [
        FileChange(path="staged.txt", status="M"),
        FileChange(path="both.txt", status="M"),
        FileChange(path="new name.txt", orig_path="old name.txt", status="R"),
    ]
    assert parsed.unstaged == [
        FileChange(path="unstaged.txt", status="M"),
        FileChange(path="both.txt", status="M"),
    ]
    assert parsed.conflicted == [FileChange(path="conflict.txt", status="U")]
    assert parsed.untracked == ["untracked dir/file.txt"]


def test_parse_porcelain_v2_detached() -> None:
    parsed = parse_porcelain_v2("# branch.oid abcd\0# branch.head (detached)\0")
    assert parsed.head is None
    assert parsed.oid == "abcd"
    assert parsed.upstream is None


async def test_find_repo_from_subdirectory(repo: Path) -> None:
    (repo / "sub").mkdir()
    paths = await find_repo(repo / "sub")
    assert paths is not None
    assert paths.root == repo.resolve()
    assert paths.git_dir == (repo / ".git").resolve()
    assert paths.common_dir == (repo / ".git").resolve()


async def test_find_repo_outside_repo(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    assert await find_repo(tmp_path / "plain") is None
    assert await find_repo(tmp_path / "missing") is None


async def test_has_head(empty_repo: Path) -> None:
    assert await has_head(empty_repo) is False
    commit_file(empty_repo, "a.txt", "a\n", "first")
    assert await has_head(empty_repo) is True


async def test_snapshot_clean_repo(repo: Path) -> None:
    paths = await find_repo(repo)
    assert paths is not None
    snapshot = await read_snapshot(paths)
    assert snapshot.root == str(repo.resolve())
    assert snapshot.head.branch == "main"
    assert snapshot.head.detached_sha is None
    assert snapshot.upstream is None
    assert snapshot.state == "clean"
    assert snapshot.staged == snapshot.unstaged == snapshot.conflicted == []
    assert snapshot.untracked == []
    assert snapshot.stash_count == 0
    assert snapshot.theme is None


async def test_snapshot_with_changes(repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    write(repo, "added.txt", "new\n")
    git(repo, "add", "added.txt")
    write(repo, "untracked.txt", "u\n")
    paths = await find_repo(repo)
    assert paths is not None
    snapshot = await read_snapshot(paths)
    assert snapshot.staged == [FileChange(path="added.txt", status="A")]
    assert snapshot.unstaged == [FileChange(path="README.md", status="M")]
    assert snapshot.untracked == ["untracked.txt"]


async def test_snapshot_detached_head(repo: Path) -> None:
    sha = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "-q", "--detach")
    paths = await find_repo(repo)
    assert paths is not None
    snapshot = await read_snapshot(paths)
    assert snapshot.head.branch is None
    assert snapshot.head.detached_sha == sha


async def test_snapshot_empty_repo(empty_repo: Path) -> None:
    paths = await find_repo(empty_repo)
    assert paths is not None
    snapshot = await read_snapshot(paths)
    assert snapshot.head.branch == "main"
    assert snapshot.head.detached_sha is None


async def test_snapshot_upstream_ahead(remote_pair: tuple[Path, Path]) -> None:
    repo, _ = remote_pair
    commit_file(repo, "b.txt", "b\n", "second")
    paths = await find_repo(repo)
    assert paths is not None
    snapshot = await read_snapshot(paths)
    assert snapshot.upstream is not None
    assert snapshot.upstream.name == "origin/main"
    assert (snapshot.upstream.ahead, snapshot.upstream.behind) == (1, 0)


async def test_snapshot_merge_conflict(repo: Path) -> None:
    make_conflict(repo)
    paths = await find_repo(repo)
    assert paths is not None
    assert detect_state(paths.git_dir) == "merging"
    snapshot = await read_snapshot(paths)
    assert snapshot.state == "merging"
    assert snapshot.conflicted == [FileChange(path="README.md", status="U")]


async def test_snapshot_counts_stashes(repo: Path) -> None:
    write(repo, "README.md", "stash me\n")
    git(repo, "stash", "-q")
    paths = await find_repo(repo)
    assert paths is not None
    snapshot = await read_snapshot(paths)
    assert snapshot.stash_count == 1
