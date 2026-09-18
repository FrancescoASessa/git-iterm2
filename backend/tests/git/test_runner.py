import asyncio
import os
from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.runner import BASE_ARGS, GitResult, _failure, git_env, run_git, stream_git


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


async def _wait_until_gone(pid: int, timeout: float = 2.0) -> bool:  # noqa: ASYNC109
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        await asyncio.sleep(0.02)
    return False


async def _read_pid(pid_file: Path) -> int:
    for _ in range(500):
        if pid_file.exists() and pid_file.read_text().strip():
            return int(pid_file.read_text())
        await asyncio.sleep(0.01)
    raise AssertionError("silent command did not start")


@pytest.fixture
def silent_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Define `git slow`: records its pid, then sleeps without any output."""
    pid_file = tmp_path / "pid"
    alias = f"alias.slow=!echo $$ > '{pid_file}'; exec sleep 30"
    monkeypatch.setattr("git_iterm2.git.runner.BASE_ARGS", (*BASE_ARGS, "-c", alias))
    return pid_file


@pytest.fixture
def prompt_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Define `git quick`: records its pid, then finishes on its own shortly
    after (as a `git commit` running a fast pre-commit hook would), writing
    a sentinel file right before it exits. If it were killed instead of
    awaited, the sentinel would never appear."""
    pid_file = tmp_path / "pid"
    done_file = tmp_path / "done"
    alias = f"alias.quick=!echo $$ > '{pid_file}'; sleep 0.3; echo done > '{done_file}'; exit 0"
    monkeypatch.setattr("git_iterm2.git.runner.BASE_ARGS", (*BASE_ARGS, "-c", alias))
    return pid_file, done_file


async def test_stream_git_idle_timeout_kills_process_group(
    tmp_path: Path, silent_command: Path
) -> None:
    async def on_line(line: str) -> None:
        return None

    loop = asyncio.get_running_loop()
    started = loop.time()
    with pytest.raises(GitError) as info:
        await stream_git(tmp_path, "slow", on_line=on_line, idle_timeout=0.3)
    assert loop.time() - started < 2
    assert info.value.code is ErrorCode.GIT_FAILED
    assert info.value.message == "git slow timed out with no output"
    assert await _wait_until_gone(await _read_pid(silent_command))


async def test_stream_git_cancel_kills_process_group(tmp_path: Path, silent_command: Path) -> None:
    async def on_line(line: str) -> None:
        return None

    task = asyncio.create_task(stream_git(tmp_path, "slow", on_line=on_line))
    pid = await _read_pid(silent_command)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await _wait_until_gone(pid)


async def test_run_git_cancel_lets_a_prompt_child_finish(
    tmp_path: Path, prompt_command: tuple[Path, Path]
) -> None:
    """`run_git` backs mutating commands (`commit`, `add`, `rebase
    --continue`, ...). If cancellation killed the child immediately, a
    `git commit` running a slow-but-finishing pre-commit hook would be
    SIGKILLed mid-write and leave `.git/index.lock` behind, breaking every
    later git command until a human deletes it by hand. Cancelling `run_git`
    must let an already-running child finish on its own (bounded by
    `_CANCEL_REAP_TIMEOUT`), not kill it out from under a lock it holds."""
    pid_file, done_file = prompt_command
    task = asyncio.create_task(run_git(tmp_path, "quick"))
    pid = await _read_pid(pid_file)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await _wait_until_gone(pid)
    assert done_file.read_text().strip() == "done"  # exited on its own, not killed


async def test_run_git_cancel_kills_a_child_that_never_exits(
    tmp_path: Path, silent_command: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A child that's truly wedged (not just finishing up) must still be
    reaped eventually — just not immediately — so an unreaped subprocess
    transport can't linger past the owning event loop's lifetime (an
    unreaped transport is only closed when the garbage collector eventually
    gets to it, which can happen after the loop has already closed,
    surfacing as `RuntimeError: Event loop is closed` from
    `BaseSubprocessTransport.__del__` in unrelated, later tests)."""
    monkeypatch.setattr("git_iterm2.git.runner._CANCEL_REAP_TIMEOUT", 0.1)
    task = asyncio.create_task(run_git(tmp_path, "slow"))
    pid = await _read_pid(silent_command)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await _wait_until_gone(pid)


@pytest.mark.parametrize(
    ("stderr", "stdout", "expected"),
    [
        ("To /r.git\n ! [rejected] main\nerror: failed to push\nhint: pull", "", "failed to push"),
        ("warning: x\nfatal: bad thing\nerror: later", "", "bad thing"),
        ("\n  first line\nsecond", "out", "first line"),
        ("", "\nNothing to commit\n", "Nothing to commit"),
        ("", "", "git push failed"),
    ],
)
def test_failure_message_prefers_fatal_and_error_lines(
    stderr: str, stdout: str, expected: str
) -> None:
    error = _failure(("push",), GitResult(stdout, stderr, 1))
    assert error.message == expected
