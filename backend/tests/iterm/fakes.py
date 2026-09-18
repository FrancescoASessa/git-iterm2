import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeColor:
    """Mirrors the real `iterm2.Color` shape, bug included.

    Channels are stored as floats (0-255), matching `Color.from_dict`. The
    real library's `.hex` property is broken on iTerm2 2.23/2.24 (it
    `%02x`-formats a float and raises `ValueError`); production code must
    never touch `.hex` and must compute the string itself instead
    (`git_iterm2.iterm.theme.color_hex`). This fake reproduces that crash
    so any code path that regresses to `.hex` fails loudly here too.
    """

    red: float
    green: float
    blue: float

    @property
    def hex(self) -> str:
        raise ValueError("Unknown format code 'x' for object of type 'float'")

    @classmethod
    def from_hex(cls, value: str) -> "FakeColor":
        value = value.lstrip("#")
        return cls(
            red=float(int(value[0:2], 16)),
            green=float(int(value[2:4], 16)),
            blue=float(int(value[4:6], 16)),
        )


@dataclass
class FakeProfile:
    background_color: FakeColor
    foreground_color: FakeColor
    selection_color: FakeColor
    ansi: list[FakeColor]
    normal_font: str
    name: str = "Default"

    def __getattr__(self, item: str) -> Any:
        if item.startswith("ansi_") and item.endswith("_color"):
            return self.ansi[int(item.removeprefix("ansi_").removesuffix("_color"))]
        raise AttributeError(item)


def make_profile(**overrides: Any) -> FakeProfile:
    defaults: dict[str, Any] = {
        "background_color": FakeColor.from_hex("#1c1c1c"),
        "foreground_color": FakeColor.from_hex("#d8d8d8"),
        "selection_color": FakeColor.from_hex("#33414e"),
        "ansi": [FakeColor.from_hex(f"#{index:02x}{index:02x}{index:02x}") for index in range(16)],
        "normal_font": "MesloLGS NF 13",
    }
    defaults.update(overrides)
    return FakeProfile(**defaults)


@dataclass
class FakeSession:
    session_id: str = "session-1"
    profile: FakeProfile = field(default_factory=make_profile)
    variables: dict[str, Any] = field(default_factory=dict)
    sent: list[str] = field(default_factory=list)
    splits: list[dict[str, Any]] = field(default_factory=list)
    variable_error: Exception | None = None
    """Set to make `async_get_variable` raise, for exercising defensive
    `try/except` paths around a real iTerm2 RPC failing (e.g. the session
    having gone away between the event firing and the read)."""
    variable_block: "asyncio.Event | None" = None
    """Set to make `async_get_variable` await this event forever (it is
    never set), for exercising bounded-timeout paths around a real iTerm2
    RPC that stalls (e.g. iTerm2 is busy or modal, or the session is
    closing mid-request)."""

    async def async_get_profile(self) -> FakeProfile:
        return self.profile

    async def async_get_variable(self, name: str) -> Any:
        if self.variable_block is not None:
            await self.variable_block.wait()
        if self.variable_error is not None:
            raise self.variable_error
        return self.variables.get(name)

    async def async_split_pane(self, **kwargs: Any) -> "FakeSession":
        self.splits.append(kwargs)
        # The real iTerm2 API returns a brand-new session for the split. The
        # fake mirrors that (production code must keep sending to the newly
        # created session), but shares the parent's `sent` list object so
        # tests can assert on the session they hold a reference to.
        return FakeSession(session_id=f"{self.session_id}-split", sent=self.sent)

    async def async_send_text(self, text: str, suppress_broadcast: bool = False) -> None:
        self.sent.append(text)


@dataclass
class FakeTab:
    current_session: FakeSession | None


@dataclass
class FakeWindow:
    current_tab: FakeTab | None


@dataclass
class FakeApp:
    current_terminal_window: FakeWindow | None

    def get_session_by_id(self, session_id: str) -> FakeSession | None:
        window = self.current_terminal_window
        session = window.current_tab.current_session if window and window.current_tab else None
        return session if session is not None and session.session_id == session_id else None


def app_with(session: FakeSession | None) -> FakeApp:
    return FakeApp(FakeWindow(FakeTab(session)) if session is not None else None)
