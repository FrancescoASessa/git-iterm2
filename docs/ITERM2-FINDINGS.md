# iTerm2 verification findings

Produced by running `packaging/verify_iterm2.py` (see that file's docstring
for how to run it) against a real, running iTerm2. This fills in the
"Remaining" items of spec §10 (`docs/superpowers/specs/2026-09-17-git-iterm2-design.md`).

## Environment

Verified 2026-09-18 on the user's machine: iTerm2 3.7.1 (`defaults read
/Applications/iTerm.app/Contents/Info.plist CFBundleShortVersionString` ->
`3.7.1`), macOS.

## Raw output

```json
{
  "iterm2_version": null,
  "profile": {
    "ansi_0": "#14191e",
    "ansi_15": "#ffffff",
    "background": "#fafafa",
    "background_color_space": "SRGB",
    "foreground": "#101010",
    "name": "Default",
    "normal_font": "Monaco 12",
    "selection": "#b3d7ff"
  },
  "profile_name_variable_fires": false,
  "registered_url": "http://127.0.0.1:62948/?t=verification-token",
  "session_id": "D62DEB99-F656-4FA5-AAA1-1F8A62AA1BF1",
  "session_path": "/Users/francesco/Progetti/git-iterm2/backend",
  "webview_headers": {
    "host": "127.0.0.1:62948",
    "origin": null,
    "sec_fetch_site": "none",
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) iTerm2"
  },
  "webview_query": {"t": "verification-token"}
}
```

Toolbelt tool state after the script exited, and after re-running it: not
observed in this run -- see question 2 below, which is left open.

## Questions and answers

### 1. Does the toolbelt webview send `Origin`? What `Host` does it use?

Drives whether the backend's Origin check needs an exception for the
toolbelt webview -- it must NOT be relaxed without evidence.

**Answer:** No. The webview sends `Host: 127.0.0.1:<port>` (matching the
bound server's own port, here `62948`) and does **not** send an `Origin`
header at all (`"origin": null`), with `Sec-Fetch-Site: none`. This matches
`git_iterm2.api.security.security_middleware`
(`backend/src/git_iterm2/api/security.py`) as written today: it checks
`request.host` against `{f"127.0.0.1:{port}", f"localhost:{port}"}`
unconditionally, but only rejects on `Origin` when one is *present* and not
in the allowlist (`if origin is not None and origin not in {...}`) --
`X-Token` is still required on every `/api/` request regardless. **No
backend change is needed, and the Origin check must not be relaxed
further** -- a missing Origin is already accepted, and the token is what
actually authenticates the toolbelt webview. Do not "fix" the Origin check
later; there is nothing to fix, and loosening the Host allowlist or the
token requirement to accommodate the webview would be a real regression.

### 2. Does the toolbelt tool persist across script restarts, and does iTerm2 reopen the previously registered URL?

Drives whether the panel must re-register on every start (spec §10 says it
must).

**Answer:** Unanswered by this run -- the toolbelt-tool state after the
script exited, and after a second run, was not reported back. **Left open.**
It does not change what we build: spec §10 already requires the panel to
re-register on every start, and that is correct regardless of which way
this question resolves. If iTerm2 does keep showing a stale registration
after the process that registered it exits, that stale entry would carry a
now-dead per-process token from a previous run -- re-registering on every
start is exactly what replaces it with a live, current token, so
mandatory re-registration is not weakened by leaving this open.

### 3. Is there a usable profile-change signal, or is re-reading the profile on active-session change enough?

**Answer:** No usable signal was observed. `profile_name_variable_fires:
false` -- the `profileName` session variable did not fire during the
observed window even though the user switched profile. Do not rely on any
profile-change notification; re-read the profile on each focus/path event
instead (spec's `VariableMonitor` on `path`, plus `FocusMonitor`, already
does this). Consequence: the panel's theme updates on the *next* focus
change after the user switches profile, not the instant they switch it --
this is an accepted latency, not a bug to chase with a monitor that has
been shown not to fire.

### 4. The exact iTerm2 version verified, and the minimum the installer should require.

**Answer:** Verified iTerm2 version: **3.7.1**. The `iterm2.version` app
variable (`iterm2.async_get_variable(connection, "iterm2.version")`)
returned `null` with no exception -- it is not a usable source for the
running iTerm2's version. Version detection must instead read
`CFBundleShortVersionString` from `/Applications/iTerm.app/Contents/Info.plist`
(e.g. via `defaults read`), which is how this run's version was confirmed.
The declared minimum stays **3.5** (spec's existing floor; nothing in this
run's findings requires raising it -- all APIs the panel uses were already
confirmed present in 3.7.1 and none of them are 3.6/3.7-only per the
`iterm2` package docs consulted for the resolved items above).

## Still open

### 5. Keyboard focus handling in the toolbelt webview

Not exercised by `verify_iterm2.py` or by any automated test -- it needs a
human interacting with the real toolbelt in a real iTerm2, because it
depends on how iTerm2 itself routes keyboard events between the toolbelt
webview and the terminal session next to it. **Answered by Task 9's manual
checklist, not by this script.**

What to try, with the toolbelt panel focused:

- Type a commit message into the commit textarea -- do the characters land
  in the textarea?
- Press ⌘↵ inside the commit textarea -- does it trigger commit (rather
  than doing nothing, or being swallowed by iTerm2/the terminal)?
- Open a confirm dialog (e.g. discard/force-push) and press Escape -- does
  it close the dialog? Press Tab -- does focus move between the dialog's
  own controls (and stay inside the dialog), or does it escape to
  something else?
- Press `/` to focus the branch filter input -- does it focus the input
  instead of being interpreted as an iTerm2/terminal shortcut?

What a bad outcome looks like: keystrokes reaching the terminal session
underneath instead of the webview (e.g. `/` opening a terminal search, or
typed characters appearing in the shell prompt instead of the textarea),
⌘↵ doing nothing or triggering an iTerm2 action instead of commit, Escape
not closing the dialog, or Tab moving focus outside the dialog while it's
still open.

## Library notes

- **`iterm2.Color.hex` raises `ValueError` for profile colours, in iterm2
  2.23.** `Color.from_dict` (used to populate `Profile.background_color`
  etc.) stores `.red`/`.green`/`.blue` as `float` (`float(input_dict[...]) *
  255`), but the `.hex` property formats them with the `%02x`-style spec
  `format(self.red, '02x')`, and Python's `format()` rejects an `'x'`
  format code for a `float`. Confirmed against the installed package
  source (`iterm2/color.py`) and reproduced live: `verify_iterm2.py`
  crashed with exactly this `ValueError` on its first run against a real
  iTerm2 (3.7.1) before this fix. Any code that needs a profile colour's
  hex — including the panel's adapter — must compute it itself (round and
  clamp `.red`/`.green`/`.blue` to `0..255` ints, then format), not call
  `.hex`. `packaging/verify_iterm2.py`'s `color_hex()` helper is the
  reference implementation.
- Profile colours default to `ColorSpace.CALIBRATED`, not `sRGB`
  (`Color.from_dict`'s fallback when the profile dict has no `"Color
  Space"` key). `iterm2.Color.hex` assumes sRGB and does nothing special
  for `CALIBRATED` (only `P3` gets a `p3` prefix), so this is silently
  inaccurate even where `.hex` doesn't crash. The verification script
  records `background_color_space` so this can be checked against what a
  real profile reports.
- On the verification run above, the "Default" profile's colours came back
  in `SRGB` (`background_color_space: "SRGB"`), not `CALIBRATED` -- so on
  this machine/profile our round-and-clamp `color_hex()` is exact, with no
  colour-space conversion needed. This is still per-profile, not
  guaranteed: a profile that explicitly sets `CALIBRATED` (or omits
  `"Color Space"`, which `Color.from_dict` defaults to `CALIBRATED`) would
  get raw-value hex without gamma/colour-space correction. Treat
  `color_hex()`'s output as "close enough for a terminal theme," not
  colour-managed.
- `iterm2.async_get_variable(connection, "iterm2.version")` returns `null`
  (no exception) rather than a version string -- it is not a usable source
  for the running iTerm2's version. See question 4 above: read
  `CFBundleShortVersionString` from Info.plist instead.
