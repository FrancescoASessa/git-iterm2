import pytest

from git_iterm2.iterm.theme import (
    FALLBACK_DARK,
    FALLBACK_LIGHT,
    color_hex,
    parse_font,
    theme_from_session,
)
from git_iterm2.models import ThemePalette
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


def _ansi(**by_index: str) -> list[FakeColor]:
    """A 16-entry ANSI list, `#000000` everywhere but the given indices."""
    colors = [FakeColor.from_hex("#000000") for _ in range(16)]
    for index, value in by_index.items():
        colors[int(index.removeprefix("c"))] = FakeColor.from_hex(value)
    return colors


async def test_theme_carries_only_the_semantic_colours_and_the_mono_font() -> None:
    """The panel's surfaces are its own: background, foreground and selection
    do not travel, and neither do the 16 ANSI entries. Only the accent
    (ANSI 4), diff added (ANSI 2) and diff removed (ANSI 1) do."""
    session = FakeSession(
        profile=make_profile(
            background_color=FakeColor.from_hex("#101010"),
            foreground_color=FakeColor.from_hex("#eeeeee"),
            selection_color=FakeColor.from_hex("#224466"),
            ansi=_ansi(c1="#e06c75", c2="#98c379", c4="#61afef"),
            normal_font="MesloLGS NF 13",
        )
    )

    theme = await theme_from_session(session)

    assert theme.light.accent == "#61afef"
    assert theme.light.added == "#98c379"
    assert theme.light.removed == "#e06c75"
    assert theme.mono_family == "MesloLGS NF"
    assert theme.mono_size == 13.0
    dumped = theme.model_dump()
    assert set(dumped) == {"light", "dark", "mono_family", "mono_size"}
    assert set(dumped["light"]) == {"accent", "added", "removed"}


async def test_both_palettes_match_without_separate_light_and_dark_colours() -> None:
    session = FakeSession(
        profile=make_profile(
            ansi=_ansi(c1="#e06c75", c2="#98c379", c4="#61afef"),
            use_separate_colors_for_light_and_dark_mode=False,
            # Present but unused: a profile keeps stale variant keys after the
            # toggle is turned back off, and the terminal renders the legacy
            # colours, so the panel must too.
            ansi_light=_ansi(c1="#aa0000", c2="#00aa00", c4="#0000aa"),
        )
    )

    theme = await theme_from_session(session)

    assert theme.light == theme.dark
    assert theme.dark.accent == "#61afef"


async def test_separate_colours_are_read_per_appearance() -> None:
    """The defect this replaces: with the toggle on, the legacy getters return
    the *light* colours, so a dark terminal got a light palette."""
    session = FakeSession(
        profile=make_profile(
            ansi=_ansi(c1="#ffffff", c2="#ffffff", c4="#ffffff"),
            use_separate_colors_for_light_and_dark_mode=True,
            ansi_light=_ansi(c1="#cf222e", c2="#1a7f37", c4="#0a69da"),
            ansi_dark=_ansi(c1="#f85149", c2="#3fb950", c4="#4493f8"),
        )
    )

    theme = await theme_from_session(session)

    assert theme.light == ThemePalette(accent="#0a69da", added="#1a7f37", removed="#cf222e")
    assert theme.dark == ThemePalette(accent="#4493f8", added="#3fb950", removed="#f85149")


async def test_missing_variant_falls_back_to_the_legacy_colour() -> None:
    session = FakeSession(
        profile=make_profile(
            ansi=_ansi(c1="#e06c75", c2="#98c379", c4="#61afef"),
            use_separate_colors_for_light_and_dark_mode=True,
            ansi_light=_ansi(c1="#cf222e", c2="#1a7f37", c4="#0a69da"),
            # No dark variant at all: iTerm2's getters return None for a
            # missing key, and the legacy colour is the best we have.
            ansi_dark=None,
        )
    )

    theme = await theme_from_session(session)

    assert theme.light.accent == "#0a69da"
    assert theme.dark.accent == "#61afef"


async def test_falls_back_to_the_built_in_palette_when_the_profile_has_no_colour() -> None:
    # `ansi=None` is the fake's stand-in for a profile with no colour under
    # those keys, which is what iTerm2's getters report as `None`.
    session = FakeSession(profile=make_profile(ansi=None))

    theme = await theme_from_session(session)

    assert theme.light == FALLBACK_LIGHT
    assert theme.dark == FALLBACK_DARK
