import pytest

from git_iterm2.errors import ErrorCode, GitError, classify_stderr


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("fatal: not a git repository (or any of the parent directories): .git",
         ErrorCode.NOT_A_REPO),
        ("fatal: Unable to create '/r/.git/index.lock': File exists.", ErrorCode.LOCKED),
        ("fatal: could not read Username for 'https://github.com': terminal prompts disabled",
         ErrorCode.AUTH_REQUIRED),
        ("git@github.com: Permission denied (publickey).", ErrorCode.AUTH_REQUIRED),
        (" ! [rejected]        main -> main (non-fast-forward)\nerror: failed to push some refs",
         ErrorCode.NON_FAST_FORWARD),
        (
            "hint: Updates were rejected because the remote contains work",
            ErrorCode.NON_FAST_FORWARD,
        ),
        ("error: Your local changes to the following files would be overwritten by checkout:",
         ErrorCode.DIRTY_TREE),
        ("CONFLICT (content): Merge conflict in a.txt", ErrorCode.CONFLICT),
        ("error: you need to resolve your current index first", ErrorCode.CONFLICT),
        ("fatal: something unexpected", ErrorCode.GIT_FAILED),
    ],
)
def test_classify_stderr(text: str, code: ErrorCode) -> None:
    assert classify_stderr(text) is code


def test_git_error_carries_fields() -> None:
    error = GitError(ErrorCode.LOCKED, "locked", "stderr text")
    assert error.code is ErrorCode.LOCKED
    assert error.message == "locked"
    assert error.stderr == "stderr text"
    assert str(error) == "locked"
