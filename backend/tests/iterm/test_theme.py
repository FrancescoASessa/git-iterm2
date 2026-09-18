import pytest

from git_iterm2.iterm.theme import color_hex, parse_font, theme_from_session
from tests.iterm.fakes import FakeColor, FakeSession, make_profile


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("MesloLGS NF 13", ("MesloLGS NF", 13.0)),
        ("Menlo Regular 12", ("Menlo Regular", 12.0)),
        ("SF Mono Medium 11.5", ("SF Mono Medium", 11.5)),
        ("Monaco", ("Monaco", 12.0)),
        ("", ("Menlo", 12.0)),
    ],
)
def test_parse_font(value: str, expected: tuple[str, float]) -> None:
    assert parse_font(value) == expected


def test_color_hex_rounds_fractional_channels() -> None:
    # Never go through `.hex` (see FakeColor / color_hex docstrings for the
    # upstream bug this guards against) — color_hex must compute this itself.
    color = FakeColor(red=27.6, green=0.4, blue=254.9)

    assert color_hex(color) == "#1c00ff"


def test_color_hex_clamps_out_of_range_channels() -> None:
    color = FakeColor(red=-10.0, green=300.0, blue=128.0)

    assert color_hex(color) == "#00ff80"


async def test_theme_from_session() -> None:
    session = FakeSession(
        profile=make_profile(
            background_color=FakeColor.from_hex("#101010"),
            foreground_color=FakeColor.from_hex("#eeeeee"),
            selection_color=FakeColor.from_hex("#224466"),
            normal_font="MesloLGS NF 13",
        )
    )

    theme = await theme_from_session(session)

    assert theme.background == "#101010"
    assert theme.foreground == "#eeeeee"
    assert theme.selection == "#224466"
    assert len(theme.ansi) == 16
    assert theme.ansi[0] == "#000000"
    assert theme.ansi[15] == "#0f0f0f"
    assert theme.font_family == "MesloLGS NF"
    assert theme.font_size == 13.0
