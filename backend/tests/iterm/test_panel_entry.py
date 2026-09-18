import asyncio
import json
import subprocess
import sys
from pathlib import Path

import aiohttp
import pytest

from git_iterm2 import panel
from tests.iterm.fakes import FakeSession, app_with


class FakeConnection:
    pass


async def test_panel_registers_a_tool_and_serves_the_api(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = FakeSession(variables={"path": str(repo)})
    app = app_with(session)
    registered = asyncio.Event()
    registered_urls: list[str] = []

    async def fake_register(connection: object, url: str) -> None:
        registered_urls.append(url)
        registered.set()

    monkeypatch.setattr(panel, "register_panel", fake_register)
    monkeypatch.setattr(panel, "get_app", lambda connection: _ready(app))
    monkeypatch.setenv("GIT_ITERM2_LOG_LEVEL", "WARNING")
    monkeypatch.setattr(panel, "LOG_DIR", tmp_path)

    task = asyncio.create_task(panel.run_panel(FakeConnection(), static_dir=None))
    try:
        await asyncio.wait_for(registered.wait(), timeout=5.0)
        url = registered_urls[0]
        base, _, token = url.partition("/?t=")
        assert base.startswith("http://127.0.0.1:")
        async with aiohttp.ClientSession() as http:  # noqa: SIM117
            async with http.get(f"{base}/api/branches", headers={"X-Token": token}) as response:
                assert response.status == 200
                body = await response.json()
        assert [branch["name"] for branch in body["local"]] == ["main"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_panel_reports_no_repo_outside_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    session = FakeSession(variables={"path": str(plain)})
    registered = asyncio.Event()
    registered_urls: list[str] = []

    async def fake_register(connection: object, url: str) -> None:
        registered_urls.append(url)
        registered.set()

    monkeypatch.setattr(panel, "register_panel", fake_register)
    monkeypatch.setattr(panel, "get_app", lambda connection: _ready(app_with(session)))
    monkeypatch.setattr(panel, "LOG_DIR", tmp_path)

    task = asyncio.create_task(panel.run_panel(FakeConnection(), static_dir=None))
    try:
        await asyncio.wait_for(registered.wait(), timeout=5.0)
        base, _, token = registered_urls[0].partition("/?t=")
        async with aiohttp.ClientSession() as http:  # noqa: SIM117
            async with http.get(f"{base}/api/branches", headers={"X-Token": token}) as response:
                assert response.status == 409
                assert (await response.json())["code"] == "NOT_A_REPO"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_shell_integration_hint_reaches_the_ui_without_a_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of the flag is the case where there is *no* repo.

    `run_panel`'s `on_path` sets `shell_integration=False` exactly when it
    also calls `set_active_path(None)` -- a session with no readable `path`
    variable has no directory to resolve a repository from. The controller
    therefore has no snapshot to put the flag inside, so it must ride on the
    `snapshot` message *envelope*, next to a null `repo`, or the UI can only
    ever show "Not a git repository" -- the exact confusion this feature
    exists to remove.

    Driven through the real entry point rather than by poking the
    controller: the unreachable combination (a repo path *and* the flag
    false) is what hid this for so long.
    """
    session = FakeSession(variables={})  # a session, but no readable `path`
    registered = asyncio.Event()
    registered_urls: list[str] = []

    async def fake_register(connection: object, url: str) -> None:
        registered_urls.append(url)
        registered.set()

    monkeypatch.setattr(panel, "register_panel", fake_register)
    monkeypatch.setattr(panel, "get_app", lambda connection: _ready(app_with(session)))
    monkeypatch.setattr(panel, "LOG_DIR", tmp_path)

    task = asyncio.create_task(panel.run_panel(FakeConnection(), static_dir=None))
    try:
        await asyncio.wait_for(registered.wait(), timeout=5.0)
        base, _, token = registered_urls[0].partition("/?t=")
        async with aiohttp.ClientSession() as http:  # noqa: SIM117
            async with http.ws_connect(f"{base}/ws") as ws:
                await ws.send_str(json.dumps({"type": "auth", "token": token}))
                message = json.loads((await ws.receive(timeout=5.0)).data)
        assert message["type"] == "snapshot"
        assert message["repo"] is None
        assert message["shell_integration"] is False
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_startup_apply_is_bounded_by_a_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Applying the current session at startup runs unbounded iTerm2 RPCs
    (`async_get_variable`, then `theme_from_session` -> `async_get_profile`)
    before the panel is registered. If iTerm2 is busy, modal, or the session
    is closing, those RPCs can stall forever; if `run_panel` waited for them
    unconditionally, the user would see no panel at all (with only "panel
    listening on port N" in the log) and only "panel listening on port N"
    in the log — worse than the 409 a not-yet-applied session produces,
    because a 409 self-heals on the next focus event or poll. `run_panel`
    must bound that wait and register the panel anyway.
    """
    session = FakeSession(variables={"path": "/tmp/x"}, variable_block=asyncio.Event())
    app = app_with(session)
    registered = asyncio.Event()
    registered_urls: list[str] = []

    async def fake_register(connection: object, url: str) -> None:
        registered_urls.append(url)
        registered.set()

    monkeypatch.setattr(panel, "_STARTUP_APPLY_TIMEOUT", 0.05)
    monkeypatch.setattr(panel, "register_panel", fake_register)
    monkeypatch.setattr(panel, "get_app", lambda connection: _ready(app))
    monkeypatch.setattr(panel, "LOG_DIR", tmp_path)

    task = asyncio.create_task(panel.run_panel(FakeConnection(), static_dir=None))
    try:
        await asyncio.wait_for(registered.wait(), timeout=2.0)
        assert registered_urls  # register_panel ran despite the stalled RPC
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_cleanup_runs_even_if_something_fails_after_the_server_starts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If anything after `start_server` raises -- here, `register_panel`
    itself fails (a stale/duplicate tool identifier, a dropped connection)
    -- the server must still be torn down. Otherwise a token-authenticated
    server keeps listening on a live socket with nothing left to stop it.
    """
    session = FakeSession(variables={"path": "/tmp/x"})
    app = app_with(session)
    ports: list[int] = []
    real_start_server = panel.start_server

    async def spying_start_server(*args: object, **kwargs: object) -> tuple[object, int]:
        runner, port = await real_start_server(*args, **kwargs)  # type: ignore[arg-type]
        ports.append(port)
        return runner, port

    async def failing_register(connection: object, url: str) -> None:
        raise RuntimeError("duplicate tool identifier")

    monkeypatch.setattr(panel, "start_server", spying_start_server)
    monkeypatch.setattr(panel, "register_panel", failing_register)
    monkeypatch.setattr(panel, "get_app", lambda connection: _ready(app))
    monkeypatch.setattr(panel, "LOG_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="duplicate tool identifier"):
        await panel.run_panel(FakeConnection(), static_dir=None)

    assert ports
    with pytest.raises(OSError):
        await asyncio.open_connection("127.0.0.1", ports[0])


_BLOCK_ITERM2_SNIPPET = """
import sys
import importlib.abc


class _BlockIterm2(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "iterm2" or name.startswith("iterm2."):
            raise ModuleNotFoundError(name)
        return None


sys.meta_path.insert(0, _BlockIterm2())

for module in ["git_iterm2.api.app", "git_iterm2.core.controller", "git_iterm2.standalone"]:
    __import__(module)
"""


def test_core_and_api_import_without_iterm2() -> None:
    """These modules must stay importable (and testable) without the
    optional `iterm2` package installed. A `builtins.__import__` deny hook
    installed from *inside* the test process only blocks imports that
    happen after it's installed: if `iterm2` (or one of these modules) was
    already imported earlier in the same interpreter -- as it will be on a
    machine with the `iterm` extra installed, the shipped target
    environment -- the hook is never consulted and a regression (a new
    top-level `import iterm2` in one of these modules) would pass silently.
    Running in a subprocess with a fresh interpreter and a `sys.meta_path`
    finder that blocks `iterm2` at the import-system level makes this a
    real guarantee. (Verified manually: adding a temporary top-level
    `import iterm2` to `api/app.py` makes this subprocess exit non-zero.)
    """
    result = subprocess.run(
        [sys.executable, "-c", _BLOCK_ITERM2_SNIPPET],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


async def _ready(value: object) -> object:
    return value
