# git-iterm2

A VSCode-style Source Control panel for the iTerm2 toolbelt. It follows the git repository
of the active iTerm2 session and lets you inspect and operate on it without leaving the
terminal: branch state, staged/unstaged changes, diffs, branches, commit graph, stash and
remote operations.

> **Screenshot:** coming soon — the panel showing the Changes tab, inline diff open, next to
> the "Profiles" and "Session Status" toolbelt tools.

## Requirements

- macOS, with [iTerm2](https://iterm2.com) 3.5 or newer (developed and verified on 3.7.1).
- iTerm2's Python API enabled (Preferences › General › Magic › Enable Python API).
- iTerm2 [Shell Integration](https://iterm2.com/documentation-shell-integration.html)
  recommended: without it, the panel cannot tell which directory a session is in and shows
  a hint asking you to install it.

## Install

1. Download `GitPanel.its` from the [latest release](../../releases/latest).
2. Double-click it, or run `packaging/install.sh <path-or-https-url-to-GitPanel.its>`.
   Either way, iTerm2 opens its own script-import dialog.
3. **The archive is unsigned** (there is no Apple Developer ID certificate for it). iTerm2
   will show an "unsigned script" warning — this is expected; you must approve it yourself,
   and nothing in this project bypasses that prompt. A matching `.sha256` file lets you
   confirm the download wasn't corrupted in transit; it does not prove who published the
   archive, since it comes from the same host as the archive itself.
4. If iTerm2 asks to restart the script, or you don't see it registered right away, quit
   and reopen iTerm2 once so AutoLaunch picks it up.
5. Open **View › Toolbelt › Git**.

To remove it later, run `packaging/uninstall.sh`.

## What it does

- **Changes** — staged, unstaged, untracked and conflicted files; stage/unstage/discard;
  commit with amend; click a file for an inline diff, double-click (or `⌥`-click) to open
  it in a new split pane running `git diff`.
- **Branches** — local and remote branches, filter, checkout (offers stash-and-checkout on
  a dirty tree), create, rename, delete, set upstream.
- **Graph** — paginated, lane-rendered commit history; click a commit for its changed files
  and per-file diff.
- **Stash** — list, push (with message, optionally including untracked files), apply, pop,
  drop.

Fetch/pull/push run with progress, and a banner with Continue/Abort appears while a merge,
rebase or cherry-pick is in progress.

## Following the active session

The panel always shows the repository of iTerm2's *currently active* session: it re-resolves
the repo root when you switch tabs/panes or `cd` inside one, via iTerm2 Shell Integration's
`path` variable. There is no way to pin a different repo independently of the active session.

## Logs

`~/Library/Logs/git-iterm2/panel.log`, rotated automatically. Verbosity is controlled by the
`GIT_ITERM2_LOG_LEVEL` environment variable (default `INFO`). The per-process auth token is
never written to this file.

## Development

The panel is a Python backend (`backend/`, served locally via aiohttp) plus a Preact/
TypeScript SPA (`web/`), packaged together into the `.its` archive (`packaging/`). See
[`backend/README.md`](backend/README.md) and [`web/README.md`](web/README.md) for the dev
commands for each layer, and [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full layout and
quality gates.

## Security

- The server binds `127.0.0.1` only, on a port the OS assigns at startup — never a fixed or
  externally reachable port.
- Every request needs a 32-byte random token generated fresh per process start; it is
  embedded in the toolbelt's own URL and never logged.
- No telemetry: the panel only runs the git commands you trigger, against your local
  checkout, using your existing git/ssh/credential-helper configuration.

## License

[MIT](LICENSE) © 2026 Francesco Sessa
