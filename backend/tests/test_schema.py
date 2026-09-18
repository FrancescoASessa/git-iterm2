import json
from pathlib import Path

from git_iterm2.schema import build_openapi

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "openapi.json"


def test_openapi_contains_contract_models() -> None:
    schemas = build_openapi()["components"]["schemas"]
    for name in [
        "RepoSnapshot",
        "Diff",
        "Branches",
        "GraphPage",
        "CommitDetail",
        "StashList",
        "OpStarted",
        "ErrorBody",
        "SnapshotMessage",
        "OpProgressMessage",
        "OpDoneMessage",
        "PathsBody",
        "CommitBody",
        "CheckoutBody",
        "RenameBranchBody",
        "DeleteBranchBody",
        "UpstreamBody",
        "StashPushBody",
        "StashIndexBody",
        "DiffSplitBody",
        "AuthMessage",
    ]:
        assert name in schemas, name


def test_openapi_file_is_current() -> None:
    assert json.loads(SCHEMA_FILE.read_text()) == build_openapi(), (
        "openapi.json is stale: run `uv run python -m git_iterm2.schema > openapi.json`"
    )


def test_message_discriminators_are_required() -> None:
    schemas = build_openapi()["components"]["schemas"]
    for name in ["SnapshotMessage", "OpProgressMessage", "OpDoneMessage", "AuthMessage"]:
        assert "type" in schemas[name]["required"], name
    assert "orig_path" in schemas["FileChange"]["required"]
    assert "theme" in schemas["RepoSnapshot"]["required"]
