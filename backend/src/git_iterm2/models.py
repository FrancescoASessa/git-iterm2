from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from git_iterm2.errors import ErrorCode, GitError

FileStatus = Literal["M", "A", "D", "R", "C", "T", "U"]
RepoState = Literal["clean", "merging", "rebasing", "cherry-picking"]


class ApiModel(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class FileChange(ApiModel):
    path: str
    orig_path: str | None = None
    status: FileStatus


class Head(ApiModel):
    branch: str | None
    detached_sha: str | None


class Upstream(ApiModel):
    name: str
    ahead: int
    behind: int


class Theme(ApiModel):
    background: str
    foreground: str
    selection: str
    ansi: list[str]
    font_family: str
    font_size: float


class RepoSnapshot(ApiModel):
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
    shell_integration: bool = True


class DiffLine(ApiModel):
    kind: Literal["context", "add", "del"]
    text: str
    old_no: int | None
    new_no: int | None


class DiffHunk(ApiModel):
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: list[DiffLine]


class Diff(ApiModel):
    path: str
    binary: bool
    truncated: bool
    hunks: list[DiffHunk]


class BranchInfo(ApiModel):
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


class Branches(ApiModel):
    local: list[BranchInfo]
    remote: list[BranchInfo]


class GraphEdge(ApiModel):
    from_lane: int
    to_lane: int
    half: Literal["top", "bottom"]


class GraphCommit(ApiModel):
    sha: str
    parents: list[str]
    author: str
    timestamp: int
    subject: str
    refs: list[str]
    lane: int
    edges: list[GraphEdge]


class GraphPage(ApiModel):
    commits: list[GraphCommit]
    next_cursor: str | None


class CommitFile(ApiModel):
    path: str
    orig_path: str | None
    status: FileStatus


class CommitDetail(ApiModel):
    sha: str
    parents: list[str]
    author: str
    email: str
    timestamp: int
    subject: str
    body: str
    files: list[CommitFile]


class StashEntry(ApiModel):
    index: int
    message: str
    sha: str
    timestamp: int


class StashList(ApiModel):
    entries: list[StashEntry]


class ErrorBody(ApiModel):
    code: ErrorCode
    message: str
    stderr: str = ""

    @classmethod
    def from_error(cls, error: GitError) -> "ErrorBody":
        return cls(code=error.code, message=error.message, stderr=error.stderr)


class PathsBody(ApiModel):
    paths: list[str] = Field(min_length=1)


class CommitBody(ApiModel):
    message: str = ""
    amend: bool = False


class CheckoutBody(ApiModel):
    branch: str | None = None
    create: str | None = None
    start_point: str | None = None
    force: bool = False


class RenameBranchBody(ApiModel):
    old_name: str
    new_name: str


class DeleteBranchBody(ApiModel):
    name: str
    force: bool = False


class UpstreamBody(ApiModel):
    name: str
    upstream: str


class StashPushBody(ApiModel):
    message: str = ""
    include_untracked: bool = False


class StashIndexBody(ApiModel):
    index: int = Field(ge=0)


class DiffSplitBody(ApiModel):
    path: str
    staged: bool = False


class OpStarted(ApiModel):
    op_id: str


class AuthMessage(ApiModel):
    type: Literal["auth"]
    token: str


class SnapshotMessage(ApiModel):
    type: Literal["snapshot"] = "snapshot"
    repo: RepoSnapshot | None


class OpProgressMessage(ApiModel):
    type: Literal["op_progress"] = "op_progress"
    op_id: str
    phase: str
    pct: int | None = None
    line: str


class OpDoneMessage(ApiModel):
    type: Literal["op_done"] = "op_done"
    op_id: str
    ok: bool
    error: ErrorBody | None = None


ServerMessage = SnapshotMessage | OpProgressMessage | OpDoneMessage
