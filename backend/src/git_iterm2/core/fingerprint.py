import os

from git_iterm2.git.repo import RepoPaths

Fingerprint = tuple[tuple[str, int], ...]

_GIT_DIR_ENTRIES = (
    "index",
    "HEAD",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REBASE_HEAD",
    "rebase-merge",
    "rebase-apply",
    "logs/HEAD",
)


def _mtime(path: str) -> int | None:
    try:
        return os.stat(path).st_mtime_ns
    except FileNotFoundError:
        return None


def repo_fingerprint(paths: RepoPaths) -> Fingerprint:
    candidates = [str(paths.git_dir / name) for name in _GIT_DIR_ENTRIES]
    candidates.append(str(paths.common_dir / "packed-refs"))
    candidates.extend(
        dirpath for dirpath, _dirnames, _filenames in os.walk(paths.common_dir / "refs")
    )
    entries: list[tuple[str, int]] = []
    for candidate in candidates:
        mtime = _mtime(candidate)
        if mtime is not None:
            entries.append((candidate, mtime))
    return tuple(entries)
