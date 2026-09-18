from pathlib import Path

import pytest

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.graph import (
    RawCommit,
    assign_lanes,
    decode_cursor,
    encode_cursor,
    parse_log,
    read_graph,
)
from git_iterm2.models import GraphCommit
from tests.helpers import commit_file, git


def raw(sha: str, *parents: str) -> RawCommit:
    return RawCommit(sha=sha, parents=list(parents), author="a", timestamp=0, subject=sha, refs=[])


def edges(commit: GraphCommit) -> list[tuple[int, int, str]]:
    return [(e.from_lane, e.to_lane, e.half) for e in commit.edges]


def test_linear_history() -> None:
    commits, lanes = assign_lanes([raw("C", "B"), raw("B", "A"), raw("A")], [])
    assert [c.lane for c in commits] == [0, 0, 0]
    assert edges(commits[0]) == [(0, 0, "bottom")]
    assert edges(commits[1]) == [(0, 0, "top"), (0, 0, "bottom")]
    assert edges(commits[2]) == [(0, 0, "top")]
    assert lanes == []


def test_merge_history() -> None:
    commits, lanes = assign_lanes(
        [raw("M", "B", "F"), raw("B", "A"), raw("F", "A"), raw("A")], []
    )
    assert [c.lane for c in commits] == [0, 0, 1, 0]
    assert edges(commits[0]) == [(0, 0, "bottom"), (0, 1, "bottom")]
    assert edges(commits[1]) == [(0, 0, "top"), (1, 1, "top"), (0, 0, "bottom"), (1, 1, "bottom")]
    assert edges(commits[2]) == [(0, 0, "top"), (1, 1, "top"), (0, 0, "bottom"), (1, 1, "bottom")]
    assert edges(commits[3]) == [(0, 0, "top"), (1, 0, "top")]
    assert lanes == []


def test_merge_into_existing_lane_keeps_pass_through() -> None:
    commits, lanes = assign_lanes([raw("D", "Q"), raw("C", "P", "Q")], [])
    c = commits[1]
    assert c.lane == 1
    assert edges(c) == [(0, 0, "top"), (1, 0, "bottom"), (0, 0, "bottom"), (1, 1, "bottom")]
    assert lanes == ["Q", "P"]


def test_lanes_continue_across_pages() -> None:
    history = [raw("M", "B", "F"), raw("B", "A"), raw("F", "A"), raw("A")]
    whole, _ = assign_lanes(history, [])
    first, carried = assign_lanes(history[:2], [])
    second, _ = assign_lanes(history[2:], carried)
    assert first + second == whole


def test_cursor_round_trip() -> None:
    cursor = encode_cursor(200, ["abc", None, "def"])
    assert decode_cursor(cursor) == (200, ["abc", None, "def"])
    assert decode_cursor(None) == (0, [])


@pytest.mark.parametrize("bad", ["not-base64!", "e30", "eyJza2lwIjogLTF9"])
def test_invalid_cursor(bad: str) -> None:
    with pytest.raises(GitError) as info:
        decode_cursor(bad)
    assert info.value.code is ErrorCode.INVALID_ARGUMENT


def test_parse_log() -> None:
    output = (
        "aaa\x00bbb ccc\x00Ann\x00100\x00merge it\x00HEAD -> main, origin/main, tag: v1\x1e\n"
        "bbb\x00\x00Bob\x0090\x00root\x00\x1e\n"
    )
    commits = parse_log(output)
    assert commits[0] == RawCommit(
        sha="aaa",
        parents=["bbb", "ccc"],
        author="Ann",
        timestamp=100,
        subject="merge it",
        refs=["HEAD", "main", "origin/main", "tag: v1"],
    )
    assert commits[1].parents == []
    assert commits[1].refs == []


async def test_read_graph(repo: Path) -> None:
    git(repo, "switch", "-q", "-c", "feature")
    commit_file(repo, "f.txt", "f\n", "feature work")
    git(repo, "switch", "-q", "main")
    commit_file(repo, "m.txt", "m\n", "main work")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")

    page = await read_graph(repo)

    assert page.next_cursor is None
    assert len(page.commits) == 4
    top = page.commits[0]
    assert top.subject == "merge feature"
    assert len(top.parents) == 2
    assert "HEAD" in top.refs and "main" in top.refs
    assert all(commit.lane < 2 for commit in page.commits)


async def test_read_graph_pagination_matches_single_page(repo: Path) -> None:
    for index in range(4):
        commit_file(repo, f"f{index}.txt", "x\n", f"commit {index}")
    whole = await read_graph(repo, limit=100)
    first = await read_graph(repo, limit=2)
    assert first.next_cursor is not None
    rest = await read_graph(repo, cursor=first.next_cursor, limit=100)
    assert first.commits + rest.commits == whole.commits


async def test_read_graph_empty_repo(empty_repo: Path) -> None:
    page = await read_graph(empty_repo)
    assert page.commits == []
    assert page.next_cursor is None


async def test_read_graph_rejects_bad_limit(repo: Path) -> None:
    with pytest.raises(GitError) as info:
        await read_graph(repo, limit=0)
    assert info.value.code is ErrorCode.INVALID_ARGUMENT
