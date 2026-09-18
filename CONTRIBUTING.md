# Contributing

## Layout

Three layers, each independently testable:

```
backend/     Python (aiohttp). git service, active-repo controller, REST/WebSocket API,
             the only place that imports the `iterm2` package.
web/         Preact + TypeScript SPA (Vite), served by the backend.
packaging/   Assembles backend + built web/dist into the GitPanel.zip iTerm2 script archive
             (build-archive.sh), plus install.sh / uninstall.sh for end users.
```

Within `backend/src/git_iterm2/`: `iterm/` (iTerm2 API only) → `core/` (application layer,
no HTTP/iTerm2 knowledge) → `git/` (pure git CLI wrapper, no iTerm2/HTTP knowledge) → `api/`
(aiohttp app translating `core/` to HTTP/WebSocket). Each layer knows only the one below
it; that boundary is the design, and a change that crosses it needs a good reason.

## Generated files — never hand-edit

- `backend/openapi.json` is generated from the pydantic models in
  `backend/src/git_iterm2/models.py`. Regenerate after changing them:

      cd backend && uv run python -m git_iterm2.schema > openapi.json

  `backend/tests/test_schema.py` fails if this file is stale.

- `web/src/api/types.gen.ts` is generated from `backend/openapi.json`. Regenerate:

      cd web && npm run gen:types

  `npm run check:types-current` (part of CI) fails if it's stale.

## Quality gates

The gates live in one reusable workflow, `.github/workflows/tests.yml`. `ci.yml` calls it
on every push and pull request; `release.yml` calls the same workflow on a `v*` tag and
publishes nothing unless it passes, so a release is gated by exactly these checks:

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

**Packaging** (macOS) — the `.zip` archive must build cleanly, and the archive it produces
is then inspected by `backend/tests/test_packaging.py`:

    bash packaging/build-archive.sh
    cd backend && GIT_ITERM2_REQUIRE_PACKAGING_TEST=1 uv run pytest -q tests/test_packaging.py

That test needs a prebuilt `web/dist` and skips without one (so an ordinary `pytest -q` run
doesn't silently pay for a web build). `GIT_ITERM2_REQUIRE_PACKAGING_TEST=1` refuses the
skip, which is what keeps the packaging job from passing vacuously.

`iterm/` (the code that actually talks to the iTerm2 API) has no automated coverage — iTerm2
doesn't run in CI. It's covered by the manual checklist in `docs/MANUAL-CHECKS.md`, which a
human runs against a real iTerm2 before a release.

## Running the panel from source

Without building the `.zip` archive, against any repository:

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
