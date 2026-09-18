from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient

from git_iterm2.api.app import create_app
from git_iterm2.api.keys import CONTROLLER_KEY, ServerConfig
from git_iterm2.core.controller import RepoController
from git_iterm2.git.repo import RepoPaths
from tests.helpers import commit_file, git, make_conflict, write

TOKEN = "test-token"
H = {"X-Token": TOKEN}


@pytest.fixture
def split_calls() -> list[tuple[Path, str, bool]]:
    return []


@pytest.fixture
async def client(aiohttp_client, repo: Path, split_calls) -> TestClient:  # type: ignore[no-untyped-def]
    async def opener(paths: RepoPaths, path: str, staged: bool) -> None:
        split_calls.append((paths.root, path, staged))

    controller = RepoController()
    await controller.set_active_path(repo)
    config = ServerConfig(token=TOKEN, open_diff_split=opener)
    return await aiohttp_client(create_app(controller, config))


async def test_stage_then_diff_then_commit(client: TestClient, repo: Path) -> None:
    write(repo, "new.txt", "hello\n")

    response = await client.post("/api/stage", json={"paths": ["new.txt"]}, headers=H)
    assert response.status == 204

    response = await client.get("/api/diff?path=new.txt&staged=true", headers=H)
    assert response.status == 200
    diff = await response.json()
    assert diff["hunks"][0]["lines"] == [
        {"kind": "add", "text": "hello", "old_no": None, "new_no": 1}
    ]

    response = await client.post("/api/commit", json={"message": "add new"}, headers=H)
    assert response.status == 204
    assert git(repo, "log", "-1", "--format=%s").strip() == "add new"


async def test_unstage_and_discard(client: TestClient, repo: Path) -> None:
    write(repo, "README.md", "changed\n")
    git(repo, "add", "README.md")
    unstage_response = await client.post("/api/unstage", json={"paths": ["README.md"]}, headers=H)
    assert unstage_response.status == 204
    discard_response = await client.post("/api/discard", json={"paths": ["README.md"]}, headers=H)
    assert discard_response.status == 204
    assert (repo / "README.md").read_text() == "hello\n"


async def test_invalid_path_is_400(client: TestClient) -> None:
    response = await client.post("/api/stage", json={"paths": ["../x"]}, headers=H)
    assert response.status == 400
    assert (await response.json())["code"] == "INVALID_PATH"


async def test_invalid_json_is_400(client: TestClient) -> None:
    response = await client.post("/api/stage", data="not json", headers=H)
    assert response.status == 400
    assert (await response.json())["code"] == "INVALID_ARGUMENT"


async def test_missing_query_is_400(client: TestClient) -> None:
    response = await client.get("/api/diff", headers=H)
    assert response.status == 400


async def test_graph_commit_and_commit_diff(client: TestClient, repo: Path) -> None:
    sha = commit_file(repo, "README.md", "hello\nmore\n", "second")
    graph = await (await client.get("/api/graph?limit=10", headers=H)).json()
    assert graph["commits"][0]["sha"] == sha
    assert graph["next_cursor"] is None

    detail = await (await client.get(f"/api/commit/{sha}", headers=H)).json()
    assert detail["subject"] == "second"

    response = await client.get(f"/api/commit/{sha}/diff?path=README.md", headers=H)
    lines = (await response.json())["hunks"][0]["lines"]
    assert lines[-1]["text"] == "more"


async def test_bad_graph_limit(client: TestClient) -> None:
    response = await client.get("/api/graph?limit=abc", headers=H)
    assert response.status == 400


async def test_branches_checkout_rename_delete(client: TestClient, repo: Path) -> None:
    response = await client.post("/api/checkout", json={"create": "feature"}, headers=H)
    assert response.status == 204
    branches = await (await client.get("/api/branches", headers=H)).json()
    current = [b["name"] for b in branches["local"] if b["is_current"]]
    assert current == ["feature"]

    assert (await client.post("/api/checkout", json={"branch": "main"}, headers=H)).status == 204
    response = await client.post(
        "/api/branch/rename", json={"old_name": "feature", "new_name": "renamed"}, headers=H
    )
    assert response.status == 204
    response = await client.post("/api/branch/delete", json={"name": "renamed"}, headers=H)
    assert response.status == 204
    assert git(repo, "branch", "--format=%(refname:short)").split() == ["main"]


async def test_checkout_requires_branch_or_create(client: TestClient) -> None:
    response = await client.post("/api/checkout", json={}, headers=H)
    assert response.status == 400


async def test_stash_round_trip(client: TestClient, repo: Path) -> None:
    write(repo, "README.md", "wip\n")
    response = await client.post("/api/stash/push", json={"message": "wip"}, headers=H)
    assert response.status == 204
    stash = await (await client.get("/api/stash", headers=H)).json()
    assert len(stash["entries"]) == 1
    assert (await client.post("/api/stash/pop", json={"index": 0}, headers=H)).status == 204
    assert (repo / "README.md").read_text() == "wip\n"


