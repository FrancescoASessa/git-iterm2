#!/usr/bin/env bash
# Remove the GitPanel iTerm2 toolbelt script that packaging/install.sh (or
# iTerm2's own script importer) installed.
#
# Usage:
#   packaging/uninstall.sh [-y|--yes]
#
# iTerm2 can place an imported script's AutoLaunch entry at either of two
# locations depending on how it was imported; this checks both and deletes
# only the exact ones found. Never a broader directory -- nothing else
# under Scripts/ is touched.
#
# Verified 2026-09-18 against a real iTerm2 3.7.1 (docs/ITERM2-FINDINGS.md):
# a normal script-archive import lands in Scripts/GitPanel, NOT
# Scripts/AutoLaunch/GitPanel. Both are still checked below as a defensive
# fallback in case a differently-configured import used the other path.
#
# IMPORTANT: this script deletes files only. It CANNOT untick "Git" from
# View > Toolbelt -- that registration lives in iTerm2's own preferences,
# confirmed to persist independently of whether the script is even running,
# not in anything under Scripts/. After running this script, untick Git
# under View > Toolbelt yourself if you no longer want it listed.
set -euo pipefail

log()  { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

ASSUME_YES=0
for arg in "$@"; do
  case "${arg}" in
    -y|--yes) ASSUME_YES=1 ;;
    *) fail "unknown argument: ${arg}" ;;
  esac
done

[[ -n "${HOME:-}" ]] || fail "\$HOME is not set; refusing to guess where iTerm2's Scripts directory is"

ITERM_SCRIPTS_DIR="${HOME}/Library/Application Support/iTerm2/Scripts"
# Two candidate locations, both derived directly from ITERM_SCRIPTS_DIR:
#   - AutoLaunch/GitPanel: where a script configured to start with iTerm2
#     would land, if it were imported that way.
#   - GitPanel: where a real import against iTerm2 3.7.1 was actually
#     observed to land (verified 2026-09-18, docs/ITERM2-FINDINGS.md) --
#     this script does NOT start automatically with iTerm2.
# Both are checked rather than assuming only the observed one, in case a
# differently-configured import used the other path.
CANDIDATES=(
  "${ITERM_SCRIPTS_DIR}/AutoLaunch/GitPanel"
  "${ITERM_SCRIPTS_DIR}/GitPanel"
)

FOUND=()
for candidate in "${CANDIDATES[@]}"; do
  [[ -e "${candidate}" ]] && FOUND+=("${candidate}")
done

if [[ ${#FOUND[@]} -eq 0 ]]; then
  log "Nothing to remove. Checked:"
  for candidate in "${CANDIDATES[@]}"; do
    log "  ${candidate}"
  done
  exit 0
fi

log "Found GitPanel installed at:"
for target in "${FOUND[@]}"; do
  log "  ${target}"
  if [[ -d "${target}" ]]; then
    find "${target}" -maxdepth 2 -mindepth 1 -print | sed 's/^/    /'
  fi
done
log ""
log "This will permanently delete the path(s) above."
log ""

if [[ "${ASSUME_YES}" -ne 1 ]]; then
  if [[ ! -t 0 ]]; then
    fail "stdin is not a terminal, so there's no one to confirm with. Re-run with -y/--yes once you've reviewed the path(s) above."
  fi
  read -r -p "Proceed? [y/N] " REPLY
  case "${REPLY}" in
    y|Y|yes|YES) ;;
    *) log "Aborted; nothing was deleted."; exit 0 ;;
  esac
fi

for target in "${FOUND[@]}"; do
  rm -rf -- "${target}"
  log "Removed ${target}."
done

log ""
log "Note: 'Git' will still be listed (and ticked) under View > Toolbelt."
log "That registration lives in iTerm2's own preferences, not in the files"
log "just removed, and this script cannot clear it. Untick it yourself:"
log "View > Toolbelt > Git."
