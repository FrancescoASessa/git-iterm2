from typing import Literal

from pydantic import BaseModel, Field

from git_iterm2.errors import ErrorCode, GitError

FileStatus = Literal["M", "A", "D", "R", "C", "T", "U"]
RepoState = Literal["clean", "merging", "rebasing", "cherry-picking"]


class FileChange(BaseModel):
    path: str
    orig_path: str | None = None
    status: FileStatus


class Head(BaseModel):
    branch: str | None
    detached_sha: str | None


class Upstream(BaseModel):
    name: str
    ahead: int
    behind: int


class Theme(BaseModel):
    background: str
    foreground: str
    selection: str
    ansi: list[str]
    font_family: str
    font_size: float


class RepoSnapshot(BaseModel):
    root: str
    head: Head
    upstream: Upstream | None
    state: RepoState
    staged: list[FileChange]
    unstaged: list[FileChange]
    untracked: list[str]
    conflicted: list[FileChange]
    stash_count: int
    theme: Theme | None = None


class DiffLine(BaseModel):
    kind: Literal["context", "add", "del"]
    text: str
    old_no: int | None
    new_no: int | None


class DiffHunk(BaseModel):
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: list[DiffLine]


class Diff(BaseModel):
    path: str
    binary: bool
    truncated: bool
    hunks: list[DiffHunk]


class BranchInfo(BaseModel):
    name: str
    full_ref: str
    is_remote: bool
    is_current: bool
    upstream: str | None
    ahead: int | None
    behind: int | None
    last_commit_sha: str
    last_commit_subject: str
    last_commit_ts: int


class Branches(BaseModel):
    local: list[BranchInfo]
    remote: list[BranchInfo]


class GraphEdge(BaseModel):
    from_lane: int
    to_lane: int
    half: Literal["top", "bottom"]


class GraphCommit(BaseModel):
    sha: str
    parents: list[str]
    author: str
    timestamp: int
    subject: str
    refs: list[str]
    lane: int
    edges: list[GraphEdge]


class GraphPage(BaseModel):
    commits: list[GraphCommit]
    next_cursor: str | None


class CommitFile(BaseModel):
    path: str
    orig_path: str | None
    status: FileStatus


class CommitDetail(BaseModel):
    sha: str
    parents: list[str]
    author: str
    email: str
    timestamp: int
    subject: str
    body: str
    files: list[CommitFile]


class StashEntry(BaseModel):
    index: int
    message: str
    sha: str
    timestamp: int


class StashList(BaseModel):
    entries: list[StashEntry]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    stderr: str = ""

    @classmethod
    def from_error(cls, error: GitError) -> "ErrorBody":
        return cls(code=error.code, message=error.message, stderr=error.stderr)


class PathsBody(BaseModel):
    paths: list[str] = Field(min_length=1)


class CommitBody(BaseModel):
    message: str = ""
    amend: bool = False


class CheckoutBody(BaseModel):
    branch: str | None = None
    create: str | None = None
    start_point: str | None = None


class RenameBranchBody(BaseModel):
    old_name: str
    new_name: str


class DeleteBranchBody(BaseModel):
    name: str
    force: bool = False


class UpstreamBody(BaseModel):
    name: str
    upstream: str


class StashPushBody(BaseModel):
    message: str = ""
    include_untracked: bool = False


class StashIndexBody(BaseModel):
    index: int = Field(ge=0)


class DiffSplitBody(BaseModel):
    path: str
    staged: bool = False


class OpStarted(BaseModel):
    op_id: str


class AuthMessage(BaseModel):
    type: Literal["auth"] = "auth"
    token: str


class SnapshotMessage(BaseModel):
    type: Literal["snapshot"] = "snapshot"
    repo: RepoSnapshot | None


class OpProgressMessage(BaseModel):
    type: Literal["op_progress"] = "op_progress"
    op_id: str
    phase: str
    pct: int | None = None
    line: str


class OpDoneMessage(BaseModel):
    type: Literal["op_done"] = "op_done"
    op_id: str
    ok: bool
    error: ErrorBody | None = None


ServerMessage = SnapshotMessage | OpProgressMessage | OpDoneMessage
