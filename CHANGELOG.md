# Changelog

All notable changes to this project are documented in this file.

## 0.1.0 — 2026-09-18

### Added

- Git source-control panel in the iTerm2 toolbelt (View › Toolbelt › Git), following the
  active session's repository as you `cd` or switch tabs.
- **Changes** tab: staged, unstaged, untracked and conflicted files; stage/unstage/discard;
  commit with amend; inline unified diff preview; open a diff in a new split pane.
- **Branches** tab: local and remote branches with upstream and last commit, filter,
  checkout (with stash-and-checkout on a dirty tree), create, rename, delete, set upstream.
- **Graph** tab: paginated, lane-rendered commit graph with commit detail and per-file diff.
- **Stash** tab: list, push (message, include untracked), apply, pop, drop.
- Remote operations (fetch, pull, push) with progress, and a merge/rebase/cherry-pick banner
  with Continue/Abort.
- Local REST + WebSocket API (`/api/...`, `/ws`) served by an in-process aiohttp backend,
  bound to `127.0.0.1` on an OS-assigned port with a per-process token; OpenAPI schema and
  generated TypeScript client types.
- Packaging as an unsigned iTerm2 `.zip` script archive (`packaging/build-archive.sh`), with
  `packaging/install.sh` and `packaging/uninstall.sh` for scripted install/removal.
- Logging to `~/Library/Logs/git-iterm2/` (rotated, level via `GIT_ITERM2_LOG_LEVEL`), with
  startup info and errors also shown in the iTerm2 Script Console. The panel's token is
  redacted from both.
