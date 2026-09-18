# git-iterm2 backend

Python backend for the git-iterm2 toolbelt panel: git service, active-repo controller and a
local REST/WebSocket API. See `docs/superpowers/specs/2026-09-17-git-iterm2-design.md`.

## Development

    uv sync
    uv run pytest
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run mypy src

## Standalone server

Serves one repository without iTerm2 (UI development, end-to-end tests):

    uv run python -m git_iterm2.standalone --repo /path/to/repo [--token TOKEN] [--static ../web/dist]

The first line printed is the panel URL, including the token.

## API contract

`openapi.json` is generated from the pydantic models and consumed by the web UI.
Regenerate it after changing `src/git_iterm2/models.py`:

    uv run python -m git_iterm2.schema > openapi.json

`tests/test_schema.py` fails when the file is stale.
