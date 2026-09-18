# Security

git-iterm2 runs a local HTTP server and executes `git` on your repositories. This
page describes what that server exposes, what protects it, and what it
deliberately does not protect against.

## Reporting a vulnerability

Report privately through GitHub's **Security ▸ Report a vulnerability** on this
repository, which opens a draft advisory only the maintainers can see. Please do
not open a public issue for something exploitable.

Include what you did, what happened, and the version (`backend/pyproject.toml`
carries it). A proof of concept helps; a working exploit against someone else's
machine is not needed and not wanted.

## What the panel exposes

The panel is a web page served to iTerm2's toolbelt web view by a Python process
that starts when you launch the script and dies with it. That process:

- binds **127.0.0.1 only**, on a **port the OS assigns** — never a fixed port,
  never an external interface;
- mints a **fresh token per process** (`secrets.token_urlsafe(32)`), which the
  web view carries in its URL. Every API request must present it in an
  `X-Token` header, compared with `hmac.compare_digest`;
- checks the `Host` header against an allowlist, so a malicious page cannot
  reach the server by resolving a hostname it controls to 127.0.0.1
  (DNS rebinding);
- requires a WebSocket client to authenticate in its first frame within five
  seconds, and closes the connection with code 4401 otherwise;
- **never logs the token** — a logging filter redacts it from messages,
  arguments, exception text and stack info, aiohttp's access log is off (it
  would otherwise record the query string), and `Referrer-Policy: no-referrer`
  keeps it out of outbound requests.

The page itself is served with a Content-Security-Policy restricting scripts,
styles and connections to its own origin.

## How git is run

- Every invocation goes through an argument list — **no shell**, so a branch or
  file name cannot become a command.
- `GIT_TERMINAL_PROMPT=0` and a non-interactive environment: a remote operation
  that wants credentials fails instead of hanging on an invisible prompt.
- Paths are passed after `--` with `GIT_LITERAL_PATHSPECS=1`, so a file named
  like a flag or a glob is treated as a file.
- The one place a command reaches a shell is "open this diff in a split", which
  writes a command line into a new iTerm2 session; every interpolated path goes
  through `shlex.quote`.
- Destructive operations (discard, force checkout, stash drop, branch delete)
  require explicit confirmation in the UI.

## What this does not protect against

**Another process running as you.** The token lives in this user's memory and in
the web view's URL. A process running as your user can already read your files
and run `git` itself, so the panel does not try to defend that boundary. The
protections above are aimed at *other* machines on the network and at *other
origins* in a browser.

**A hostile repository, partially.** The panel runs `git` inside whatever
directory your active session is in. Git itself executes repository-controlled
code in some configurations — hooks, `core.fsmonitor`, some `filter` drivers —
and the panel does not sandbox that. Treat opening a shell in an untrusted
repository as the risk it already is; the panel does not add to it, but it does
not remove it either.

**Distribution.** Release archives are **not code-signed** — no Apple Developer
certificate is involved, and none is planned. Two things stand in for that, and
they answer different questions:

- The published `.sha256` proves **integrity**: the file you downloaded is the
  file that was published. It says nothing about who published it — it is
  served from the same place as the archive, so anyone able to replace one can
  replace both.
- A [build provenance attestation][attestation] proves **origin**: GitHub
  signs, through Sigstore, a statement binding the archive's digest to this
  repository, the commit it was built from and the GitHub Actions run that
  built it. The signature is not served from this repository's release page,
  so replacing the archive does not let anyone replace the attestation.
  Verify it before installing:

  ```sh
  gh attestation verify GitPanel.zip --repo FrancescoASessa/git-iterm2
  ```

What the attestation does **not** do: it does not make macOS or iTerm2 treat
the archive as signed. Gatekeeper and iTerm2's importer know nothing about it,
so the unsigned-import prompt is exactly as it was. It is a check you run
deliberately, not one the operating system runs for you.

If neither is enough for you, build the archive yourself from source:
`bash packaging/build-archive.sh`.

[attestation]: https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds

## Supported versions

Fixes go to the latest release. While the project is at `0.x`, that is the only
supported line.
