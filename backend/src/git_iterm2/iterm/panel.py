from typing import Any

PANEL_TITLE = "Git"
PANEL_IDENTIFIER = "com.github.git-iterm2.panel"


async def register_panel(connection: Any, url: str) -> None:
    import iterm2

    await iterm2.tool.async_register_web_view_tool(
        connection, PANEL_TITLE, PANEL_IDENTIFIER, True, url
    )
