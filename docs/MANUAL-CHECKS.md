# Manual verification checklist

Automated tests cover `core/`, `git/`, `api/` and `web/`. Nothing in CI runs a real iTerm2,
so `iterm/` — and anything about how the toolbelt webview actually behaves — only gets
checked here, by a human, against a real iTerm2, before a release.

Run this against a **freshly built** `GitPanel.zip` (`bash packaging/build-archive.sh`),
imported the way an end user would (double-click, or `packaging/install.sh`), not against a
copy already running from a previous install or from source.

For each item: do the step, then fill in the blank with what actually happened. Don't guess
or fill in an expected answer — several of these are explicitly open questions that only
this checklist can settle.

## Install

- [ ] Fresh install from a built `GitPanel.zip` (no prior GitPanel install on this machine).
      Double-click the archive, or run `packaging/install.sh dist/GitPanel.zip`.
      iTerm2 asks whether to launch the script automatically or manually — answer it.
      Result: ______________________________________________________
- [x] **Which directory did iTerm2 actually import the script into?** Check both:
      `~/Library/Application Support/iTerm2/Scripts/GitPanel` and
      `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/GitPanel`.
      Actual path: `~/Library/Application Support/iTerm2/Scripts/GitPanel` -- **not**
      `AutoLaunch/`. Verified 2026-09-18 against a real iTerm2 3.7.1. See
      docs/ITERM2-FINDINGS.md. (`packaging/uninstall.sh` still checks both locations as a
      defensive fallback, but the one actually used is now known.)
- [x] After import, quit and reopen iTerm2. Does the script start automatically (AutoLaunch),
      or does it need to be started manually via Scripts menu?
      Result: does not start automatically -- it was imported outside `AutoLaunch/`, so
      there is nothing for AutoLaunch to pick up. Start it from the import dialog's
      "Launch" button, or later from the Scripts menu. Verified 2026-09-18; `README.md` and
      `packaging/install.sh` previously said otherwise and have been corrected.
- [x] Open **View › Toolbelt › Git**. Does the panel appear and load a snapshot?
      Result: yes, once the toolbelt itself is shown (see the "Show Toolbelt" note below --
      ticking the tool alone does not display it). With the toolbelt shown and Git ticked,
      the panel loaded the active session's repository, branch, untracked files, and all
      four tabs. Verified 2026-09-18.
- [x] **Ticking Git under View › Toolbelt is not the same as showing the toolbelt.** "Show
      Toolbelt" (⇧⌘B) is a separate toggle; with the toolbelt hidden, a correctly-registered,
      correctly-running panel is invisible with no error anywhere. Verified 2026-09-18 --
      this cost real debugging time. See docs/ITERM2-FINDINGS.md.

## Toolbelt persistence

- [x] With the Git tool visible in the toolbelt, quit and reopen iTerm2. Is the tool still
      present in the toolbelt afterwards, or does it have to be re-added via
      View › Toolbelt › Git each time?
      Result: present, **provided the script is in `Scripts/AutoLaunch/`**. With the script
      moved there, a full quit (⌘Q) and reopen restarted it on its own and the panel was
      back in the toolbelt with no action from the user. Imported to `Scripts/` (the default
      for a `.zip` import), nothing restarts it. Verified 2026-09-18, iTerm2 3.7.1.
- [x] **Related but narrower finding (verified 2026-09-18, not a substitute for the check
      above):** a tool's registration persists in iTerm2's *preferences* independently of
      whether the registering script's process is still running -- a probe script's tool
      stayed listed and ticked for hours after that script had exited, with iTerm2 never
      quit. This means uninstalling the script's files does **not** remove the toolbelt menu
      entry; the user must untick it manually under View › Toolbelt (see the Uninstall
      section below). Whether the entry also survives a full iTerm2 quit/reopen (the item
      above) was not tested and remains open. See docs/ITERM2-FINDINGS.md.
- [ ] Restart just the script (Scripts › Manage › kill and re-run, or `kill` the process and
      let AutoLaunch restart it) without quitting iTerm2. Does the toolbelt panel reconnect
      on its own, or does it need the toolbelt to be toggled/reopened?
      Result: ______________________________________________________

## Following the active session

- [ ] Open two tabs in different git repositories. Switch between them — does the panel
      switch to the corresponding repo each time?
      Result: ______________________________________________________
- [ ] In one session, `cd` into a different repository (or a subdirectory of the same one).
      Does the panel follow within about a second?
      Result: ______________________________________________________
- [ ] `cd` into a directory that is not a git repository. Does the panel show the
      "not a git repository" empty state?
      Result: ______________________________________________________
- [ ] Open a session without iTerm2 Shell Integration installed (or in a profile with it
      disabled). Does the panel show the "Shell Integration not enabled" hint instead of
      guessing a directory?
      Result: ______________________________________________________

## Appearance

The panel's surfaces are deliberately *not* the profile's colors (see §5 of the design
spec): they are neutral and follow the **system** appearance. Only the accent (branch and
ref labels, primary button, focus ring) and the diff green/red come from the profile.

- [ ] In a dark terminal, is the panel dark — and light in a light one? Check with a
      profile that has "Use Separate Colors for Light and Dark Mode" **on** and one with
      it **off**.
      Result: ______________________________________________________
- [ ] Switch macOS System Settings ▸ Appearance between Light and Dark while the panel is
      open, without touching iTerm2. Does the panel follow immediately (no focus change,
      no reopen)?
      Result: ______________________________________________________
      (Genuinely untested as of 2026-09-18. This is the untested assumption behind the
      light/dark surface theming added in `feat(ui): restyle the panel as a native macOS
      surface`: the CSS relies on `prefers-color-scheme` inside the toolbelt's WKWebView,
      and whether that media query re-resolves live when macOS appearance changes while the
      webview is already running -- rather than only on next load -- has not been observed.
      Do not assume either answer.)
