from pathlib import Path

from git_iterm2.core.fingerprint import repo_fingerprint
from git_iterm2.git.repo import find_repo
from tests.helpers import commit_file, git, write


async def test_fingerprint_changes_on_git_operations(repo: Path) -> None:
    paths = await find_repo(repo)
    assert paths is not None

    initial = repo_fingerprint(paths)
    assert repo_fingerprint(paths) == initial

    write(repo, "README.md", "changed\n")
    git(repo, "add", "README.md")
    staged = repo_fingerprint(paths)
    assert staged != initial

    git(repo, "branch", "feature")
    branched = repo_fingerprint(paths)
    assert branched != staged

    commit_file(repo, "b.txt", "b\n", "second")
    assert repo_fingerprint(paths) != branched
