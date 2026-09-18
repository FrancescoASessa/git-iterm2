from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.repo import RepoPaths, detect_state
from git_iterm2.git.runner import run_git

_COMMANDS = {"merging": "merge", "rebasing": "rebase", "cherry-picking": "cherry-pick"}


def _command(paths: RepoPaths) -> str:
    command = _COMMANDS.get(detect_state(paths.git_dir))
    if command is None:
        raise GitError(
            ErrorCode.INVALID_ARGUMENT, "No merge, rebase or cherry-pick is in progress"
        )
    return command


async def continue_sequence(paths: RepoPaths) -> None:
    await run_git(paths.root, _command(paths), "--continue")


async def abort_sequence(paths: RepoPaths) -> None:
    await run_git(paths.root, _command(paths), "--abort")
