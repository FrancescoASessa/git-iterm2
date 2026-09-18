# git-iterm2 web panel

Preact + TypeScript SPA served by the backend inside the iTerm2 toolbelt.

## Development

    npm install
    npm run gen:types          # regenerate API types from ../backend/openapi.json
    npm run build              # tsc --noEmit + vite build → dist/
    cd ../backend && uv run python -m git_iterm2.standalone --repo /path/to/repo --static ../web/dist

Open the URL it prints (it carries the token and the port, which is random per run).
There is no Vite dev-server proxy: the backend serves the panel itself from
`--static`, so after changing anything under `src/`, re-run `npm run build` in
`web/` and reload the page to pick up the new `dist/`.

## Tests

    npm run test               # Vitest unit + component tests
    npm run lint
    npm run typecheck
    npm run format:check
    npm run check:types-current
    npm run build && npm run e2e   # Playwright against the real backend

The Playwright suite (`e2e/`) builds nothing itself — run `npm run build` first so
`dist/` exists, and `npx playwright install chromium` once to fetch its browser
binary. `e2e/global-setup.ts` then creates a temp git repository, starts the
backend's standalone server against it (`uv run python -m git_iterm2.standalone`),
and writes the resulting URL/token/repo path to `web/.e2e-env.json` for the specs
to read; it tears both down again after the run.

## Contract

`src/api/types.gen.ts` is generated from `../backend/openapi.json` and must never be
hand-edited. `npm run check:types-current` fails when it is stale.
