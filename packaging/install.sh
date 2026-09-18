#!/usr/bin/env bash
# Install the GitPanel iTerm2 toolbelt script, without the user touching a
# terminal beyond running this script.
#
# Usage:
#   packaging/install.sh [ARCHIVE_OR_URL]
#
# ARCHIVE_OR_URL is one of:
#   - a path to a local GitPanel.its (e.g. produced by packaging/build-its.sh)
#   - an https:// URL to a published GitPanel.its (plain http:// is refused;
#     see the curl --proto flags below)
#   - omitted, in which case $GITPANEL_RELEASE_URL is used
#
# In every case a sibling "<name>.sha256" (same path/URL with ".sha256"
# appended) must exist and must match, or the install is refused -- see the
# "Checksum" note below for exactly what that does and does not prove.
#
# A downloaded archive is saved to a PERSISTENT cache directory
# ($GITPANEL_CACHE_DIR, default ~/Library/Caches/git-iterm2 -- if set,
# GITPANEL_CACHE_DIR must be an absolute path, or this script refuses to
# run, since a relative one would resolve differently depending on the cwd
# it's invoked from) and left there after this script exits. It must NOT
# be deleted before iTerm2 finishes
# importing it: `open -a iTerm "<archive>"` hands the file to iTerm2 and
# returns immediately -- the unsigned-script approval dialog iTerm2 then
# shows is asynchronous and can sit unanswered for as long as the user
# takes, so anything that deletes the archive on this script's own exit
# (e.g. a `mktemp -d` + `trap ... EXIT`) would race it out from under a
# slow human. This script never writes into
# ~/Library/Application Support/iTerm2 itself -- it hands the verified
# archive to `open -a iTerm`, which runs iTerm2's own unsigned-script
# import flow (see the printed notice below).
set -euo pipefail

