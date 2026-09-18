import pytest
from pydantic import ValidationError

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.models import (
    ErrorBody,
    FileChange,
    Head,
    PathsBody,
    RepoSnapshot,
    SnapshotMessage,
    StashIndexBody,
)


def test_snapshot_round_trips_through_json() -> None:
    snapshot = RepoSnapshot(
        root="/r",
        head=Head(branch="main", detached_sha=None),
        upstream=None,
        state="clean",
        staged=[FileChange(path="a.txt", status="M")],
        unstaged=[],
        untracked=["b.txt"],
        conflicted=[],
        stash_count=0,
    )
    message = SnapshotMessage(repo=snapshot)
    restored = SnapshotMessage.model_validate_json(message.model_dump_json())
    assert restored == message
    assert restored.type == "snapshot"
    assert restored.repo is not None and restored.repo.theme is None


def test_error_body_from_error() -> None:
    body = ErrorBody.from_error(GitError(ErrorCode.CONFLICT, "boom", "details"))
    assert body.model_dump() == {"code": "CONFLICT", "message": "boom", "stderr": "details"}


def test_request_validation() -> None:
    with pytest.raises(ValidationError):
        PathsBody(paths=[])
    with pytest.raises(ValidationError):
        StashIndexBody(index=-1)
