"""Tests for the packaging pipeline (`packaging/build-archive.sh`).

Runs the real build script end to end into a temporary output directory and
inspects the produced archive. Calls it with `--skip-web-build`, so this
test never runs `npm ci` (which would wipe and reinstall `web/node_modules`
and rewrite `web/dist`) and never touches the network -- it reuses whatever
is already built at `web/dist`. Requires that prebuilt `web/dist` to exist;
skipped otherwise, with a pointer to build it first, rather than silently
paying for a full web build (or failing confusingly) on every otherwise
unrelated backend test run.

Does not require a running iTerm2. Does not mutate the working tree.

These assertions are written against iTerm2's own import requirements (see
`docs/ITERM2-FINDINGS.md`), not our prior assumptions about them -- an
earlier version of this file passed against an archive iTerm2 actually
rejected on a live install:

- `.its` requires a signature we cannot produce; the unsigned path is
  `.zip` (`iTermScriptImporter.m`'s `verifyAndUnwrapArchive:
  requireSignature:`, `smellsLikeSignedArchive:`).
- `install_requires` is split on `";"`, not `","`
  (`iTermSetupCfgParser.m`, `componentsSeparatedByString:@";"`).
- `python_requires` must start with `=` or iTerm2 silently discards it
  (`iTermSetupCfgParser.m`: `if (![expression hasPrefix:@"="]) { return; }`).
"""

import configparser
import hashlib
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "packaging" / "build-archive.sh"
WEB_DIST_INDEX = REPO_ROOT / "web" / "dist" / "index.html"

# iTerm2 versions this build has verified offer a Python interpreter for a
# full-environment script (verified 2026-09-18 against the app binary; see
# docs/ITERM2-FINDINGS.md). `python_requires` must name one of these.
ITERM2_OFFERED_PYTHON_VERSIONS = {"3.10", "3.11", "3.12", "3.13"}

REQUIRED = os.environ.get("GIT_ITERM2_REQUIRE_PACKAGING_TEST") == "1"
"""Set by the CI job that has just built the archive (and therefore
`web/dist`). Without it, a job that forgot to build the SPA -- which is how
this test came to never run in CI at all -- would go on skipping in
silence instead of failing."""

pytestmark = pytest.mark.skipif(
    not WEB_DIST_INDEX.exists() and not REQUIRED,
    reason="web/dist is not built; run `npm run build` in web/ first",
)


def _build(tmp_path: Path) -> tuple[Path, Path]:
    assert WEB_DIST_INDEX.exists(), (
        "GIT_ITERM2_REQUIRE_PACKAGING_TEST=1 but web/dist is missing: "
        "the job must build the web bundle (or the archive) first"
    )
    out_dir = tmp_path / "dist"

    subprocess.run(
        ["bash", str(BUILD_SCRIPT), str(out_dir), "--skip-web-build"],
        cwd=REPO_ROOT,
        check=True,
    )

    archive = out_dir / "GitPanel.zip"
    checksum_file = out_dir / "GitPanel.zip.sha256"
    assert archive.is_file(), f"{archive} was not created"
    assert checksum_file.is_file(), f"{checksum_file} was not created"
    return archive, checksum_file


def test_build_produces_an_unsigned_zip_not_a_dot_its(tmp_path: Path) -> None:
    # iTermScriptImporter.m requires anything imported with a `.its`
    # extension to pass `smellsLikeSignedArchive:` -- a plain zip fails that
    # check and iTerm2 refuses it ("This script archive is corrupt and
    # cannot be installed."). `.zip` is the extension
    # `reallyImportScriptFromURL` accepts for an unsigned, user-initiated
    # import, which is the only kind we can produce (no signing
    # certificate). The build must therefore never produce a `.its` file at
    # all, next to producing the right `.zip` one.
    archive, checksum_file = _build(tmp_path)

    assert archive.name == "GitPanel.zip"
    assert archive.suffix == ".zip"
    assert not (archive.parent / "GitPanel.its").exists()
    assert checksum_file.name == "GitPanel.zip.sha256"


