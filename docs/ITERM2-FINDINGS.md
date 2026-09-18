# iTerm2 verification findings

Produced by running `packaging/verify_iterm2.py` (see that file's docstring
for how to run it) against a real, running iTerm2. This fills in the
questions that could only be answered by a running iTerm2, plus everything later
learned by installing the panel for real.

## Environment

Verified 2026-09-18 on the user's machine: iTerm2 3.7.1 (`defaults read
/Applications/iTerm.app/Contents/Info.plist CFBundleShortVersionString` ->
`3.7.1`), macOS.

## Packaging: archive format, dependency separator, Python version pin

Verified 2026-09-18, by a live install attempt against the same real iTerm2 (3.7.1) on the
user's machine, and by reading iTerm2's own source (`iTermScriptImporter.m`,
`iTermSetupCfgParser.m`) for the exact rules it applies. The archive our build produced at
the time (`GitPanel.its`, comma-separated `install_requires`, `python_requires = >=3.11`)
could not be installed; these three defects are why, and are now fixed
(`packaging/build-archive.sh`, `packaging/setup.cfg.in`).

- **`.its` requires a signed archive; `.zip` is the unsigned path.**
  `iTermScriptImporter.m`'s `verifyAndUnwrapArchive:requireSignature:` calls
  `[verifier smellsLikeSignedArchive:]` for any file imported with a `.its` extension. The
  signed-archive format behind `.its` is gnachman's SignedArchive (a chunked tag/length
  structure carrying a certificate and signature) — we have no Apple Developer ID
  certificate to produce one, and a plain zip renamed to `.its` fails that check. On the
  live install attempt, this produced iTerm2's dialog: "This script archive is corrupt and
  cannot be installed." `reallyImportScriptFromURL` accepts the **`.zip`** extension for an
  unsigned, user-initiated import instead. Confirmed empirically: the identical archive
  bytes, renamed from `.its` to `.zip`, passed the check and reached Python provisioning.
  → We now build and publish `GitPanel.zip` (`packaging/build-archive.sh`), never `.its`.

- **`install_requires` must be separated with `;`, not `,`.** The second live-install
  failure was `uv pip failed with status 2. error: Failed to parse: 'iterm2,aiohttp,pydantic'`
  — the comma-separated value we generated was read back as a single requirement.
  `iTermSetupCfgParser.m` accumulates the `install_requires` value and splits it with
  `componentsSeparatedByString:@";"`; iTerm2's own setup.cfg writer joins dependencies with
  `@"; "`. → `packaging/setup.cfg.in` now reads
  `install_requires=iterm2; aiohttp; pydantic`.

- **`python_requires` must be an exact pin starting with `=`.** `iTermSetupCfgParser.m`
  discards it silently otherwise: `if (![expression hasPrefix:@"="]) { return; }`. Our
  previous `python_requires = >=3.11` was therefore never read by iTerm2 at all — no error,
  just silently ignored. iTerm2's own template writes `python_requires = =%@` (an exact
  version). → `packaging/setup.cfg.in` now reads `python_requires = =@PYTHON_VERSION@`,
  substituted by `packaging/build-archive.sh` (currently pinned to `3.12`, satisfying
  `backend/pyproject.toml`'s `requires-python = ">=3.11"` floor).

- **Python versions this iTerm2 build offers.** Verified from the app binary: **3.10, 3.11,
  3.12, 3.13**. `python_requires`'s pin must name one of these or iTerm2 has nothing to
  provision against.

## Import location, toolbelt registration and lifecycle

Verified 2026-09-18, live: importing a freshly built `GitPanel.zip` into the same real
iTerm2 (3.7.1) and watching what iTerm2 actually did with it, then separately watching an
already-registered toolbelt tool over several hours.

- **iTerm2 imports the script to `~/Library/Application Support/iTerm2/Scripts/GitPanel`,
  not to `AutoLaunch/`.** This answers the "which directory" question left open in
  `docs/MANUAL-CHECKS.md`. A script imported this way does **not** start automatically when
  iTerm2 launches -- the import dialog offers a "Launch" button, and otherwise the user
  starts it manually from the Scripts menu. `packaging/install.sh`'s "Next steps" text and
  `README.md`'s install steps previously told the user that quitting and reopening iTerm2
  would let AutoLaunch pick the script up; that was wrong and has been corrected (see
  `packaging/install.sh` and `README.md`).

- **`~/.config/iterm2/AppSupport` is a symlink to `~/Library/Application Support/iTerm2`**
  (confirmed: same inode). This is why the Script Console's log lines for this script show
  its path as `~/.config/iterm2/AppSupport/Scripts/GitPanel/...` rather than the
  `~/Library/...` path the script was actually imported to -- both paths name the same
  files. `packaging/uninstall.sh` operates on the `~/Library/Application Support/...` path,
  which is correct as written; do not "fix" it toward the `~/.config/...` alias.

- **Script Console logging works (spec §9 bullet 2).** The panel's stderr reaches
  Scripts > Manage > Console. Observed lines:
  `INFO git_iterm2.panel panel listening on port 62316` and
  `INFO git_iterm2.panel panel registered in the toolbelt`.

- **Toolbelt tool registrations persist in iTerm2's preferences independently of the
  registering script's process.** A probe script registered during earlier verification
  work still appeared, ticked, under View > Toolbelt hours after that script had exited.
  The registration lives in iTerm2's own preferences, not in anything this project writes
  to disk. Consequence: **uninstalling the script's files cannot remove the toolbelt menu
  entry** -- `packaging/uninstall.sh` deletes the script directory, but the user must
  manually untick the tool under View > Toolbelt themselves. This is now noted in
  `packaging/uninstall.sh`'s own output, in `README.md`'s uninstall step, and in
  `docs/MANUAL-CHECKS.md`'s Uninstall section.

- **Ticking a tool under View > Toolbelt does not itself show the toolbelt.** "Show
  Toolbelt" (⇧⌘B) is a separate toggle. With the toolbelt hidden, a correctly-registered,
  correctly-running panel is invisible, with no error anywhere -- nothing in iTerm2's UI
  hints that the toolbelt itself is hidden. This cost real debugging time during
  verification; worth remembering before concluding a registration has failed.

- **End to end, the panel works.** With the toolbelt shown (⇧⌘B) and Git ticked, the panel
  showed the active session's repository, its current branch, its untracked files, and all
  four tabs (Changes, Branches, Graph, Stash).

## Profile colours: separate light/dark pairs

Verified 2026-09-18 against the user's real profiles, which have "Use Separate Colors for
Light and Dark Mode" enabled -- `Background Color (Light)` / `Background Color (Dark)` key
pairs (and the same pairing for foreground, selection, cursor and all 16 ANSI colours).

The `iterm2` Python library's legacy properties (e.g. `profile.background_color`) return the
**light** variant regardless of which mode the profile is actually using. A panel that reads
only the legacy properties therefore renders light colours even on a dark terminal. The
library also exposes the light/dark-suffixed variants directly, and
`git_iterm2.iterm.theme` (`backend/src/git_iterm2/iterm/theme.py`) already reads both and
ships both palettes so the panel's CSS can choose -- this verification confirms that is the
correct approach against a real profile using separate colours, not just a theoretical one.

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

Toolbelt tool state after the script exited, and after re-running it: not observed by
`verify_iterm2.py` in this run -- see question 2 below. (A separate, later observation from a
different probe script did confirm the registration outlives the process; see "Import
location, toolbelt registration and lifecycle" above and question 2's updated answer.)

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

**Partially answered, 2026-09-18.** The registration half is now confirmed: a probe
script's toolbelt tool stayed listed and ticked under View > Toolbelt for hours after that
script's own process had exited -- see "Import location, toolbelt registration and
lifecycle" above. The registration lives in iTerm2's own preferences, not in anything this
project writes to disk, so it outlives the process that created it. **Still open:** whether
iTerm2 reopens the previously-registered URL against a *new* run of the script
automatically, or whether the panel only reconnects after the toolbelt is
toggled/reopened -- not exercised this run (see `docs/MANUAL-CHECKS.md`'s "Restart just the
script" item). Whether the tool survives a full iTerm2 quit/reopen is also still open
(`docs/MANUAL-CHECKS.md`'s "Toolbelt persistence" section) and was deliberately not guessed
at here. None of this changes what we build: spec §10 already requires the panel to
re-register on every start, and that is correct regardless of which way the remaining half
resolves. If iTerm2 does keep showing a stale registration after the process that
registered it exits, that stale entry would carry a now-dead per-process token from a
previous run -- re-registering on every start is exactly what replaces it with a live,
current token, so mandatory re-registration is not weakened by leaving this open.

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
