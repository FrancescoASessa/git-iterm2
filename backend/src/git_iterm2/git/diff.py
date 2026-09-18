import re
from pathlib import Path
from typing import Literal

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.commits import commit_parents, empty_tree
from git_iterm2.git.runner import run_git
from git_iterm2.git.validation import validate_repo_paths, validate_revision
from git_iterm2.models import Diff, DiffHunk, DiffLine

MAX_DIFF_LINES = 5000

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_COMBINED_HUNK = re.compile(r"^@@@ ")

LineKind = Literal["context", "add", "del"]


def parse_unified_diff(path: str, text: str, max_lines: int = MAX_DIFF_LINES) -> Diff:
    hunks: list[DiffHunk] = []
    binary = False
    truncated = False
    combined = False
    current: DiffHunk | None = None
    old_no = new_no = 0
    count = 0

    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    for line in lines:
        if line.startswith("@@") or current is None:
            if line.startswith("Binary files "):
                binary = True
                continue
            match = _HUNK.match(line)
            if match:
                old_no, new_no = int(match.group(1)), int(match.group(3))
                current = DiffHunk(
                    header=line,
                    old_start=old_no,
                    old_lines=int(match.group(2) or "1"),
                    new_start=new_no,
                    new_lines=int(match.group(4) or "1"),
                    lines=[],
                )
                hunks.append(current)
                combined = False
                continue
            if _COMBINED_HUNK.match(line):
                current = DiffHunk(
                    header=line, old_start=0, old_lines=0, new_start=0, new_lines=0, lines=[]
                )
                hunks.append(current)
                combined = True
                continue
            if current is None:
                continue
        if line.startswith("\\"):
            continue
        if count >= max_lines:
            truncated = True
            break
        count += 1
        kind: LineKind
        if combined:
            prefix, body = line[:2], line[2:]
            kind = "add" if "+" in prefix else "del" if "-" in prefix else "context"
            current.lines.append(DiffLine(kind=kind, text=body, old_no=None, new_no=None))
            continue
        prefix, body = line[:1], line[1:]
        if prefix == "+":
            current.lines.append(DiffLine(kind="add", text=body, old_no=None, new_no=new_no))
            new_no += 1
        elif prefix == "-":
            current.lines.append(DiffLine(kind="del", text=body, old_no=old_no, new_no=None))
            old_no += 1
        else:
            current.lines.append(DiffLine(kind="context", text=body, old_no=old_no, new_no=new_no))
            old_no += 1
            new_no += 1

    return Diff(path=path, binary=binary, truncated=truncated, hunks=hunks)


async def get_worktree_diff(root: Path, path: str, staged: bool) -> Diff:
    (rel,) = validate_repo_paths([path])
    if not staged:
        untracked = await run_git(root, "ls-files", "--others", "--exclude-standard", "--", rel)
        if untracked.stdout.strip():
            result = await run_git(
                root, "diff", "--no-index", "--no-ext-diff", "--", "/dev/null", rel, check=False
            )
            if result.returncode not in (0, 1):
                raise GitError(ErrorCode.GIT_FAILED, "git diff failed", result.stderr)
            return parse_unified_diff(rel, result.stdout)
    args = ["diff", "--no-ext-diff", "-M"]
    if staged:
        args.append("--cached")
    result = await run_git(root, *args, "--", rel)
    return parse_unified_diff(rel, result.stdout)


async def get_commit_diff(root: Path, sha: str, path: str) -> Diff:
    rev = validate_revision(sha)
    (rel,) = validate_repo_paths([path])
    parents = await commit_parents(root, rev)
    base = parents[0] if parents else await empty_tree(root)
    result = await run_git(root, "diff", "--no-ext-diff", "-M", base, rev, "--", rel)
    return parse_unified_diff(rel, result.stdout)
