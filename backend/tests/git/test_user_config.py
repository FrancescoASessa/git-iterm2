import re
import subprocess
from pathlib import Path

from git_iterm2.git.commits import read_commit
from git_iterm2.git.diff import get_commit_diff, get_worktree_diff
from git_iterm2.git.graph import read_graph
from tests.helpers import commit_file, git, write

SHA = re.compile(r"^[0-9a-f]{40}$")
ESCAPE = "\x1b"
SIGNATURE = "gpgsig -----BEGIN PGP SIGNATURE-----\n \n AAAA\n -----END PGP SIGNATURE-----\n"


def sign_head(repo: Path) -> str:
    """Rewrite HEAD with a (bogus) signature header so signature display kicks in."""
    raw = git(repo, "cat-file", "commit", "HEAD")
    headers, message = raw.split("\n\n", 1)
    signed = f"{headers}\n{SIGNATURE}\n{message}"
    sha = subprocess.run(
        ["git", "hash-object", "-t", "commit", "-w", "--stdin"],
        cwd=repo,
        input=signed,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    git(repo, "update-ref", "HEAD", sha)
    return sha


async def test_hostile_user_config_does_not_corrupt_parsing(repo: Path, tmp_path: Path) -> None:
    fake_gpg = tmp_path / "fake-gpg"
    fake_gpg.write_text("#!/bin/sh\necho SIGNATURE-NOISE >&2\necho SIGNATURE-NOISE\nexit 1\n")
    fake_gpg.chmod(0o755)
    git(repo, "config", "gpg.program", str(fake_gpg))
    git(repo, "config", "color.diff", "always")
    git(repo, "config", "color.ui", "always")
    git(repo, "config", "color.status", "always")
    git(repo, "config", "color.branch", "always")
    git(repo, "config", "log.showSignature", "true")
    git(repo, "config", "diff.external", "false")
    commit_file(repo, "a.txt", "one\n", "add a")
    sha = sign_head(repo)
    write(repo, "README.md", "changed\n")

    diff = await get_worktree_diff(repo, "README.md", staged=False)
    assert diff.hunks
    texts = [line.text for hunk in diff.hunks for line in hunk.lines]
    assert texts == ["hello", "changed"]
    assert all(ESCAPE not in hunk.header for hunk in diff.hunks)

    commit_diff = await get_commit_diff(repo, sha, "a.txt")
    assert [line.text for hunk in commit_diff.hunks for line in hunk.lines] == ["one"]

    page = await read_graph(repo)
    assert len(page.commits) == 2
    assert all(SHA.match(commit.sha) for commit in page.commits)

    detail = await read_commit(repo, sha)
    assert detail.sha == sha
    assert detail.subject == "add a"
    assert "SIGNATURE-NOISE" not in detail.body
    assert [file.path for file in detail.files] == ["a.txt"]
