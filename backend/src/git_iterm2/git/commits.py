from pathlib import Path

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.runner import run_git
from git_iterm2.git.validation import validate_revision
from git_iterm2.models import CommitDetail, CommitFile, FileStatus

_STATUSES = "MADRCTU"


async def empty_tree(root: Path) -> str:
    result = await run_git(root, "hash-object", "-t", "tree", "/dev/null")
    return result.stdout.strip()


async def commit_parents(root: Path, sha: str) -> list[str]:
    result = await run_git(root, "rev-list", "--parents", "-n", "1", validate_revision(sha))
    return result.stdout.split()[1:]


def parse_name_status(output: str) -> list[CommitFile]:
    tokens = output.split("\0")
    files: list[CommitFile] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        letter = token[0] if token[0] in _STATUSES else "M"
        status: FileStatus = letter  # type: ignore[assignment]
        if letter in "RC":
            orig_path, path = tokens[index], tokens[index + 1]
            index += 2
            files.append(CommitFile(path=path, orig_path=orig_path, status=status))
        else:
            path = tokens[index]
            index += 1
            files.append(CommitFile(path=path, orig_path=None, status=status))
    return files


async def read_commit(root: Path, sha: str) -> CommitDetail:
    rev = validate_revision(sha)
    resolved = await run_git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{rev}^{{commit}}",
        check=False,
    )
    if resolved.returncode != 0:
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Not a commit: {sha}")
    result = await run_git(
        root,
        "show",
        "--no-show-signature",
        "--no-patch",
        "--format=%H%x00%P%x00%an%x00%ae%x00%ct%x00%s%x00%b",
        resolved.stdout.strip(),
    )
    full_sha, parents_raw, author, email, timestamp, subject, body = result.stdout.split("\x00", 6)
    parents = parents_raw.split()
    base = parents[0] if parents else await empty_tree(root)
    changed = await run_git(
        root, "diff", "--no-color", "--no-ext-diff", "--name-status", "-z", "-M", base, full_sha
    )
    return CommitDetail(
        sha=full_sha,
        parents=parents,
        author=author,
        email=email,
        timestamp=int(timestamp),
        subject=subject,
        body=body.strip(),
        files=parse_name_status(changed.stdout),
    )