async def test_sequence_abort(client: TestClient, repo: Path) -> None:
    make_conflict(repo)
    response = await client.post("/api/sequence/abort", headers=H)
    assert response.status == 204
    assert not (repo / ".git" / "MERGE_HEAD").exists()


async def test_conflict_error_status(client: TestClient, repo: Path) -> None:
    write(repo, "README.md", "stashed\n")
    await client.post("/api/stash/push", json={}, headers=H)
    commit_file(repo, "README.md", "committed\n", "diverge")
    response = await client.post("/api/stash/apply", json={"index": 0}, headers=H)
    assert response.status == 409
    assert (await response.json())["code"] == "CONFLICT"


async def test_remote_op_returns_202(client: TestClient) -> None:
    response = await client.post("/api/fetch", headers=H)
    assert response.status == 202
    assert len((await response.json())["op_id"]) == 32
    await client.server.app[CONTROLLER_KEY].wait_for_ops()


async def test_open_diff_split(client: TestClient, repo: Path, split_calls) -> None:  # type: ignore[no-untyped-def]
    response = await client.post(
        "/api/open-diff-split", json={"path": "README.md", "staged": True}, headers=H
    )
    assert response.status == 204
    assert split_calls == [(repo.resolve(), "README.md", True)]


async def test_open_diff_split_unsupported(aiohttp_client, repo: Path) -> None:  # type: ignore[no-untyped-def]
    controller = RepoController()
    await controller.set_active_path(repo)
    client = await aiohttp_client(create_app(controller, ServerConfig(token=TOKEN)))
    response = await client.post("/api/open-diff-split", json={"path": "README.md"}, headers=H)
    assert response.status == 501
    assert (await response.json())["code"] == "UNSUPPORTED"


async def test_not_a_repo_is_409(aiohttp_client, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    controller = RepoController()
    client = await aiohttp_client(create_app(controller, ServerConfig(token=TOKEN)))
    response = await client.get("/api/branches", headers=H)
    assert response.status == 409
    assert (await response.json())["code"] == "NOT_A_REPO"


async def test_tree_sha_is_invalid_argument(client: TestClient, repo: Path) -> None:
    tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
    response = await client.get(f"/api/commit/{tree}", headers=H)
    assert response.status == 400
    body = await response.json()
    assert body["code"] == "INVALID_ARGUMENT"
    assert body["message"] == f"Not a commit: {tree}"


async def test_unknown_api_route_is_json_404(client: TestClient) -> None:
    response = await client.get("/api/does-not-exist", headers=H)
    assert response.status == 404
    assert response.content_type == "application/json"
    assert (await response.json())["code"] == "INVALID_ARGUMENT"


async def test_wrong_method_is_json_405(client: TestClient) -> None:
    response = await client.get("/api/stage", headers=H)
    assert response.status == 405
    assert (await response.json())["code"] == "INVALID_ARGUMENT"


async def test_unexpected_exception_is_generic_json_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(root: Path) -> None:
        raise RuntimeError("secret /private/path detail")

    monkeypatch.setattr("git_iterm2.api.routes.list_branches", boom)
    response = await client.get("/api/branches", headers=H)
    assert response.status == 500
    body = await response.json()
    assert body == {"code": "GIT_FAILED", "message": "Internal error", "stderr": ""}


async def test_checkout_force(client: TestClient, repo: Path) -> None:
    git(repo, "switch", "-q", "-c", "other")
    commit_file(repo, "README.md", "other\n", "other")
    git(repo, "switch", "-q", "main")
    write(repo, "README.md", "local edit\n")

    response = await client.post("/api/checkout", json={"branch": "other"}, headers=H)
    assert response.status == 409
    assert (await response.json())["code"] == "DIRTY_TREE"

    response = await client.post(
        "/api/checkout", json={"branch": "other", "force": True}, headers=H
    )
    assert response.status == 204
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == "other"
    assert (repo / "README.md").read_text() == "other\n"


async def test_stale_graph_cursor_is_conflict(client: TestClient, repo: Path) -> None:
    for index in range(3):
        commit_file(repo, f"g{index}.txt", "x\n", f"graph {index}")
    first = await (await client.get("/api/graph?limit=2", headers=H)).json()
    assert first["next_cursor"]
    commit_file(repo, "late.txt", "x\n", "late")
    response = await client.get(
        "/api/graph", params={"limit": "2", "cursor": first["next_cursor"]}, headers=H
    )
    assert response.status == 409
    assert (await response.json())["code"] == "STALE_CURSOR"
