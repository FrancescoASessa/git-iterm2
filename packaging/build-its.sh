#!/usr/bin/env bash
# Build the GitPanel.its iTerm2 script archive.
#
# Usage: packaging/build-its.sh [OUTPUT_DIR] [--skip-web-build] [--web-dist PATH]
#
# OUTPUT_DIR defaults to "dist" resolved against the repo root. Produces
# OUTPUT_DIR/GitPanel.its and OUTPUT_DIR/GitPanel.its.sha256 (checksum of
# the bare "GitPanel.its" filename, so `install.sh` can verify it after
# downloading both files into the same directory, wherever that is).
#
# By default this rebuilds the web UI (`cd web && npm ci && npm run build`)
# before packaging it. Pass --skip-web-build to reuse whatever is already
# at web/dist (or --web-dist PATH to use a different prebuilt directory)
# instead -- this is what backend/tests/test_packaging.py uses, so running
# the test suite never mutates web/node_modules or web/dist and never needs
# network access.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUT_DIR_ARG="dist"
SKIP_WEB_BUILD=0
WEB_DIST_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-web-build)
      SKIP_WEB_BUILD=1
      shift
      ;;
    --web-dist)
      [[ $# -ge 2 ]] || { echo "error: --web-dist requires a path argument" >&2; exit 1; }
      WEB_DIST_OVERRIDE="$2"
      SKIP_WEB_BUILD=1
      shift 2
      ;;
    --*)
      echo "error: unknown option: $1" >&2
      exit 1
      ;;
    *)
      OUT_DIR_ARG="$1"
      shift
      ;;
  esac
done

case "${OUT_DIR_ARG}" in
  /*) OUT_DIR="${OUT_DIR_ARG}" ;;
  *) OUT_DIR="${REPO_ROOT}/${OUT_DIR_ARG}" ;;
esac
mkdir -p "${OUT_DIR}"
OUT_DIR="$(cd "${OUT_DIR}" && pwd)"

PYPROJECT="${REPO_ROOT}/backend/pyproject.toml"
if [[ ! -f "${PYPROJECT}" ]]; then
  echo "error: cannot find ${PYPROJECT}" >&2
  exit 1
fi

# Tolerate the version line being quoted with ' or " (either is valid TOML),
# then validate its shape strictly: only characters that are safe to splice
# into `sed "s/@VERSION@/${VERSION}/"` unescaped below (no /, &, \, quotes,
# or whitespace) and into setup.cfg as a bare value. If the pyproject line
# doesn't look like `version = "x"` / `version = 'x'` at all, or the
# extracted value fails the shape check, fail loudly instead of silently
# writing whatever grep/sed produced (which, before this check, could be
# the entire unmatched `version = '0.1.0'` line verbatim into setup.cfg).
VERSION_LINE="$(grep -m1 '^version' "${PYPROJECT}" || true)"
if [[ -z "${VERSION_LINE}" ]]; then
  echo "error: no 'version' line found in ${PYPROJECT}" >&2
  exit 1
fi
VERSION="$(printf '%s\n' "${VERSION_LINE}" | sed -E "s/^version[[:space:]]*=[[:space:]]*['\"]([^'\"]+)['\"].*/\\1/")"
if [[ "${VERSION}" == "${VERSION_LINE}" || -z "${VERSION}" ]]; then
  echo "error: could not extract a version from: ${VERSION_LINE}" >&2
  exit 1
fi
if [[ ! "${VERSION}" =~ ^[0-9A-Za-z.+-]+$ ]]; then
  echo "error: version '${VERSION}' (from ${PYPROJECT}) has an unexpected shape; expected something like 0.1.0" >&2
  exit 1
fi

echo "==> Building GitPanel.its version ${VERSION}"

