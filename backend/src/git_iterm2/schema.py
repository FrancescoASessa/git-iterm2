import json
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode, models_json_schema

from git_iterm2 import __version__
from git_iterm2.models import (
    AuthMessage,
    Branches,
    CheckoutBody,
    CommitBody,
    CommitDetail,
    DeleteBranchBody,
    Diff,
    DiffSplitBody,
    ErrorBody,
    GraphPage,
    OpDoneMessage,
    OpProgressMessage,
    OpStarted,
    PathsBody,
    RenameBranchBody,
    RepoSnapshot,
    SnapshotMessage,
    StashIndexBody,
    StashList,
    StashPushBody,
    UpstreamBody,
)

RESPONSE_MODELS: list[type[BaseModel]] = [
    RepoSnapshot,
    Diff,
    Branches,
    GraphPage,
    CommitDetail,
    StashList,
    OpStarted,
    ErrorBody,
    SnapshotMessage,
    OpProgressMessage,
    OpDoneMessage,
]
REQUEST_MODELS: list[type[BaseModel]] = [
    PathsBody,
    CommitBody,
    CheckoutBody,
    RenameBranchBody,
    DeleteBranchBody,
    UpstreamBody,
    StashPushBody,
    StashIndexBody,
    DiffSplitBody,
    AuthMessage,
]


def build_openapi() -> dict[str, Any]:
    entries: list[tuple[type[BaseModel], JsonSchemaMode]] = [
        (model, "serialization") for model in RESPONSE_MODELS
    ]
    entries.extend((model, "validation") for model in REQUEST_MODELS)
    _, top_level = models_json_schema(entries, ref_template="#/components/schemas/{model}")
    return {
        "openapi": "3.1.0",
        "info": {"title": "git-iterm2", "version": __version__},
        "paths": {},
        "components": {"schemas": top_level["$defs"]},
    }


def main() -> None:
    print(json.dumps(build_openapi(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
