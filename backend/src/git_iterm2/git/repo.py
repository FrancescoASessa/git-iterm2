from dataclasses import dataclass
from pathlib import Path

from git_iterm2.git.runner import run_git
from git_iterm2.models import RepoState


@dataclass(frozen=True)
class RepoPaths:
    root: Path
    git_dir: Path
    common_dir: Path


async def find_repo(path: Path) -> RepoPaths | None:
    if not path.is_dir():
        return None
    result = await run_git(
        path,
        "rev-parse",
        "--path-format=absolute",
        "--show-toplevel",
        "--git-dir",
        "--git-common-dir",
        check=False,
    )
    if result.returncode != 0:
        return None
    lines = result.stdout.splitlines()
    if len(lines) != 3:
        return None
    root, git_dir, common_dir = (Path(line) for line in lines)
    return RepoPaths(root=root, git_dir=git_dir, common_dir=common_dir)


def detect_state(git_dir: Path) -> RepoState:
    if (git_dir / "rebase-merge").is_dir() or (git_dir / "rebase-apply").is_dir():
        return "rebasing"
    if (git_dir / "MERGE_HEAD").is_file():
        return "merging"
    if (git_dir / "CHERRY_PICK_HEAD").is_file():
        return "cherry-picking"
    return "clean"


async def has_head(root: Path) -> bool:
    result = await run_git(root, "rev-parse", "--verify", "--quiet", "HEAD", check=False)
    return result.returncode == 0