- [ ] Do the branch label and ref chips use the profile's blue (ANSI 4), and do diff
      added/removed lines use the profile's green/red as a tint rather than a solid
      terminal background?
      Result: ______________________________________________________
- [ ] Is UI text in the system font and only repository text (branch names, file paths,
      commit hashes, `stash@{n}`, diff content) in the profile's monospace font, at the
      profile's size?
      Result: ______________________________________________________
- [ ] Switch the active session to a profile with different colors and a different font.
      Does the panel update, and after which action (immediately, or only after the next
      focus change)?
      Result: ______________________________________________________
- [ ] Narrow the toolbelt to its minimum and widen it. Does every control stay reachable,
      with no horizontal scrollbar, in Changes / Branches / Graph / Stash?
      Result: ______________________________________________________
- [ ] Tab through the panel with the keyboard. Is the focus ring visible on rows, tabs and
      buttons?
      Result: ______________________________________________________

## Diff

- [ ] Click a changed file in the Changes tab — does an inline diff render?
      Result: ______________________________________________________
- [ ] Double-click (or `⌥`-click) a changed file — does it open a new split pane running
      `git diff`?
      Result: ______________________________________________________
- [ ] Repeat the split-pane diff for a file whose name contains a space and a `$`
      (e.g. `touch 'weird $file name.txt'`, then edit it). Does the split open cleanly with
      the correct file, with no shell-expansion or quoting problems?
      Result: ______________________________________________________

## Remote operations

- [ ] Fetch against a real remote. Does it complete and update ahead/behind counts?
      Result: ______________________________________________________
- [ ] Pull against a real remote (fast-forward case). Does it complete and refresh the
      snapshot?
      Result: ______________________________________________________
- [ ] Push against a real remote. Does it complete, and does progress show while it runs?
      Result: ______________________________________________________
- [ ] Trigger `AUTH_REQUIRED` (e.g. push somewhere without valid credentials cached). Does
      the UI offer "Run in split", and does that split run the command in a real terminal
      pane?
      Result: ______________________________________________________

## Merge conflict

- [ ] Create a real merge conflict (merge two branches that touch the same lines) and open
      the panel. Does the merge-in-progress banner appear with Continue/Abort?
      Result: ______________________________________________________
- [ ] Resolve the conflict and click Continue. Does it complete the merge?
      Result: ______________________________________________________
- [ ] Start another conflicting merge and click Abort. Does it cleanly return to the
      pre-merge state?
      Result: ______________________________________________________

## Stash round-trip

- [ ] Push a stash with a message (try both with and without "include untracked").
      Result: ______________________________________________________
- [ ] Apply it, then pop it, then drop one. Does the Stash tab and count stay correct
      throughout?
      Result: ______________________________________________________

## Keyboard focus in the toolbelt webview

Spec §10 leaves this open — it is not exercised by any automated test. With the toolbelt
panel focused:

- [x] Type a commit message into the commit textarea. Do the characters land in the
      textarea?
      Result: yes. Clicking the textarea gives it focus, typed text lands in it rather than
      in the terminal behind, and committing from the panel worked end to end. Verified
      2026-09-18, iTerm2 3.7.1.
- [ ] Press `⌘↵` inside the commit textarea. Does it trigger commit (rather than doing
      nothing, or being intercepted by iTerm2)?
      Result: ______________________________________________________
- [ ] Open a confirm dialog (e.g. discard or force-push) and press `Escape`. Does it close
      the dialog?
      Result: ______________________________________________________
- [ ] With that dialog open, press `Tab` repeatedly. Does focus stay inside the dialog's own
      controls, or does it escape to something else?
      Result: ______________________________________________________
- [ ] Press `/` to focus the branch filter input. Does it focus the input, or does iTerm2/the
      terminal intercept it (e.g. as a terminal search shortcut)?
      Result: ______________________________________________________

A bad outcome on any of the above (keystrokes reaching the terminal session underneath
instead of the webview, `⌘↵`/Escape/Tab doing nothing or the wrong thing) is worth filing
as an issue even though nothing here can auto-detect it.

## Logs contain no token

- [ ] After using the panel for a while (including at least one failed request), run:

      grep -c "t=" ~/Library/Logs/git-iterm2/panel.log

  Expected: `0`, or only matches that are not the auth token (inspect any hits by hand).
      Result: ______________________________________________________

## Uninstall

**Known going in (verified 2026-09-18, see docs/ITERM2-FINDINGS.md): a toolbelt tool's
registration lives in iTerm2's own preferences, not in the script's files. Deleting the
files cannot and does not remove the "Git" entry from View › Toolbelt -- the user must
untick it there themselves.** Do not treat the entry still being listed after an uninstall
as a bug in `packaging/uninstall.sh`; check the box below with that expectation in mind.

- [ ] Run `packaging/uninstall.sh` and confirm. Does it report removing the path(s) found in
      the "which directory" check above?
      Result: ______________________________________________________
- [ ] After uninstalling, confirm both candidate directories
      (`~/Library/Application Support/iTerm2/Scripts/GitPanel` and
      `.../Scripts/AutoLaunch/GitPanel`) are gone. Separately, confirm the Git entry is still
      listed (ticked) under View › Toolbelt until unticked by hand, and untick it.
      Result: ______________________________________________________
