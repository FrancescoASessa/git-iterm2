import base64
import binascii
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.repo import has_head
from git_iterm2.git.runner import run_git
from git_iterm2.models import GraphCommit, GraphEdge, GraphPage

LOG_FORMAT = "%H%x00%P%x00%an%x00%ct%x00%s%x00%D%x1e"
MAX_LIMIT = 1000


@dataclass(frozen=True)
class RawCommit:
    sha: str
    parents: list[str]
    author: str
    timestamp: int
    subject: str
    refs: list[str]


def _parse_refs(decorations: str) -> list[str]:
    refs: list[str] = []
    if not decorations:
        return refs
    for part in decorations.split(", "):
        if part.startswith("HEAD -> "):
            refs.extend(["HEAD", part.removeprefix("HEAD -> ")])
        else:
            refs.append(part)
    return refs


def parse_log(output: str) -> list[RawCommit]:
    commits: list[RawCommit] = []
    for record in output.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, parents, author, timestamp, subject, decorations = record.split("\x00")
        commits.append(
            RawCommit(
                sha=sha,
                parents=parents.split(),
                author=author,
                timestamp=int(timestamp),
                subject=subject,
                refs=_parse_refs(decorations),
            )
        )
    return commits


def _free_lane(lanes: list[str | None]) -> int:
    for index, value in enumerate(lanes):
        if value is None:
            return index
    lanes.append(None)
    return len(lanes) - 1


def assign_lanes(
    commits: Sequence[RawCommit], lanes: Sequence[str | None]
) -> tuple[list[GraphCommit], list[str | None]]:
    active: list[str | None] = list(lanes)
    result: list[GraphCommit] = []

    for commit in commits:
        before = list(active)
        expecting = [index for index, sha in enumerate(before) if sha == commit.sha]
        lane = expecting[0] if expecting else _free_lane(active)

        row_edges: list[GraphEdge] = []
        for index, sha in enumerate(before):
            if sha is None:
                continue
            target = lane if sha == commit.sha else index
            row_edges.append(GraphEdge(from_lane=index, to_lane=target, half="top"))

        for index in expecting:
            active[index] = None

        targets: set[int] = set()
        if commit.parents:
            active[lane] = commit.parents[0]
            targets.add(lane)
            for parent in commit.parents[1:]:
                if parent in active:
                    target = active.index(parent)
                else:
                    target = _free_lane(active)
                    active[target] = parent
                targets.add(target)

        for index, sha in enumerate(active):
            if sha is None:
                continue
            if index in targets:
                row_edges.append(GraphEdge(from_lane=lane, to_lane=index, half="bottom"))
                passes_through = (
                    index != lane
                    and index < len(before)
                    and before[index] is not None
                    and before[index] != commit.sha
                    and before[index] == sha
                )
                if passes_through:
                    row_edges.append(GraphEdge(from_lane=index, to_lane=index, half="bottom"))
            else:
                row_edges.append(GraphEdge(from_lane=index, to_lane=index, half="bottom"))

        while active and active[-1] is None:
            active.pop()

        result.append(
            GraphCommit(
                sha=commit.sha,
                parents=commit.parents,
                author=commit.author,
                timestamp=commit.timestamp,
                subject=commit.subject,
                refs=commit.refs,
                lane=lane,
                edges=row_edges,
            )
        )
    return result, active


async def tips_fingerprint(root: Path) -> str:
    """Identify the set of history tips the graph is drawn from.

    Covers the same refs `read_graph` walks (branches, remotes, tags) plus HEAD, so that
    unrelated refs such as the stash do not invalidate pagination cursors.
    """
    refs = await run_git(
        root,
        "for-each-ref",
        "--format=%(objectname) %(refname)",
        "refs/heads",
        "refs/remotes",
        "refs/tags",
    )
    head = await run_git(root, "rev-parse", "--verify", "--quiet", "HEAD", check=False)
    head_sha = head.stdout.strip() if head.returncode == 0 else ""
    digest = hashlib.sha256(f"{refs.stdout}\0{head_sha}".encode())
    return digest.hexdigest()[:16]


def encode_cursor(skip: int, lanes: Sequence[str | None], tips: str) -> str:
    payload = json.dumps({"skip": skip, "lanes": list(lanes), "tips": tips}).encode()
    return base64.urlsafe_b64encode(payload).decode()


def decode_cursor(cursor: str | None) -> tuple[int, list[str | None], str | None]:
    if not cursor:
        return 0, [], None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data: Any = json.loads(base64.urlsafe_b64decode(padded.encode()))
        skip = data["skip"]
        lanes = data["lanes"]
        tips = data["tips"]
        valid = (
            isinstance(tips, str)
            and isinstance(skip, int)
            and skip >= 0
            and isinstance(lanes, list)
            and all(item is None or isinstance(item, str) for item in lanes)
        )
    except (ValueError, KeyError, TypeError, binascii.Error) as error:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "Invalid graph cursor") from error
    if not valid:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "Invalid graph cursor")
    return skip, lanes, tips


async def read_graph(root: Path, cursor: str | None = None, limit: int = 200) -> GraphPage:
    if not 1 <= limit <= MAX_LIMIT:
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"limit must be between 1 and {MAX_LIMIT}")
    skip, lanes, cursor_tips = decode_cursor(cursor)
    tips = await tips_fingerprint(root)
    if cursor_tips is not None and cursor_tips != tips:
        raise GitError(ErrorCode.STALE_CURSOR, "Graph changed; reload from the top")

    revisions = ["--branches", "--remotes", "--tags"]
    if await has_head(root):
        revisions.append("HEAD")
    else:
        any_ref = await run_git(root, "for-each-ref", "--count=1")
        if not any_ref.stdout.strip():
            return GraphPage(commits=[], next_cursor=None)

    result = await run_git(
        root,
        "log",
        "--no-show-signature",
        "--no-color",
        "--topo-order",
        f"--skip={skip}",
        f"--max-count={limit}",
        f"--format={LOG_FORMAT}",
        *revisions,
        "--",
    )
    raw_commits = parse_log(result.stdout)
    commits, lanes_after = assign_lanes(raw_commits, lanes)
    next_cursor = (
        encode_cursor(skip + len(raw_commits), lanes_after, tips)
        if len(raw_commits) == limit
        else None
    )
    return GraphPage(commits=commits, next_cursor=next_cursor)
