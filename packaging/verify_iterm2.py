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


def color_hex(color: Any) -> str:
    """Render an iterm2.Color as #rrggbb ourselves.

    iterm2.Color.hex (2.23) formats .red/.green/.blue with %02x, but
    Color.from_dict stores them as floats -- format() rejects a float with
    an 'x' code, so .hex raises ValueError for every profile color. Round
    and clamp instead of using the library's own .hex property.
    """

    def channel(value: float) -> int:
        return max(0, min(255, round(value)))

    return f"#{channel(color.red):02x}{channel(color.green):02x}{channel(color.blue):02x}"


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
    # Each probe below is wrapped in its own try/except and records
    # {"error": repr(exc)} under its own key on failure, so one bad call
    # (e.g. an unverified variable/attribute name) can't cost the user the
    # whole run. The JSON is printed in `finally` so partial findings always
    # reach them even if something above raises unexpectedly.
    runner: web.AppRunner | None = None
    try:
        app = await iterm2.async_get_app(connection)

        # Verified against a real iTerm2 (3.7.1): this always returns null,
        # no exception -- the API cannot report the running iTerm2's
        # version. Kept (rather than dropped) only so a future run can
        # notice if that ever changes; do NOT use this for version
        # detection. Read CFBundleShortVersionString from
        # /Applications/iTerm.app/Contents/Info.plist instead (see
        # docs/ITERM2-FINDINGS.md, question 4).
        try:
            FINDINGS["iterm2_version"] = await iterm2.async_get_variable(
                connection, "iterm2.version"
            )
        except Exception as exc:  # noqa: BLE001 -- record and keep going
            FINDINGS["iterm2_version"] = {"error": repr(exc)}

        runner, port = await probe_server()
        url = f"http://127.0.0.1:{port}/?t=verification-token"
        try:
            await iterm2.tool.async_register_web_view_tool(
                connection, "git-iterm2 verify", IDENTIFIER, True, url
            )
            FINDINGS["registered_url"] = url
        except Exception as exc:  # noqa: BLE001
            FINDINGS["registered_url"] = {"url": url, "error": repr(exc)}

        session = (
            app.current_terminal_window.current_tab.current_session
            if app.current_terminal_window
            else None
        )

        if session is not None:
            try:
                profile = await session.async_get_profile()
                FINDINGS["profile"] = {
                    "name": profile.name,
                    "background": color_hex(profile.background_color),
                    "foreground": color_hex(profile.foreground_color),
                    "selection": color_hex(profile.selection_color),
                    "ansi_0": color_hex(profile.ansi_0_color),
                    "ansi_15": color_hex(profile.ansi_15_color),
                    "normal_font": profile.normal_font,
                    # Profiles default to CALIBRATED, not sRGB -- worth
                    # recording since iterm2.Color.hex assumes sRGB.
                    "background_color_space": profile.background_color.color_space.name,
                }
            except Exception as exc:  # noqa: BLE001
                FINDINGS["profile"] = {"error": repr(exc)}

            try:
                FINDINGS["session_path"] = await session.async_get_variable("path")
            except Exception as exc:  # noqa: BLE001
                FINDINGS["session_path"] = {"error": repr(exc)}

            FINDINGS["session_id"] = session.session_id
        else:
            FINDINGS["profile"] = {"error": "no current session"}
            FINDINGS["session_path"] = {"error": "no current session"}
            FINDINGS["session_id"] = None

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

            try:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(watch(), timeout=15)
                FINDINGS["profile_name_variable_fires"] = profile_changed
            except Exception as exc:  # noqa: BLE001
                FINDINGS["profile_name_variable_fires"] = {"error": repr(exc)}
        else:
            FINDINGS["profile_name_variable_fires"] = False
    finally:
        print(json.dumps(FINDINGS, indent=2, sort_keys=True, default=repr))
        print()
        print("This script is about to exit on its own (run_until_complete returns")
        print("as soon as main() does -- no Ctrl-C needed). To answer the")
        print("persistence question:")
        print("  1. note whether the 'git-iterm2 verify' toolbelt tool disappears")
        print("     or stays once this process has exited,")
        print("  2. run the script again and note whether iTerm2 shows the panel")
        print("     again automatically, before this script's next registration call.")
        if runner is not None:
            await runner.cleanup()


iterm2.run_until_complete(main)
