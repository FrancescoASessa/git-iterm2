from pathlib import Path

from git_iterm2.git.commits import parse_name_status, read_commit
from git_iterm2.models import CommitFile
from tests.helpers import commit_file, git, write


def test_parse_name_status() -> None:
    output = "M\0a.txt\0R087\0old.txt\0new.txt\0A\0dir/b.txt\0"
    assert parse_name_status(output) == [
        CommitFile(path="a.txt", orig_path=None, status="M"),
        CommitFile(path="new.txt", orig_path="old.txt", status="R"),
        CommitFile(path="dir/b.txt", orig_path=None, status="A"),
    ]


async def test_read_commit(repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    write(repo, "new.txt", "new\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "second\n\nlonger body")
    sha = git(repo, "rev-parse", "HEAD").strip()
    parent = git(repo, "rev-parse", "HEAD~1").strip()

    detail = await read_commit(repo, sha)

    assert detail.sha == sha
    assert detail.parents == [parent]
    assert detail.author == "Test"
    assert detail.email == "test@example.com"
    assert detail.subject == "second"
    assert detail.body == "longer body"
    files = sorted((f.path, f.status) for f in detail.files)
    assert files == [("README.md", "M"), ("new.txt", "A")]


async def test_read_root_commit(repo: Path) -> None:
    sha = git(repo, "rev-parse", "HEAD").strip()
    detail = await read_commit(repo, sha)
    assert detail.parents == []
    assert [(f.path, f.status) for f in detail.files] == [("README.md", "A")]


async def test_read_merge_commit_lists_changes_against_first_parent(repo: Path) -> None:
    git(repo, "switch", "-q", "-c", "feature")
    commit_file(repo, "feature.txt", "f\n", "feature")
    git(repo, "switch", "-q", "main")
    commit_file(repo, "main.txt", "m\n", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")
    sha = git(repo, "rev-parse", "HEAD").strip()
    detail = await read_commit(repo, sha)
    assert len(detail.parents) == 2
    assert [(f.path, f.status) for f in detail.files] == [("feature.txt", "A")]
