# Contributing

## Layout

Three layers, each independently testable:

```
backend/     Python (aiohttp). git service, active-repo controller, REST/WebSocket API,
             the only place that imports the `iterm2` package.
web/         Preact + TypeScript SPA (Vite), served by the backend.
packaging/   Assembles backend + built web/dist into the GitPanel.its iTerm2 script archive
             (build-its.sh), plus install.sh / uninstall.sh for end users.
```

Within `backend/src/git_iterm2/`: `iterm/` (iTerm2 API only) → `core/` (application layer,
no HTTP/iTerm2 knowledge) → `git/` (pure git CLI wrapper, no iTerm2/HTTP knowledge) → `api/`
(aiohttp app translating `core/` to HTTP/WebSocket). See
`docs/superpowers/specs/2026-09-17-git-iterm2-design.md` for the full design.

## Generated files — never hand-edit

- `backend/openapi.json` is generated from the pydantic models in
  `backend/src/git_iterm2/models.py`. Regenerate after changing them:

      cd backend && uv run python -m git_iterm2.schema > openapi.json

  `backend/tests/test_schema.py` fails if this file is stale.

- `web/src/api/types.gen.ts` is generated from `backend/openapi.json`. Regenerate:

      cd web && npm run gen:types

  `npm run check:types-current` (part of CI) fails if it's stale.

## Quality gates

CI (`.github/workflows/ci.yml`) runs on every push and pull request (tags are excluded —
those go through `release.yml` instead):

**Backend** (macOS and Ubuntu), from `backend/`:

    uv sync
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run mypy src          # strict mode, configured in pyproject.toml
    uv run pytest -q

**Web**, from `web/`:

    npm ci
    npm run lint
    npm run format:check
    npm run typecheck
    npm run check:types-current
    npm run test
    npm run build

**End-to-end** (macOS, Playwright against the real backend in standalone mode), from `web/`:

    npm run build
    npx playwright install --with-deps chromium
    npm run e2e

**Packaging** — the `.its` archive must build cleanly:

    bash packaging/build-its.sh

`iterm/` (the code that actually talks to the iTerm2 API) has no automated coverage — iTerm2
doesn't run in CI. It's covered by the manual checklist in `docs/MANUAL-CHECKS.md`, which a
human runs against a real iTerm2 before a release.

## Running the panel from source

Without building the `.its` archive, against any repository:

    cd web && npm install && npm run build
    cd ../backend && uv sync
    uv run python -m git_iterm2.standalone --repo /path/to/repo --static ../web/dist

The first line printed is the panel's URL, including its token — open it in a browser.
This is also how the Playwright end-to-end suite drives the panel, and how `web/`'s own UI
development loop works (see `web/README.md`): there is no separate dev-server proxy, so
after editing `web/src/`, re-run `npm run build` and reload the page.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`,
`test:`, `build:`, `ci:`, …), matching this repository's history.
