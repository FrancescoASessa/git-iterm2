from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiohttp import web
from pydantic import BaseModel, ValidationError

from git_iterm2.api.keys import CONFIG_KEY, CONTROLLER_KEY
from git_iterm2.core.controller import RepoController
from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.branches import (
    checkout_branch,
    create_branch,
    delete_branch,
    list_branches,
    rename_branch,
    set_upstream,
)
from git_iterm2.git.changes import commit, discard, stage, unstage
from git_iterm2.git.commits import read_commit
from git_iterm2.git.diff import get_commit_diff, get_worktree_diff
from git_iterm2.git.graph import read_graph
from git_iterm2.git.remote import REMOTE_OPS, RemoteOp
from git_iterm2.git.sequencer import abort_sequence, continue_sequence
from git_iterm2.git.stash import StashAction, list_stashes, push_stash, stash_entry_action
from git_iterm2.git.validation import validate_repo_paths
from git_iterm2.models import (
    CheckoutBody,
    CommitBody,
    DeleteBranchBody,
    DiffSplitBody,
    OpStarted,
    PathsBody,
    RenameBranchBody,
    StashIndexBody,
    StashList,
    StashPushBody,
    UpstreamBody,
)

M = TypeVar("M", bound=BaseModel)
Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]
STASH_ACTIONS: tuple[StashAction, ...] = ("apply", "pop", "drop")


def _controller(request: web.Request) -> RepoController:
    return request.app[CONTROLLER_KEY]


async def _body(request: web.Request, model: type[M]) -> M:
    try:
        data = await request.json()
    except ValueError as error:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "Request body must be JSON") from error
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "Invalid request body", str(error)) from error


def _json(model: BaseModel, status: int = 200) -> web.Response:
    return web.Response(
        text=model.model_dump_json(), status=status, content_type="application/json"
    )


def _no_content() -> web.Response:
    return web.Response(status=204)


def _query_str(request: web.Request, name: str) -> str:
    value = request.query.get(name)
    if not value:
        raise GitError(ErrorCode.INVALID_ARGUMENT, f"Missing query parameter: {name}")
    return value


def _query_bool(request: web.Request, name: str) -> bool:
    return request.query.get(name, "false").lower() in ("1", "true", "yes")


async def get_diff(request: web.Request) -> web.StreamResponse:
    path = _query_str(request, "path")
    staged = _query_bool(request, "staged")
    diff = await _controller(request).query(lambda p: get_worktree_diff(p.root, path, staged))
    return _json(diff)


async def get_branches(request: web.Request) -> web.StreamResponse:
    return _json(await _controller(request).query(lambda p: list_branches(p.root)))


async def get_graph(request: web.Request) -> web.StreamResponse:
    cursor = request.query.get("cursor") or None
    try:
        limit = int(request.query.get("limit", "200"))
    except ValueError as error:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "limit must be an integer") from error
    page = await _controller(request).query(lambda p: read_graph(p.root, cursor, limit))
    return _json(page)


async def get_commit(request: web.Request) -> web.StreamResponse:
    sha = request.match_info["sha"]
    return _json(await _controller(request).query(lambda p: read_commit(p.root, sha)))


async def get_commit_file_diff(request: web.Request) -> web.StreamResponse:
    sha = request.match_info["sha"]
    path = _query_str(request, "path")
    return _json(await _controller(request).query(lambda p: get_commit_diff(p.root, sha, path)))


async def get_stash(request: web.Request) -> web.StreamResponse:
    entries = await _controller(request).query(lambda p: list_stashes(p.root))
    return _json(StashList(entries=entries))


async def post_stage(request: web.Request) -> web.StreamResponse:
    body = await _body(request, PathsBody)
    await _controller(request).action(lambda p: stage(p.root, body.paths))
    return _no_content()


async def post_unstage(request: web.Request) -> web.StreamResponse:
    body = await _body(request, PathsBody)
    await _controller(request).action(lambda p: unstage(p.root, body.paths))
    return _no_content()


async def post_discard(request: web.Request) -> web.StreamResponse:
    body = await _body(request, PathsBody)
    await _controller(request).action(lambda p: discard(p.root, body.paths))
    return _no_content()


