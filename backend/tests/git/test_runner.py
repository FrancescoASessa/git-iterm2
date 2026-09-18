from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.runner import git_env, run_git, stream_git


async def test_run_git_returns_stdout(repo: Path) -> None:
    result = await run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    assert result.stdout.strip() == "main"
    assert result.returncode == 0


async def test_run_git_passes_stdin(tmp_path: Path) -> None:
    result = await run_git(tmp_path, "hash-object", "--stdin", stdin="hello\n")
    assert result.stdout.strip() == "ce013625030ba8dba906f756967f9e9ca394464a"


async def test_run_git_raises_classified_error(tmp_path: Path) -> None:
    with pytest.raises(GitError) as info:
        await run_git(tmp_path, "status")
    assert info.value.code is ErrorCode.NOT_A_REPO
    assert "not a git repository" in info.value.stderr


async def test_run_git_without_check_returns_failure(tmp_path: Path) -> None:
    result = await run_git(tmp_path, "status", check=False)
    assert result.returncode != 0


async def test_run_git_env_override(tmp_path: Path) -> None:
    result = await run_git(tmp_path, "var", "GIT_EDITOR", env={"GIT_EDITOR": "vi"})
    assert result.stdout.strip() == "vi"


def test_git_env_overrides() -> None:
    env = git_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["LC_ALL"] == "C"
    assert env["GIT_OPTIONAL_LOCKS"] == "0"
    assert env["GIT_EDITOR"] == "true"
    assert env["GIT_LITERAL_PATHSPECS"] == "1"


def test_git_env_applies_overrides() -> None:
    env = git_env({"GIT_LITERAL_PATHSPECS": "0"})
    assert env["GIT_LITERAL_PATHSPECS"] == "0"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


async def test_stream_git_reports_stderr_lines(tmp_path: Path, repo: Path) -> None:
    lines: list[str] = []

    async def on_line(line: str) -> None:
        lines.append(line)

    await stream_git(
        tmp_path, "clone", "--progress", str(repo), str(tmp_path / "clone"), on_line=on_line
    )
    assert any("Cloning into" in line for line in lines)


async def test_stream_git_raises_on_failure(tmp_path: Path) -> None:
    async def on_line(line: str) -> None:
        return None

    with pytest.raises(GitError):
        await stream_git(
            tmp_path, "clone", str(tmp_path / "missing"), str(tmp_path / "x"), on_line=on_line
        )
