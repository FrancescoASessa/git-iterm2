import logging
from pathlib import Path

import pytest

from git_iterm2.logging_setup import configure_logging


def test_logs_go_to_the_file_and_never_contain_the_token(tmp_path: Path) -> None:
    token = "super-secret-token"
    configure_logging(token, log_dir=tmp_path)
    logger = logging.getLogger("git_iterm2.test")

    logger.info("panel at http://127.0.0.1:1234/?t=%s", token)
    logger.warning("token=%s in a message", token)
    for handler in logging.getLogger("git_iterm2").handlers:
        handler.flush()

    contents = (tmp_path / "panel.log").read_text()
    assert token not in contents
    assert "<token>" in contents
    assert "panel at http://127.0.0.1:1234/?t=" in contents


def test_level_comes_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_ITERM2_LOG_LEVEL", "DEBUG")
    configure_logging("t", log_dir=tmp_path)
    assert logging.getLogger("git_iterm2").level == logging.DEBUG


def test_invalid_level_falls_back_to_info_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo'd `GIT_ITERM2_LOG_LEVEL` (e.g. "INF0") must not crash the
    panel before the server even starts -- `logging.Logger.setLevel` raises
    `ValueError` on an unrecognised name."""
    monkeypatch.setenv("GIT_ITERM2_LOG_LEVEL", "NOT_A_REAL_LEVEL")
    configure_logging("t", log_dir=tmp_path)  # must not raise
    logger = logging.getLogger("git_iterm2")
    assert logger.level == logging.INFO
    for handler in logger.handlers:
        handler.flush()
    contents = (tmp_path / "panel.log").read_text()
    assert "NOT_A_REAL_LEVEL" in contents


def test_percent_mapping_args_do_not_crash_formatting(tmp_path: Path) -> None:
    """`logger.info("%(a)s", {"a": 1})` is valid stdlib usage: a single
    mapping is kept as `record.args` rather than wrapped in a tuple. Naively
    wrapping it as `(mapping,)` while redacting breaks `%` formatting later
    ("format requires a mapping") -- no call site does this today, but the
    filter must not plant that landmine."""
    configure_logging("t", log_dir=tmp_path)
    logger = logging.getLogger("git_iterm2.test")

    logger.info("%(a)s", {"a": 1})  # must not raise
    for handler in logging.getLogger("git_iterm2").handlers:
        handler.flush()

    contents = (tmp_path / "panel.log").read_text()
    assert "1" in contents


def test_exception_text_is_redacted(tmp_path: Path) -> None:
    """`record.exc_info`/`exc_text` are formatted separately from
    `record.msg`/`args` and were never scanned, so a token surfacing inside
    an exception message would reach the file unredacted."""
    token = "super-secret-token"
    configure_logging(token, log_dir=tmp_path)
    logger = logging.getLogger("git_iterm2.test")

    try:
        raise RuntimeError(f"failed near token {token}")
    except RuntimeError:
        logger.exception("boom")
    for handler in logging.getLogger("git_iterm2").handlers:
        handler.flush()

    contents = (tmp_path / "panel.log").read_bytes()
    assert token.encode() not in contents
    assert b"<token>" in contents


def test_configure_logging_sets_propagate_false(tmp_path: Path) -> None:
    configure_logging("t", log_dir=tmp_path)
    assert logging.getLogger("git_iterm2").propagate is False


def test_non_string_msg_is_redacted(tmp_path: Path) -> None:
    """`logger.error(ValueError(f"obj {token}"))` passes a non-`str` object
    as `msg`. The filter used to check `isinstance(record.msg, str)` before
    doing anything, so this bypassed redaction entirely -- `getMessage()`
    stringifies whatever `msg` is regardless."""
    token = "super-secret-token"
    configure_logging(token, log_dir=tmp_path)
    logger = logging.getLogger("git_iterm2.test")

    logger.error(ValueError(f"obj {token}"))
    for handler in logging.getLogger("git_iterm2").handlers:
        handler.flush()

    contents = (tmp_path / "panel.log").read_bytes()
    assert token.encode() not in contents
    assert b"<token>" in contents


def test_stack_info_is_redacted() -> None:
    """`record.stack_info` (from `logger.info(..., stack_info=True)`) is
    rendered straight into the formatted output by
    `logging.Formatter.formatStack`, unrelated to `record.msg`/`args`/
    `exc_text`, and was never scanned."""
    from git_iterm2.logging_setup import _RedactToken

    token = "super-secret-token"
    record = logging.LogRecord("git_iterm2.test", logging.INFO, __file__, 1, "msg", None, None)
    record.stack_info = f'File "panel.py", line 1, in run_panel\n    leak({token})\n'

    _RedactToken(token).filter(record)

    assert token not in record.stack_info
    assert "<token>" in record.stack_info