log()  { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || fail "this installer only supports macOS (found: $(uname -s))"
[[ -n "${HOME:-}" ]] || fail "\$HOME is not set; cannot locate iTerm2 or a cache directory"

# iTerm2's install location: honor an explicit override, then fall back to
# the two places it's actually installed in practice. `open -a iTerm`
# itself resolves the app via LaunchServices regardless of where it lives,
# so this only affects our own pre-flight checks (existence, version).
if [[ -n "${GITPANEL_ITERM_APP:-}" ]]; then
  ITERM_APP="${GITPANEL_ITERM_APP}"
  [[ -d "${ITERM_APP}" ]] || fail "GITPANEL_ITERM_APP=${ITERM_APP} does not exist"
else
  ITERM_APP=""
  for candidate in "/Applications/iTerm.app" "${HOME}/Applications/iTerm.app"; do
    if [[ -d "${candidate}" ]]; then
      ITERM_APP="${candidate}"
      break
    fi
  done
  if [[ -z "${ITERM_APP}" ]]; then
    fail "iTerm2 was not found at /Applications/iTerm.app or ~/Applications/iTerm.app.
  If it's installed somewhere else, set GITPANEL_ITERM_APP=/path/to/iTerm.app and re-run.
  Otherwise install iTerm2 first: https://iterm2.com"
  fi
fi
ITERM_PLIST="${ITERM_APP}/Contents/Info.plist"

ITERM_VERSION="$(defaults read "${ITERM_PLIST}" CFBundleShortVersionString 2>/dev/null || true)"
if [[ -z "${ITERM_VERSION}" ]]; then
  log "warning: could not read iTerm2's version from ${ITERM_PLIST}; continuing anyway"
else
  log "==> Found iTerm2 ${ITERM_VERSION} (${ITERM_APP})"
  # Minimum verified version per docs/ITERM2-FINDINGS.md: 3.5. This is a
  # warning, not a hard gate -- there is no evidence an older 3.x breaks
  # the import, only that 3.7.1 is the one actually verified.
  IFS='.' read -r ITERM_MAJOR ITERM_MINOR _rest <<< "${ITERM_VERSION}"
  if [[ "${ITERM_MAJOR}" =~ ^[0-9]+$ && "${ITERM_MINOR}" =~ ^[0-9]+$ ]]; then
    if (( ITERM_MAJOR < 3 || (ITERM_MAJOR == 3 && ITERM_MINOR < 5) )); then
      log "warning: iTerm2 ${ITERM_VERSION} is older than the verified minimum (3.5); the panel may not work"
    fi
  else
    log "warning: could not parse iTerm2 version '${ITERM_VERSION}' to compare against the minimum (3.5)"
  fi
fi

SOURCE="${1:-${GITPANEL_RELEASE_URL:-}}"
if [[ -z "${SOURCE}" ]]; then
  fail "no archive given. Usage: packaging/install.sh <path-or-https-url-to-GitPanel.its>
  (or set GITPANEL_RELEASE_URL). Build a local archive first with
  packaging/build-its.sh if you don't have one."
fi

download() {
  local url="$1" dest="$2"
  command -v curl >/dev/null 2>&1 || fail "curl is required to download ${url}"
  # --proto/--proto-redir pin both the initial request AND any redirect to
  # https, so a compromised or misconfigured host can't downgrade the
  # transfer to plain http (curl's -L alone would otherwise follow an
  # https->http redirect silently). Download to a ".part" file first and
  # rename on success so a failed/interrupted download never leaves a
  # half-written file at the real destination.
  curl -fsSL --proto '=https' --proto-redir '=https' -o "${dest}.part" "${url}" \
    || fail "failed to download ${url}"
  mv "${dest}.part" "${dest}"
}

if [[ "${SOURCE}" == https://* ]]; then
  CACHE_DIR="${GITPANEL_CACHE_DIR:-${HOME}/Library/Caches/git-iterm2}"
  # Reject a relative override outright rather than resolving it against
  # whatever directory this script happens to be run from: that would make
  # two installs from two different cwds silently use two different
  # caches, with no way to tell from the printed path alone.
  case "${CACHE_DIR}" in
    /*) ;;
    *) fail "GITPANEL_CACHE_DIR must be an absolute path (got: ${CACHE_DIR}); a relative path would resolve against whatever directory you run this script from" ;;
  esac
  mkdir -p "${CACHE_DIR}"
  log "==> Downloading ${SOURCE}"
  ARCHIVE="${CACHE_DIR}/GitPanel.its"
  SHA_FILE="${CACHE_DIR}/GitPanel.its.sha256"
  download "${SOURCE}" "${ARCHIVE}"
  download "${SOURCE}.sha256" "${SHA_FILE}"
  log "==> Saved to ${ARCHIVE}"
  log "    (kept there; do not delete it until iTerm2 finishes importing it)"
elif [[ "${SOURCE}" == http://* ]]; then
  fail "only https:// URLs are supported (got: ${SOURCE}); plain http is refused, not silently upgraded"
else
  [[ -f "${SOURCE}" ]] || fail "no such file: ${SOURCE}"
  ARCHIVE="${SOURCE}"
  SHA_FILE="${SOURCE}.sha256"
  [[ -f "${SHA_FILE}" ]] || fail "missing checksum file: ${SHA_FILE} (expected next to ${SOURCE})"
fi

log "==> Verifying checksum"
# NOTE on what this proves: the archive and its .sha256 sidecar are fetched
# from the same source/host, so a match only rules out transit corruption
# (a truncated or bit-flipped download). It is NOT an authenticity check --
# whoever controls the release host controls both files equally. There is
# no code-signing certificate for this archive (see the notice below); if
# you need real provenance, verify the source you downloaded from out of
# band, not this checksum.
EXPECTED_SHA="$(awk '{print $1; exit}' "${SHA_FILE}")"
[[ -n "${EXPECTED_SHA}" ]] || fail "could not read a checksum from ${SHA_FILE}"
ACTUAL_SHA="$(shasum -a 256 "${ARCHIVE}" | awk '{print $1}')"
if [[ "${EXPECTED_SHA}" != "${ACTUAL_SHA}" ]]; then
  fail "checksum mismatch for ${ARCHIVE}
  expected: ${EXPECTED_SHA}
  actual:   ${ACTUAL_SHA}
The downloaded bytes do not match their checksum (likely a corrupted or
truncated transfer). Not installing it."
fi
log "==> Checksum matches (${ACTUAL_SHA}) -- confirms the download is intact, not who published it"

log ""
log "==> GitPanel.its is UNSIGNED (no Apple Developer ID certificate)."
log "    iTerm2 will show its own \"unsigned script\" import warning -- this"
log "    is expected. You must approve it yourself; this installer cannot"
log "    and does not bypass that prompt."
log ""

log "==> Handing the archive to iTerm2"
open -a iTerm "${ARCHIVE}" || fail "failed to open ${ARCHIVE} with iTerm ('open -a iTerm' failed)"

log ""
log "Next steps in iTerm2:"
log "  1. Approve the unsigned-script import dialog iTerm2 shows."
log "  2. If iTerm2 asks to restart the script (or you don't see it right"
log "     away), quit and reopen iTerm2 once so AutoLaunch picks it up."
log "  3. Open View > Toolbelt > Git to show the panel."
log ""
log "To remove it later, run packaging/uninstall.sh."
