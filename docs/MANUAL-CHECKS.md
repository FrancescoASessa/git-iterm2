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
- [ ] **Which directory did iTerm2 actually import the script into?** Check both:
      `~/Library/Application Support/iTerm2/Scripts/GitPanel` and
      `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/GitPanel`.
      Actual path: __________________________________________________
      (`packaging/uninstall.sh` currently checks both locations because this hadn't been
      verified yet; once answered, it can be simplified to the one that's actually used.)
- [ ] After import, quit and reopen iTerm2. Does the script start automatically (AutoLaunch),
      or does it need to be started manually via Scripts menu?
      Result: ______________________________________________________
- [ ] Open **View › Toolbelt › Git**. Does the panel appear and load a snapshot?
      Result: ______________________________________________________

## Toolbelt persistence

- [ ] With the Git tool visible in the toolbelt, quit and reopen iTerm2. Is the tool still
      present in the toolbelt afterwards, or does it have to be re-added via
      View › Toolbelt › Git each time?
      Result: ______________________________________________________
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

## Theme

- [ ] Panel colors match the active profile's background/foreground/selection/ANSI colors.
      Result: ______________________________________________________
- [ ] Switch the active session to a different profile (with different colors). Does the
      panel's theme update, and after which action (immediately, or only after the next
      focus change)?
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

- [ ] Type a commit message into the commit textarea. Do the characters land in the
      textarea?
      Result: ______________________________________________________
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

- [ ] Run `packaging/uninstall.sh` and confirm. Does it report removing the path(s) found in
      the "which directory" check above?
      Result: ______________________________________________________
- [ ] After uninstalling, confirm both candidate directories
      (`~/Library/Application Support/iTerm2/Scripts/GitPanel` and
      `.../Scripts/AutoLaunch/GitPanel`) are gone, and that the Git tool no longer appears
      under View › Toolbelt after restarting iTerm2.
      Result: ______________________________________________________
