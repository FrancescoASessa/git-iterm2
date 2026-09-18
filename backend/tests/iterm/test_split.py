import shlex
from pathlib import Path

import pytest

from git_iterm2.git.repo import RepoPaths
from git_iterm2.iterm.split import build_diff_command, make_split_opener
from tests.iterm.fakes import FakeSession, app_with


def paths(root: str = "/tmp/repo") -> RepoPaths:
    return RepoPaths(Path(root), Path(root) / ".git", Path(root) / ".git")


def test_build_diff_command_quotes_the_path() -> None:
    hostile = "a;rm -rf ~/$(whoami)`id`.txt"
    command = build_diff_command(hostile, staged=False)

    assert command.startswith("git diff --no-ext-diff -- ")
    assert "--cached" not in command
    quoted = command.removeprefix("git diff --no-ext-diff -- ")
    assert quoted.startswith("'") and quoted.endswith("'")
    assert "$(whoami)" in quoted and "`id`" in quoted  # present but inert inside single quotes
    # The hostile characters must stay welded to the path as a single shell
    # token, not break out into separate ones: a round trip through the
    # shell's own tokenizer must reproduce exactly the intended argv.
    assert shlex.split(command) == ["git", "diff", "--no-ext-diff", "--", hostile]


@pytest.mark.parametrize(
    "hostile",
    [
        "a;rm -rf ~/$(whoami)`id`.txt",
        "line1\nline2.txt",
        "it's a file.txt",
    ],
    ids=["shell-metacharacters", "embedded-newline", "embedded-single-quote"],
)
def test_build_diff_command_round_trips_hostile_names(hostile: str) -> None:
    command = build_diff_command(hostile, staged=False)

    assert shlex.split(command) == ["git", "diff", "--no-ext-diff", "--", hostile]


def test_build_diff_command_staged() -> None:
    assert build_diff_command("a.txt", staged=True) == "git diff --no-ext-diff --cached -- a.txt"


async def test_split_opener_sends_a_quoted_command() -> None:
    session = FakeSession()
    opener = make_split_opener(app_with(session))

    await opener(paths("/tmp/my repo"), "dir/file name.txt", False)

    assert session.splits == [{"vertical": True}]
    (sent,) = session.sent
    assert sent == "cd '/tmp/my repo' && git diff --no-ext-diff -- 'dir/file name.txt'\n"


async def test_split_opener_without_a_session_is_a_no_op() -> None:
    opener = make_split_opener(app_with(None))
    await opener(paths(), "a.txt", False)  # must not raise
