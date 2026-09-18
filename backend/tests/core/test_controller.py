import asyncio
from pathlib import Path

import pytest

import git_iterm2.core.controller as controller_module
from git_iterm2.core.controller import RepoController
from git_iterm2.core.fingerprint import Fingerprint, repo_fingerprint
from git_iterm2.errors import ErrorCode, GitError
from git_iterm2.git.changes import stage
from git_iterm2.git.repo import RepoPaths
from git_iterm2.models import OpDoneMessage, SnapshotMessage, Theme
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
    theme = Theme(
        background="#000000",
        foreground="#ffffff",
        selection="#333333",
        ansi=["#000000"] * 16,
        font_family="Menlo",
        font_size=12.0,
    )
    await controller.set_theme(theme)
    assert controller.snapshot is not None
    assert controller.snapshot.theme == theme


async def test_shell_integration_flag_reaches_the_snapshot(repo: Path) -> None:
    controller = RepoController()
    await controller.set_active_path(repo)
    assert controller.snapshot is not None
    assert controller.snapshot.shell_integration is True

    await controller.set_shell_integration(False)
    assert controller.snapshot is not None
    assert controller.snapshot.shell_integration is False

    # And back again: the no-op guard in `set_shell_integration` compares
    # against the *current* value, not just the initial default, so it must
    # not silently pin the flag once it has gone false.
    await controller.set_shell_integration(True)
    assert controller.snapshot is not None
    assert controller.snapshot.shell_integration is True


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
