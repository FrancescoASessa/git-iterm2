import asyncio
import sys
from pathlib import Path

import aiohttp

from git_iterm2.standalone import parse_args


def test_parse_args(tmp_path: Path) -> None:
    args = parse_args(["--repo", str(tmp_path), "--token", "t", "--port", "8123"])
    assert args.repo == tmp_path
    assert args.token == "t"
    assert args.port == 8123
    assert args.static is None
    assert args.poll_interval == 1.0


async def test_standalone_serves_api(repo: Path) -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "git_iterm2.standalone",
        "--repo",
        str(repo),
        "--token",
        "secret",
        stdout=asyncio.subprocess.PIPE,
    )
    try:
        assert proc.stdout is not None
        line = (await asyncio.wait_for(proc.stdout.readline(), 10)).decode().strip()
        assert line.startswith("git-iterm2 standalone: http://127.0.0.1:")
        base = line.split(": ", 1)[1].split("/?t=")[0]
        async with aiohttp.ClientSession() as session:  # noqa: SIM117
            async with session.get(f"{base}/api/branches", headers={"X-Token": "secret"}) as resp:
                assert resp.status == 200
                body = await resp.json()
        assert [branch["name"] for branch in body["local"]] == ["main"]
    finally:
        proc.terminate()
        await proc.wait()
