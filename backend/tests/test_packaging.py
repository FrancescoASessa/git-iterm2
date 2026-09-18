"""Tests for the `.its` packaging pipeline (`packaging/build-its.sh`).

Runs the real build script end to end into a temporary output directory and
inspects the produced archive. Calls it with `--skip-web-build`, so this
test never runs `npm ci` (which would wipe and reinstall `web/node_modules`
and rewrite `web/dist`) and never touches the network -- it reuses whatever
is already built at `web/dist`. Requires that prebuilt `web/dist` to exist;
skipped otherwise, with a pointer to build it first, rather than silently
paying for a full web build (or failing confusingly) on every otherwise
unrelated backend test run.

Does not require a running iTerm2. Does not mutate the working tree.
"""

import configparser
import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "packaging" / "build-its.sh"
WEB_DIST_INDEX = REPO_ROOT / "web" / "dist" / "index.html"

pytestmark = pytest.mark.skipif(
    not WEB_DIST_INDEX.exists(),
    reason="web/dist is not built; run `npm run build` in web/ first",
)


def test_build_its_produces_expected_archive(tmp_path: Path) -> None:
    out_dir = tmp_path / "dist"

    subprocess.run(
        ["bash", str(BUILD_SCRIPT), str(out_dir), "--skip-web-build"],
        cwd=REPO_ROOT,
        check=True,
    )

    archive = out_dir / "GitPanel.its"
    checksum_file = out_dir / "GitPanel.its.sha256"
    assert archive.is_file(), f"{archive} was not created"
    assert checksum_file.is_file(), f"{checksum_file} was not created"

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

    config = configparser.ConfigParser()
    config.read_string(setup_cfg)
    assert config["options"]["install_requires"] == "iterm2,aiohttp,pydantic"

    # The checksum recorded next to the archive must match the archive's
    # own content (the archive was just built fresh, so this also exercises
    # the exact verification install.sh performs).
    checksum_line = checksum_file.read_text().split()
    assert checksum_line, f"{checksum_file} is empty"
    expected_sha = checksum_line[0]
    actual_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert expected_sha == actual_sha
