import asyncio
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def commit_file(repo: Path, rel: str, content: str, message: str) -> str:
    write(repo, rel, content)
    git(repo, "add", "--", rel)
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def make_conflict(repo: Path) -> None:
    """Leave `repo` in the middle of a merge with README.md conflicted."""
    git(repo, "switch", "-q", "-c", "other")
    commit_file(repo, "README.md", "other\n", "other change")
    git(repo, "switch", "-q", "main")
    commit_file(repo, "README.md", "main\n", "main change")
    subprocess.run(["git", "merge", "other"], cwd=repo, capture_output=True, check=False)


class Recorder:
    """Async listener that records messages and waits for a matching one."""

    def __init__(self) -> None:
        self.messages: list[Any] = []
        self._event = asyncio.Event()

    async def __call__(self, message: Any) -> None:
        self.messages.append(message)
        self._event.set()

    async def wait_for(
        self, predicate: Callable[[Any], bool], timeout: float = 5.0  # noqa: ASYNC109
    ) -> Any:
        async def loop() -> Any:
            while True:
                self._event.clear()
                for message in self.messages:
                    if predicate(message):
                        return message
                await self._event.wait()

        async with asyncio.timeout(timeout):
            return await loop()
