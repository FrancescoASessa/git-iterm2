"""Answer the spec's open iTerm2 questions against a live iTerm2.

Run it from the repo root with iTerm2 open:

    cd backend && uv run --with iterm2 python ../packaging/verify_iterm2.py

Approve the "control iTerm2" prompt if macOS shows one. The script only reads
state and registers a throwaway toolbelt tool; it changes no settings.

`iterm2.run_until_complete` returns -- and this process exits -- as soon as
`main()` returns. There is nothing to Ctrl-C: the script prints its findings
and then quits on its own. To answer the "does the tool persist" question,
check the toolbelt *after* the script has printed its JSON and exited, then
run the script again and see whether iTerm2 reopens the registered URL
without a fresh registration call.
"""

import asyncio
import contextlib
import json
import socket
from typing import Any

import iterm2
from aiohttp import web

IDENTIFIER = "com.github.git-iterm2.verify"
FINDINGS: dict[str, Any] = {}


async def probe_server() -> tuple[web.AppRunner, int]:
    """A tiny server that records what headers the webview sends."""

    async def index(request: web.Request) -> web.Response:
        FINDINGS["webview_headers"] = {
            "host": request.headers.get("Host"),
            "origin": request.headers.get("Origin"),
            "user_agent": request.headers.get("User-Agent"),
            "sec_fetch_site": request.headers.get("Sec-Fetch-Site"),
        }
        FINDINGS["webview_query"] = dict(request.query)
        return web.Response(
            text="git-iterm2 verification: headers captured", content_type="text/plain"
        )

    app = web.Application()
    app.router.add_get("/", index)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    await web.SockSite(runner, sock).start()
    return runner, int(sock.getsockname()[1])


async def main(connection: iterm2.Connection) -> None:
    app = await iterm2.async_get_app(connection)
    FINDINGS["iterm2_version"] = await iterm2.async_get_variable(connection, "iterm2.version")

    runner, port = await probe_server()
    url = f"http://127.0.0.1:{port}/?t=verification-token"
    await iterm2.tool.async_register_web_view_tool(
        connection, "git-iterm2 verify", IDENTIFIER, True, url
    )
    FINDINGS["registered_url"] = url

    session = (
        app.current_terminal_window.current_tab.current_session
        if app.current_terminal_window
        else None
    )
    if session is not None:
        profile = await session.async_get_profile()
        FINDINGS["profile"] = {
            "name": profile.name,
            "background": profile.background_color.hex,
            "foreground": profile.foreground_color.hex,
            "selection": profile.selection_color.hex,
            "ansi_0": profile.ansi_0_color.hex,
            "ansi_15": profile.ansi_15_color.hex,
            "normal_font": profile.normal_font,
        }
        FINDINGS["session_path"] = await session.async_get_variable("path")
        FINDINGS["session_id"] = session.session_id

    # Does a profile change notify us? Watch for 15s while the user switches profile.
    print("Open View > Toolbelt > git-iterm2 verify now, then switch the session's")
    print("profile (or change its colors) within 15 seconds...")
    profile_changed = False
    if session is not None:

        async def watch() -> None:
            nonlocal profile_changed
            async with iterm2.VariableMonitor(
                connection, iterm2.VariableScopes.SESSION, "profileName", session.session_id
            ) as monitor:
                await monitor.async_get()
                profile_changed = True

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(watch(), timeout=15)
    FINDINGS["profile_name_variable_fires"] = profile_changed

    print(json.dumps(FINDINGS, indent=2, sort_keys=True))
    print()
    print("This script is about to exit on its own (run_until_complete returns")
    print("as soon as main() does -- no Ctrl-C needed). To answer the")
    print("persistence question:")
    print("  1. note whether the 'git-iterm2 verify' toolbelt tool disappears")
    print("     or stays once this process has exited,")
    print("  2. run the script again and note whether iTerm2 shows the panel")
    print("     again automatically, before this script's next registration call.")
    await runner.cleanup()


iterm2.run_until_complete(main)
