import re
from enum import StrEnum


class ErrorCode(StrEnum):
    NOT_A_REPO = "NOT_A_REPO"
    CONFLICT = "CONFLICT"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    NON_FAST_FORWARD = "NON_FAST_FORWARD"
    LOCKED = "LOCKED"
    DIRTY_TREE = "DIRTY_TREE"
    INVALID_PATH = "INVALID_PATH"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNSUPPORTED = "UNSUPPORTED"
    GIT_FAILED = "GIT_FAILED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"


class GitError(Exception):
    def __init__(self, code: ErrorCode, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stderr = stderr


_RULES: list[tuple[re.Pattern[str], ErrorCode]] = [
    (re.compile(r"not a git repository", re.IGNORECASE), ErrorCode.NOT_A_REPO),
    (re.compile(r"index\.lock|Unable to create '.*\.lock'", re.IGNORECASE), ErrorCode.LOCKED),
    (
        re.compile(
            r"Authentication failed|could not read Username|terminal prompts disabled"
            r"|Permission denied \(publickey",
            re.IGNORECASE,
        ),
        ErrorCode.AUTH_REQUIRED,
    ),
    (
        re.compile(r"non-fast-forward|Updates were rejected|\(fetch first\)", re.IGNORECASE),
        ErrorCode.NON_FAST_FORWARD,
    ),
    (
        re.compile(r"would be overwritten by|commit your changes or stash them", re.IGNORECASE),
        ErrorCode.DIRTY_TREE,
    ),
    (
        re.compile(
            r"^CONFLICT|Merge conflict|needs merge|resolve your current index first"
            r"|unmerged files",
            re.IGNORECASE | re.MULTILINE,
        ),
        ErrorCode.CONFLICT,
    ),
]


def classify_stderr(text: str) -> ErrorCode:
    for pattern, code in _RULES:
        if pattern.search(text):
            return code
    return ErrorCode.GIT_FAILED
