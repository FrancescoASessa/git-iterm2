import re
from typing import Any, Literal

from git_iterm2.models import Theme, ThemePalette

DEFAULT_FONT = ("Menlo", 12.0)
_FONT = re.compile(r"^(?P<family>.+?)\s+(?P<size>\d+(?:\.\d+)?)$")

Appearance = Literal["light", "dark"]

# The only profile colours the panel still reads. Everything else it draws is
# a neutral system surface resolved in CSS, so shipping all 16 ANSI entries
# (twice, once per appearance) would be data the UI never looks at.
_ACCENT_ANSI = 4  # blue   -> branch and ref labels
_ADDED_ANSI = 2  # green  -> diff added
_REMOVED_ANSI = 1  # red    -> diff removed

# Used when the profile has no colour under the key at all (iTerm2 returns
# `None` for a missing key rather than raising). These match the SPA's
# FALLBACK_THEME so a themeless panel looks the same as a themed one.
FALLBACK_LIGHT = ThemePalette(accent="#0a69da", added="#1a7f37", removed="#cf222e")
FALLBACK_DARK = ThemePalette(accent="#4493f8", added="#3fb950", removed="#f85149")


def parse_font(normal_font: str) -> tuple[str, float]:
    """iTerm2 reports a font as "<family and style> <size>"."""
    value = normal_font.strip()
    if not value:
        return DEFAULT_FONT
    match = _FONT.match(value)
    if match is None:
        return value, DEFAULT_FONT[1]
    return match.group("family"), float(match.group("size"))


def color_hex(color: Any) -> str:
    """Compute a colour's `#rrggbb` string ourselves.

    Do NOT use `iterm2.Color.hex` — in iTerm2 2.23/2.24,
    `Color.from_dict` stores each channel as a float
    (`float(input_dict["Red Component"]) * 255`), but `Color.hex` formats
    them with `%02x`, which raises `ValueError: Unknown format code 'x'
    for object of type 'float'` for every profile colour. This is an
    upstream bug (confirmed against a real iTerm2 3.7.1 session), not a
    style choice — never "simplify" this back to `color.hex`.
    """

    def channel(value: float) -> int:
        return max(0, min(255, round(float(value))))

    return f"#{channel(color.red):02x}{channel(color.green):02x}{channel(color.blue):02x}"


def _read_color(profile: Any, base: str, appearance: Appearance, separate: bool) -> Any:
    """Read one profile colour for `appearance`.

    A profile with "Use Separate Colors for Light and Dark Mode" enabled
    does NOT keep the legacy key in step: `profile.background_color` (and
    every other legacy colour getter) returns the *light* colour while the
    terminal renders dark. That is exactly how the panel came out white on
    a dark terminal, so read the `_light` / `_dark` variant whenever the
    profile says it uses them, and only fall back to the legacy key when
    the variant is absent.
    """
    if separate:
        variant = getattr(profile, f"{base}_{appearance}", None)
        if variant is not None:
            return variant
    return getattr(profile, base, None)


def _palette(profile: Any, appearance: Appearance, separate: bool) -> ThemePalette:
    fallback = FALLBACK_LIGHT if appearance == "light" else FALLBACK_DARK

    def ansi(index: int, default: str) -> str:
        color = _read_color(profile, f"ansi_{index}_color", appearance, separate)
        return default if color is None else color_hex(color)

    return ThemePalette(
        accent=ansi(_ACCENT_ANSI, fallback.accent),
        added=ansi(_ADDED_ANSI, fallback.added),
        removed=ansi(_REMOVED_ANSI, fallback.removed),
    )


async def theme_from_session(session: Any) -> Theme:
    profile = await session.async_get_profile()
    family, size = parse_font(profile.normal_font)
    separate = bool(getattr(profile, "use_separate_colors_for_light_and_dark_mode", None) or False)
    return Theme(
        light=_palette(profile, "light", separate),
        dark=_palette(profile, "dark", separate),
        mono_family=family,
        mono_size=size,
    )
