import subprocess
from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.diff import get_commit_diff, get_worktree_diff, parse_unified_diff
from tests.helpers import commit_file, git, write

TEXT = r"""diff --git a/f.txt b/f.txt
index 1111111..2222222 100644
--- a/f.txt
+++ b/f.txt
@@ -1,3 +1,3 @@ context
 one
-two
+TWO
 three
\ No newline at end of file
"""


def test_parse_unified_diff() -> None:
    diff = parse_unified_diff("f.txt", TEXT)
    assert diff.path == "f.txt"
    assert diff.binary is False
    assert diff.truncated is False
    assert len(diff.hunks) == 1
    hunk = diff.hunks[0]
    assert hunk.header == "@@ -1,3 +1,3 @@ context"
    assert (hunk.old_start, hunk.old_lines, hunk.new_start, hunk.new_lines) == (1, 3, 1, 3)
    assert [(line.kind, line.text, line.old_no, line.new_no) for line in hunk.lines] == [
        ("context", "one", 1, 1),
        ("del", "two", 2, None),
        ("add", "TWO", None, 2),
        ("context", "three", 3, 3),
    ]


def test_parse_hunk_without_counts() -> None:
    diff = parse_unified_diff("f.txt", "@@ -0,0 +1 @@\n+only\n")
    hunk = diff.hunks[0]
    assert (hunk.old_start, hunk.old_lines, hunk.new_start, hunk.new_lines) == (0, 0, 1, 1)
    assert [(line.kind, line.new_no) for line in hunk.lines] == [("add", 1)]


def test_parse_binary_diff() -> None:
    text = (
        "diff --git a/i.png b/i.png\nindex 1..2 100644\n"
        "Binary files a/i.png and b/i.png differ\n"
    )
    diff = parse_unified_diff("i.png", text)
    assert diff.binary is True
    assert diff.hunks == []


def test_parse_truncates() -> None:
    diff = parse_unified_diff("f.txt", TEXT, max_lines=2)
    assert diff.truncated is True
    assert len(diff.hunks[0].lines) == 2


def test_parse_combined_diff() -> None:
    text = "diff --cc f.txt\n@@@ -1,1 -1,1 +1,5 @@@\n++<<<<<<< HEAD\n +main\n- base\n"
    diff = parse_unified_diff("f.txt", text)
    assert [(line.kind, line.text) for line in diff.hunks[0].lines] == [
        ("add", "<<<<<<< HEAD"),
        ("add", "main"),
        ("del", "base"),
    ]


async def test_worktree_diff_conflicted_file_preserves_indentation(repo: Path) -> None:
    git(repo, "switch", "-q", "-c", "other")
    write(repo, "README.md", "    other\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "other change")
    git(repo, "switch", "-q", "main")
    write(repo, "README.md", "    main\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "main change")
    subprocess.run(  # noqa: ASYNC221
        ["git", "merge", "other"], cwd=repo, capture_output=True, check=False
    )
    diff = await get_worktree_diff(repo, "README.md", staged=False)
    lines = [(line.kind, line.text) for line in diff.hunks[0].lines]
    assert ("add", "    main") in lines
    assert ("add", "    other") in lines


async def test_worktree_diff_unstaged(repo: Path) -> None:
    write(repo, "README.md", "hello\nworld\n")
    diff = await get_worktree_diff(repo, "README.md", staged=False)
    kinds = [(line.kind, line.text) for line in diff.hunks[0].lines]
    assert kinds == [("context", "hello"), ("add", "world")]


async def test_worktree_diff_staged(repo: Path) -> None:
    write(repo, "README.md", "bye\n")
    git(repo, "add", "README.md")
    assert (await get_worktree_diff(repo, "README.md", staged=False)).hunks == []
    staged = await get_worktree_diff(repo, "README.md", staged=True)
    assert [(line.kind, line.text) for line in staged.hunks[0].lines] == [
        ("del", "hello"),
        ("add", "bye"),
    ]


async def test_worktree_diff_untracked(repo: Path) -> None:
    write(repo, "new file.txt", "a\nb\n")
    diff = await get_worktree_diff(repo, "new file.txt", staged=False)
    assert [(line.kind, line.new_no) for line in diff.hunks[0].lines] == [("add", 1), ("add", 2)]


async def test_worktree_diff_rejects_escaping_path(repo: Path) -> None:
    with pytest.raises(GitError) as info:
        await get_worktree_diff(repo, "../outside", staged=False)
    assert info.value.code is ErrorCode.INVALID_PATH


async def test_commit_diff(repo: Path) -> None:
    sha = commit_file(repo, "README.md", "hello\nagain\n", "second")
    diff = await get_commit_diff(repo, sha, "README.md")
    assert [(line.kind, line.text) for line in diff.hunks[0].lines] == [
        ("context", "hello"),
        ("add", "again"),
    ]


async def test_commit_diff_root_commit(repo: Path) -> None:
    sha = git(repo, "rev-parse", "HEAD").strip()
    diff = await get_commit_diff(repo, sha, "README.md")
    assert [(line.kind, line.text) for line in diff.hunks[0].lines] == [("add", "hello")]
