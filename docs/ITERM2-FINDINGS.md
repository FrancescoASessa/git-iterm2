# iTerm2 verification findings

Produced by running `packaging/verify_iterm2.py` (see that file's docstring
for how to run it) against a real, running iTerm2. This fills in the
"Remaining" items of spec §10 (`docs/superpowers/specs/2026-09-17-git-iterm2-design.md`).

## Raw output

Paste the script's JSON output here verbatim, plus what happened to the
`git-iterm2 verify` toolbelt tool after the script exited and after it was
run a second time.

```json
(pending)
```

Toolbelt tool state after the script exited (first run): (pending)

Toolbelt tool state after re-running the script (does iTerm2 reopen the
previously registered URL on its own, or only after the new registration
call completes?): (pending)

## Questions and answers

### 1. Does the toolbelt webview send `Origin`? What `Host` does it use?

Drives whether the backend's Origin check needs an exception for the
toolbelt webview -- it must NOT be relaxed without evidence.

**Answer:** (pending)

### 2. Does the toolbelt tool persist across script restarts, and does iTerm2 reopen the previously registered URL?

Drives whether the panel must re-register on every start (spec §10 says it
must).

**Answer:** (pending)

### 3. Is there a usable profile-change signal, or is re-reading the profile on active-session change enough?

**Answer:** (pending)

### 4. The exact iTerm2 version verified, and the minimum the installer should require.

**Answer:** (pending)
