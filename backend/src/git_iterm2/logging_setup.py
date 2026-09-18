import logging
import os
from collections.abc import Mapping
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "git-iterm2"
LOG_FILE = "panel.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

_FALLBACK_LEVEL = logging.INFO


class _RedactToken(logging.Filter):
    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._token:
            return True
        # `record.msg` need not be a `str` -- `logger.error(some_exception)`
        # is valid; `Formatter.getMessage()` stringifies whatever `msg` is
        # regardless of type. Check the stringified form so a non-str `msg`
        # doesn't just skip redaction, but only replace `record.msg` itself
        # when there's actually something to redact (preserving the
        # original object otherwise).
        message = record.msg if isinstance(record.msg, str) else str(record.msg)
        if self._token in message:
            record.msg = message.replace(self._token, "<token>")
        if record.args:
            if isinstance(record.args, Mapping):
                # `logger.info("%(a)s", {"a": ...})` is valid stdlib usage:
                # the stdlib keeps a single mapping as `record.args` as-is
                # (not wrapped in a tuple) so `%`-style mapping formatting
                # works later. Rewrapping it as `(mapping,)` here -- as a
                # naive "always make it a tuple" would -- breaks that
                # formatting ("... format requires a mapping"). No call
                # site does this today; just leave it alone rather than
                # planting that landmine.
                pass
            else:
                record.args = tuple(
                    argument.replace(self._token, "<token>")
                    if isinstance(argument, str)
                    else argument
                    for argument in (
                        record.args if isinstance(record.args, tuple) else (record.args,)
                    )
                )
        # `record.exc_info`/`exc_text` are formatted separately from
        # `record.msg`/`args` (by `Formatter.format`, after filters run), so
        # a token surfacing inside an exception's message or traceback would
        # otherwise reach the file unredacted. Pre-computing (and caching)
        # `exc_text` here means `Formatter.format` uses our redacted text
        # instead of recomputing the raw one.
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text and self._token in record.exc_text:
            record.exc_text = record.exc_text.replace(self._token, "<token>")
        # `record.stack_info` (from `logger.info(..., stack_info=True)`) is
        # rendered straight into the formatted output by
        # `Formatter.formatStack`, independent of `msg`/`args`/`exc_text`,
        # and -- unlike `exc_text` -- is already a plain string by the time
        # filters run (captured by `Logger.findCaller` before the record is
        # even created), so no caching dance is needed here.
        if record.stack_info and self._token in record.stack_info:
            record.stack_info = record.stack_info.replace(self._token, "<token>")
        return True


def configure_logging(token: str, log_dir: Path | None = None) -> None:
    directory = log_dir or DEFAULT_LOG_DIR
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("git_iterm2")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = RotatingFileHandler(
        directory / LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(_RedactToken(token))
    logger.addHandler(handler)
    logger.propagate = False

    level_name = os.environ.get("GIT_ITERM2_LOG_LEVEL", "INFO").upper()
    try:
        logger.setLevel(level_name)
    except ValueError:
        # A typo'd environment variable (e.g. "INF0") must not crash the
        # panel before the server even starts.
        logger.setLevel(_FALLBACK_LEVEL)
        logger.warning(
            "invalid GIT_ITERM2_LOG_LEVEL %r; using %s",
            level_name,
            logging.getLevelName(_FALLBACK_LEVEL),
        )
