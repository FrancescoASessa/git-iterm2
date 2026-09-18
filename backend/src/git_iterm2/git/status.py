from dataclasses import dataclass, field

from git_iterm2.git.repo import RepoPaths, detect_state
from git_iterm2.git.runner import run_git
from git_iterm2.git.stash import list_stashes
from git_iterm2.models import FileChange, FileStatus, Head, RepoSnapshot, Theme, Upstream

_STATUSES: frozenset[str] = frozenset("MADRCTU")


@dataclass
class ParsedStatus:
    oid: str | None = None
    head: str | None = None
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0
    staged: list[FileChange] = field(default_factory=list)
    unstaged: list[FileChange] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    conflicted: list[FileChange] = field(default_factory=list)


def _change(letter: str, path: str, orig_path: str | None) -> FileChange | None:
    if letter not in _STATUSES:
        return None
    status: FileStatus = letter  # type: ignore[assignment]
    return FileChange(path=path, orig_path=orig_path if letter in "RC" else None, status=status)


def _parse_header(parsed: ParsedStatus, header: str) -> None:
    key, _, value = header[2:].partition(" ")
    if key == "branch.oid":
        parsed.oid = value
    elif key == "branch.head":
        parsed.head = None if value == "(detached)" else value
    elif key == "branch.upstream":
        parsed.upstream = value
    elif key == "branch.ab":
        ahead, behind = value.split(" ")
        parsed.ahead = int(ahead.lstrip("+"))
        parsed.behind = int(behind.lstrip("-"))


def parse_porcelain_v2(output: str) -> ParsedStatus:
    parsed = ParsedStatus()
    tokens = output.split("\0")
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        kind = token[0]
        if token.startswith("# "):
            _parse_header(parsed, token)
        elif kind in "12":
            parts = token.split(" ", 8 if kind == "1" else 9)
            xy, path = parts[1], parts[-1]
            orig_path: str | None = None
            if kind == "2":
                orig_path = tokens[index]
                index += 1
            staged = _change(xy[0], path, orig_path)
            unstaged = _change(xy[1], path, orig_path)
            if staged:
                parsed.staged.append(staged)
            if unstaged:
                parsed.unstaged.append(unstaged)
        elif kind == "u":
            path = token.split(" ", 10)[-1]
            parsed.conflicted.append(FileChange(path=path, status="U"))
        elif kind == "?":
            parsed.untracked.append(token[2:])
    return parsed


async def read_snapshot(
    paths: RepoPaths, theme: Theme | None = None, shell_integration: bool = True
) -> RepoSnapshot:
    result = await run_git(
        paths.root, "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all"
    )
    parsed = parse_porcelain_v2(result.stdout)
    stashes = await list_stashes(paths.root)
    detached = parsed.head is None
    return RepoSnapshot(
        root=str(paths.root),
        head=Head(
            branch=parsed.head,
            detached_sha=parsed.oid if detached else None,
        ),
        upstream=(
            Upstream(name=parsed.upstream, ahead=parsed.ahead, behind=parsed.behind)
            if parsed.upstream
            else None
        ),
        state=detect_state(paths.git_dir),
        staged=parsed.staged,
        unstaged=parsed.unstaged,
        untracked=parsed.untracked,
        conflicted=parsed.conflicted,
        stash_count=len(stashes),
        theme=theme,
        shell_integration=shell_integration,
    )
