import asyncio
from pathlib import Path

import pytest

import git_iterm2.core.controller as controller_module
from git_iterm2.core.controller import RepoController
from git_iterm2.core.fingerprint import Fingerprint, repo_fingerprint
from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.changes import stage
from git_iterm2.git.repo import RepoPaths
from git_iterm2.models import OpDoneMessage, SnapshotMessage, Theme, ThemePalette
from tests.helpers import Recorder, commit_file, write


def is_snapshot(message: object) -> bool:
    return isinstance(message, SnapshotMessage)


async def test_set_active_path_emits_snapshot(repo: Path) -> None:
    controller = RepoController()
    recorder = Recorder()
    controller.subscribe(recorder)
    (repo / "sub").mkdir()

    await controller.set_active_path(repo / "sub")

    message = await recorder.wait_for(is_snapshot)
    assert message.repo.root == str(repo.resolve())
    assert controller.paths is not None
    assert controller.snapshot == message.repo


async def test_same_repo_does_not_emit_twice(repo: Path) -> None:
    controller = RepoController()
    recorder = Recorder()
    controller.subscribe(recorder)
    (repo / "sub").mkdir()
    await controller.set_active_path(repo)
    await controller.set_active_path(repo / "sub")
    assert len(recorder.messages) == 1


async def test_non_repo_path_emits_none(tmp_path: Path, repo: Path) -> None:
    controller = RepoController()
    recorder = Recorder()
    controller.subscribe(recorder)
    await controller.set_active_path(repo)
    (tmp_path / "plain").mkdir()
    await controller.set_active_path(tmp_path / "plain")
    assert recorder.messages[-1] == SnapshotMessage(repo=None)
    assert controller.paths is None


async def test_unsubscribe(repo: Path) -> None:
    controller = RepoController()
    recorder = Recorder()
    unsubscribe = controller.subscribe(recorder)
    assert controller.listener_count == 1
    unsubscribe()
    assert controller.listener_count == 0
    await controller.set_active_path(repo)
    assert recorder.messages == []


async def test_action_refreshes_snapshot(repo: Path) -> None:
    controller = RepoController()
    await controller.set_active_path(repo)
    recorder = Recorder()
    controller.subscribe(recorder)
    write(repo, "new.txt", "n\n")

    await controller.action(lambda paths: stage(paths.root, ["new.txt"]))

    message = await recorder.wait_for(
        lambda m: is_snapshot(m) and m.repo is not None and len(m.repo.staged) == 1
    )
    assert message.repo.staged[0].path == "new.txt"


async def test_action_without_repo_raises() -> None:
    controller = RepoController()

    async def noop(paths: object) -> None:
        return None

    with pytest.raises(GitError) as info:
        await controller.action(noop)
    assert info.value.code is ErrorCode.NOT_A_REPO


async def test_set_theme_is_included_in_snapshot(repo: Path) -> None:
    controller = RepoController()
    await controller.set_active_path(repo)
    palette = ThemePalette(accent="#0a69da", added="#1a7f37", removed="#cf222e")
    theme = Theme(light=palette, dark=palette, mono_family="Menlo", mono_size=12.0)
    await controller.set_theme(theme)
    assert controller.snapshot is not None
    assert controller.snapshot.theme == theme


async def test_shell_integration_flag_rides_on_the_snapshot_envelope() -> None:
    """The flag must travel on the `SnapshotMessage` envelope, not inside
    `RepoSnapshot`.

    The only state production ever puts the controller in when the flag is
    false is *no active path at all*: `panel.py`'s `on_path` calls
    `set_active_path(None)` and `set_shell_integration(False)` together,
    because a session with no readable `path` variable has no directory to
    resolve a repository from. `refresh()` then has no snapshot to put the
    flag inside, so a flag that only existed inside `RepoSnapshot` could
    never be delivered at all.
    """
    controller = RepoController()
    recorder = Recorder()
    controller.subscribe(recorder)

    await controller.set_shell_integration(False)

    message = await recorder.wait_for(is_snapshot)
    assert message.repo is None  # exactly the state production reaches
    assert message.shell_integration is False
    assert controller.shell_integration is False

    # And back again: the no-op guard in `set_shell_integration` compares
    # against the *current* value, not just the initial default, so it must
    # not silently pin the flag once it has gone false.
    recorder.messages.clear()
    await controller.set_shell_integration(True)

    message = await recorder.wait_for(is_snapshot)
    assert message.shell_integration is True
    assert controller.shell_integration is True


async def test_remote_op_success(remote_pair: tuple[Path, Path]) -> None:
    repo, _ = remote_pair
    commit_file(repo, "b.txt", "b\n", "second")
    controller = RepoController()
    await controller.set_active_path(repo)
    recorder = Recorder()
    controller.subscribe(recorder)

    op_id = controller.start_remote_op("push")
    await controller.wait_for_ops()

    done = await recorder.wait_for(lambda m: isinstance(m, OpDoneMessage))
    assert done.op_id == op_id
    assert done.ok is True
    assert done.error is None


async def test_remote_op_failure(repo: Path) -> None:
    controller = RepoController()
    await controller.set_active_path(repo)
    recorder = Recorder()
    controller.subscribe(recorder)

    controller.start_remote_op("push")
    await controller.wait_for_ops()

    done = await recorder.wait_for(lambda m: isinstance(m, OpDoneMessage))
    assert done.ok is False
    assert done.error is not None
    assert done.error.code == ErrorCode.INVALID_ARGUMENT


async def test_poll_detects_working_tree_changes(repo: Path) -> None:
    controller = RepoController(poll_interval=0.05, status_interval=0.1)
    await controller.set_active_path(repo)
    recorder = Recorder()
    controller.subscribe(recorder)
    poller = asyncio.create_task(controller.poll_forever())
    try:
        write(repo, "untracked.txt", "u\n")
        message = await recorder.wait_for(
            lambda m: (
                is_snapshot(m) and m.repo is not None and m.repo.untracked == ["untracked.txt"]
            )
        )
        assert message.repo.untracked == ["untracked.txt"]
    finally:
        poller.cancel()


async def test_remote_op_unexpected_error_still_reports_done(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RepoController()
    await controller.set_active_path(repo)
    recorder = Recorder()
    controller.subscribe(recorder)

    async def failing_run_remote_op(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("gone")

    monkeypatch.setattr(controller_module, "run_remote_op", failing_run_remote_op)

    controller.start_remote_op("fetch")
    await controller.wait_for_ops()

    done = await recorder.wait_for(lambda m: isinstance(m, OpDoneMessage))
    assert done.ok is False
    assert done.error is not None
    assert done.error.code == ErrorCode.GIT_FAILED
    assert "gone" in done.error.message


async def test_poll_survives_iteration_error(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    controller = RepoController(poll_interval=0.05, status_interval=0.1)
    await controller.set_active_path(repo)
    recorder = Recorder()
    controller.subscribe(recorder)

    calls = 0

    def flaky_fingerprint(paths: RepoPaths) -> Fingerprint:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("denied")
        return repo_fingerprint(paths)

    monkeypatch.setattr(controller_module, "repo_fingerprint", flaky_fingerprint)

    poller = asyncio.create_task(controller.poll_forever())
    try:
        write(repo, "untracked.txt", "u\n")
        message = await recorder.wait_for(
            lambda m: (
                is_snapshot(m) and m.repo is not None and m.repo.untracked == ["untracked.txt"]
            )
        )
        assert message.repo.untracked == ["untracked.txt"]
    finally:
        poller.cancel()