async def post_commit(request: web.Request) -> web.StreamResponse:
    body = await _body(request, CommitBody)
    await _controller(request).action(lambda p: commit(p.root, body.message, body.amend))
    return _no_content()


async def post_checkout(request: web.Request) -> web.StreamResponse:
    body = await _body(request, CheckoutBody)
    branch, create, start_point, force = body.branch, body.create, body.start_point, body.force
    controller = _controller(request)
    if branch:
        await controller.action(lambda p: checkout_branch(p.root, branch, force))
    elif create:
        await controller.action(lambda p: create_branch(p.root, create, start_point, force))
    else:
        raise GitError(ErrorCode.INVALID_ARGUMENT, "Provide either 'branch' or 'create'")
    return _no_content()


async def post_branch_rename(request: web.Request) -> web.StreamResponse:
    body = await _body(request, RenameBranchBody)
    await _controller(request).action(lambda p: rename_branch(p.root, body.old_name, body.new_name))
    return _no_content()


async def post_branch_delete(request: web.Request) -> web.StreamResponse:
    body = await _body(request, DeleteBranchBody)
    await _controller(request).action(lambda p: delete_branch(p.root, body.name, body.force))
    return _no_content()


async def post_branch_upstream(request: web.Request) -> web.StreamResponse:
    body = await _body(request, UpstreamBody)
    await _controller(request).action(lambda p: set_upstream(p.root, body.name, body.upstream))
    return _no_content()


async def post_stash_push(request: web.Request) -> web.StreamResponse:
    body = await _body(request, StashPushBody)
    await _controller(request).action(
        lambda p: push_stash(p.root, body.message, body.include_untracked)
    )
    return _no_content()


def _stash_handler(action: StashAction) -> Handler:
    async def handler(request: web.Request) -> web.StreamResponse:
        body = await _body(request, StashIndexBody)
        await _controller(request).action(lambda p: stash_entry_action(p.root, body.index, action))
        return _no_content()

    return handler


def _remote_handler(op: RemoteOp) -> Handler:
    async def handler(request: web.Request) -> web.StreamResponse:
        op_id = _controller(request).start_remote_op(op)
        return _json(OpStarted(op_id=op_id), status=202)

    return handler


async def post_sequence_continue(request: web.Request) -> web.StreamResponse:
    await _controller(request).action(continue_sequence)
    return _no_content()


async def post_sequence_abort(request: web.Request) -> web.StreamResponse:
    await _controller(request).action(abort_sequence)
    return _no_content()


async def post_open_diff_split(request: web.Request) -> web.StreamResponse:
    opener = request.app[CONFIG_KEY].open_diff_split
    if opener is None:
        raise GitError(ErrorCode.UNSUPPORTED, "Opening a split requires iTerm2")
    body = await _body(request, DiffSplitBody)
    (rel,) = validate_repo_paths([body.path])
    paths = _controller(request).require_paths()
    await opener(paths, rel, body.staged)
    return _no_content()


def add_api_routes(app: web.Application) -> None:
    router = app.router
    router.add_get("/api/diff", get_diff)
    router.add_get("/api/branches", get_branches)
    router.add_get("/api/graph", get_graph)
    router.add_get("/api/commit/{sha}", get_commit)
    router.add_get("/api/commit/{sha}/diff", get_commit_file_diff)
    router.add_get("/api/stash", get_stash)
    router.add_post("/api/stage", post_stage)
    router.add_post("/api/unstage", post_unstage)
    router.add_post("/api/discard", post_discard)
    router.add_post("/api/commit", post_commit)
    router.add_post("/api/checkout", post_checkout)
    router.add_post("/api/branch/rename", post_branch_rename)
    router.add_post("/api/branch/delete", post_branch_delete)
    router.add_post("/api/branch/upstream", post_branch_upstream)
    router.add_post("/api/stash/push", post_stash_push)
    for action in STASH_ACTIONS:
        router.add_post(f"/api/stash/{action}", _stash_handler(action))
    for op in REMOTE_OPS:
        router.add_post(f"/api/{op}", _remote_handler(op))
    router.add_post("/api/sequence/continue", post_sequence_continue)
    router.add_post("/api/sequence/abort", post_sequence_abort)
    router.add_post("/api/open-diff-split", post_open_diff_split)
