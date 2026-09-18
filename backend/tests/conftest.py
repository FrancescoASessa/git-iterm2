import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.helpers import commit_file, git


@pytest.fixture(autouse=True)
def _restore_git_iterm2_logger_state() -> Iterator[None]:
    """`configure_logging` (`git_iterm2.logging_setup`) mutates the
    process-wide `git_iterm2` logger: it replaces its handlers, sets its
    level from an environment variable, and disables propagation. Restore
    all three after every test so state from one test (e.g. a panel
    entry-point test that points a handler at its own `tmp_path`, or
    disables propagation) can never leak into another -- notably
    `tests/api/test_security.py::test_token_is_never_logged`, which relies
    on `caplog` seeing propagated "git_iterm2.*" records.
    """
    logger = logging.getLogger("git_iterm2")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate
    try:
        yield
    finally:
        for handler in logger.handlers:
            if handler not in original_handlers:
                handler.close()
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate


@pytest.fixture(autouse=True)
def isolated_git_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")


@pytest.fixture
def empty_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    return repo


@pytest.fixture
def repo(empty_repo: Path) -> Path:
    commit_file(empty_repo, "README.md", "hello\n", "initial")
    return empty_repo


@pytest.fixture
def remote_pair(tmp_path: Path, repo: Path) -> tuple[Path, Path]:
    """(local repo tracking origin/main, bare remote)."""
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", "main")
    return repo, bare