if [[ "${SKIP_WEB_BUILD}" -eq 1 ]]; then
  WEB_DIST="${WEB_DIST_OVERRIDE:-${REPO_ROOT}/web/dist}"
  case "${WEB_DIST}" in
    /*) ;;
    *) WEB_DIST="${REPO_ROOT}/${WEB_DIST}" ;;
  esac
  echo "==> Skipping web build, using ${WEB_DIST}"
else
  WEB_DIST="${REPO_ROOT}/web/dist"
  echo "==> Building web assets (web/dist)"
  ( cd "${REPO_ROOT}/web" && npm ci && npm run build )
fi

web_dist_hint() {
  # Prints the right follow-up hint for either failure below, depending on
  # whether WEB_DIST came from --skip-web-build/--web-dist or from the
  # npm build this script just ran itself.
  if [[ "${SKIP_WEB_BUILD}" -eq 1 ]]; then
    echo "  (--skip-web-build/--web-dist requires an already-built web/dist; run 'npm run build' in web/ first, or drop the flag)" >&2
  else
    echo "  ('npm run build' just ran but did not produce a usable web/dist)" >&2
  fi
}

if [[ ! -f "${WEB_DIST}/index.html" ]]; then
  echo "error: ${WEB_DIST}/index.html not found" >&2
  web_dist_hint
  exit 1
fi

# A bare index.html isn't enough -- that's what a placeholder/stub dist
# looks like too, and it would build and ship an archive iTerm2 happily
# imports with a panel that renders blank. Require at least one built JS
# asset, checked identically whether WEB_DIST came from a fresh build or
# from --skip-web-build/--web-dist, so a broken `npm run build` can't ship
# either.
JS_ASSET_COUNT=0
if [[ -d "${WEB_DIST}/assets" ]]; then
  # Only run `find` once the directory is known to exist: under
  # `set -eo pipefail`, `find` on a missing directory exits non-zero and
  # would otherwise abort the script right here instead of falling through
  # to the error message below.
  JS_ASSET_COUNT="$(find "${WEB_DIST}/assets" -maxdepth 1 -type f -name '*.js' | wc -l | tr -d '[:space:]')"
fi
if [[ "${JS_ASSET_COUNT}" -eq 0 ]]; then
  echo "error: ${WEB_DIST}/assets has no .js file -- this doesn't look like a real Vite build (a bare index.html isn't enough)" >&2
  web_dist_hint
  exit 1
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gitpanel-build.XXXXXX")"
cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

STAGE_ROOT="${WORK_DIR}/GitPanel"
PKG_DIR="${STAGE_ROOT}/GitPanel"
mkdir -p "${PKG_DIR}"

echo "==> Assembling staging directory"
sed "s/@VERSION@/${VERSION}/" "${SCRIPT_DIR}/setup.cfg.in" > "${STAGE_ROOT}/setup.cfg"
cp "${SCRIPT_DIR}/GitPanel/GitPanel.py" "${PKG_DIR}/GitPanel.py"

cp -R "${REPO_ROOT}/backend/src/git_iterm2" "${PKG_DIR}/git_iterm2"

# Defensive: never ship bytecode caches, .pyc files, or a stray tests/
# directory, even though none of these exist under backend/src/git_iterm2
# today.
find "${PKG_DIR}/git_iterm2" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "${PKG_DIR}/git_iterm2" -type f -name '*.pyc' -delete
rm -rf "${PKG_DIR}/git_iterm2/tests"

# The bundled web/ directory comes from WEB_DIST (a fresh build or the
# caller-supplied/prebuilt one -- see --skip-web-build/--web-dist above),
# not from anything already under backend/src/git_iterm2 (there is nothing
# there today, but this keeps the source of truth explicit).
rm -rf "${PKG_DIR}/git_iterm2/web"
cp -R "${WEB_DIST}" "${PKG_DIR}/git_iterm2/web"

echo "==> Zipping archive"
ARCHIVE="${OUT_DIR}/GitPanel.its"
rm -f "${ARCHIVE}"
( cd "${WORK_DIR}" && zip -r -X "${ARCHIVE}" GitPanel > /dev/null )

echo "==> Writing checksum"
( cd "${OUT_DIR}" && shasum -a 256 "$(basename "${ARCHIVE}")" > GitPanel.its.sha256 )

SIZE_BYTES="$(wc -c < "${ARCHIVE}" | tr -d '[:space:]')"
echo "==> Built ${ARCHIVE} (${SIZE_BYTES} bytes)"
echo "==> Checksum: ${OUT_DIR}/GitPanel.its.sha256"