def test_archive_layout_matches_what_iterm2_requires_for_a_full_environment_script(
    tmp_path: Path,
) -> None:
    # iTerm2's full-environment script layout requires an exact
    # `<name>/setup.cfg` and `<name>/<name>/<name>.py` inside the archive
    # (iTermSetupCfgParser.m / the importer's expectations for a
    # `[options] scripts=` entry) -- not merely "a setup.cfg somewhere" and
    # "a .py somewhere".
    archive, _ = _build(tmp_path)

    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        setup_cfg = zf.read("GitPanel/setup.cfg").decode()

    assert "GitPanel/setup.cfg" in names
    assert "GitPanel/GitPanel/GitPanel.py" in names
    assert "GitPanel/GitPanel/git_iterm2/panel.py" in names
    assert "GitPanel/GitPanel/git_iterm2/web/index.html" in names
    assert any(
        n.startswith("GitPanel/GitPanel/git_iterm2/web/assets/") and n.endswith(".js")
        for n in names
    ), "no bundled web JS asset found in the archive"

    assert not any("__pycache__" in n for n in names)
    assert not any(n.endswith(".pyc") for n in names)
    assert not any("/tests/" in n or n.endswith("/tests") for n in names)

    # Belt-and-braces: the setup.cfg pulled out of the layout check above is
    # exactly the one the dedicated setup.cfg tests below parse the iTerm2
    # way, so a layout regression and a setup.cfg regression can't mask
    # each other.
    assert setup_cfg.strip()


def _setup_cfg_options(tmp_path: Path) -> configparser.SectionProxy:
    archive, _ = _build(tmp_path)
    with zipfile.ZipFile(archive) as zf:
        setup_cfg = zf.read("GitPanel/setup.cfg").decode()
    config = configparser.ConfigParser()
    config.read_string(setup_cfg)
    return config["options"]


def test_install_requires_parses_the_way_iterm2_parses_it(tmp_path: Path) -> None:
    # iTermSetupCfgParser.m joins the accumulated `install_requires` parts
    # and splits the result on ";" (`componentsSeparatedByString:@";"`), not
    # ",". A comma-separated value is read back as a single requirement --
    # this must fail here if setup.cfg ever regresses to commas.
    options = _setup_cfg_options(tmp_path)
    raw = options["install_requires"]

    requirements = [part.strip() for part in raw.split(";") if part.strip()]

    assert len(requirements) == 3
    assert set(requirements) == {"iterm2", "aiohttp", "pydantic"}
    # A comma-separated value must fail this test: splitting it on ";"
    # yields exactly one (wrong) requirement.
    assert len(raw.split(",")) == 1 or "," not in raw


def test_python_requires_is_an_exact_pin_iterm2_can_read(tmp_path: Path) -> None:
    # iTermSetupCfgParser.m discards `python_requires` silently unless it
    # starts with "=" (`if (![expression hasPrefix:@"="]) { return; }`) --
    # a floor like ">=3.11" is accepted by configparser but thrown away by
    # iTerm2 itself, so the declared floor never reaches it.
    options = _setup_cfg_options(tmp_path)
    raw = options["python_requires"].strip()

    assert raw.startswith("="), (
        f"python_requires={raw!r} does not start with '=': iTerm2's "
        "iTermSetupCfgParser.m silently discards it"
    )
    version = raw[1:].strip()
    assert version in ITERM2_OFFERED_PYTHON_VERSIONS, (
        f"python_requires pins {version!r}, which this iTerm2 build does not "
        f"offer (offers: {sorted(ITERM2_OFFERED_PYTHON_VERSIONS)})"
    )


def test_checksum_matches_archive_content(tmp_path: Path) -> None:
    archive, checksum_file = _build(tmp_path)

    checksum_line = checksum_file.read_text().split()
    assert checksum_line, f"{checksum_file} is empty"
    expected_sha = checksum_line[0]
    actual_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert expected_sha == actual_sha
