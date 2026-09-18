import re
from pathlib import Path

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.runner import run_git
from git_iterm2.git.validation import validate_branch_name, validate_start_point
from git_iterm2.models import Branches, BranchInfo

_FORMAT = (
    "%(refname)%00%(refname:short)%00%(HEAD)%00%(upstream:short)%00"
    "%(upstream:track,nobracket)%00%(objectname)%00%(contents:subject)%00%(committerdate:unix)"
)
_TRACK = re.compile(r"(ahead|behind) (\d+)")


def parse_for_each_ref(output: str) -> Branches:
    local: list[BranchInfo] = []
    remote: list[BranchInfo] = []
    for line in output.splitlines():
        if not line:
            continue
        full_ref, name, head, upstream, track, sha, subject, timestamp = line.split("\x00")
        is_remote = full_ref.startswith("refs/remotes/")
        if is_remote and full_ref.endswith("/HEAD"):
            continue
        ahead: int | None = None
        behind: int | None = None
        if upstream and track != "gone":
            counts = {key: int(value) for key, value in _TRACK.findall(track)}
            ahead, behind = counts.get("ahead", 0), counts.get("behind", 0)
        info = BranchInfo(
            name=name,
            full_ref=full_ref,
            is_remote=is_remote,
            is_current=head == "*",
            upstream=upstream or None,
            ahead=ahead,
            behind=behind,
            last_commit_sha=sha,
            last_commit_subject=subject,
            last_commit_ts=int(timestamp or 0),
        )
        (remote if is_remote else local).append(info)
    return Branches(local=local, remote=remote)


async def list_branches(root: Path) -> Branches:
    result = await run_git(
        root, "for-each-ref", f"--format={_FORMAT}", "refs/heads", "refs/remotes"
    )
    return parse_for_each_ref(result.stdout)


async def _ref_exists(root: Path, ref: str) -> bool:
    result = await run_git(root, "show-ref", "--verify", "--quiet", ref, check=False)
    return result.returncode == 0


async def checkout_branch(root: Path, branch: str) -> None:
    name = await validate_branch_name(root, branch)
    if await _ref_exists(root, f"refs/heads/{name}"):
        await run_git(root, "switch", name)
    elif await _ref_exists(root, f"refs/remotes/{name}"):
        await run_git(root, "switch", "--track", name)
    else:
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Unknown branch: {name}")


async def create_branch(root: Path, name: str, start_point: str | None = None) -> None:
    valid_name = await validate_branch_name(root, name)
    args = ["switch", "-c", valid_name]
    if start_point:
        args.append(await validate_start_point(root, start_point))
    await run_git(root, *args)


async def rename_branch(root: Path, old_name: str, new_name: str) -> None:
    old = await validate_branch_name(root, old_name)
    new = await validate_branch_name(root, new_name)
    await run_git(root, "branch", "-m", old, new)


async def delete_branch(root: Path, name: str, force: bool = False) -> None:
    valid_name = await validate_branch_name(root, name)
    await run_git(root, "branch", "-D" if force else "-d", valid_name)


async def set_upstream(root: Path, name: str, upstream: str) -> None:
    valid_name = await validate_branch_name(root, name)
    valid_upstream = await validate_branch_name(root, upstream)
    await run_git(root, "branch", f"--set-upstream-to={valid_upstream}", valid_name)
