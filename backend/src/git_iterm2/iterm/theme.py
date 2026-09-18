import re
from typing import Any

from git_iterm2.models import Theme

DEFAULT_FONT = ("Menlo", 12.0)
_FONT = re.compile(r"^(?P<family>.+?)\s+(?P<size>\d+(?:\.\d+)?)$")


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


async def theme_from_session(session: Any) -> Theme:
    profile = await session.async_get_profile()
    family, size = parse_font(profile.normal_font)
    return Theme(
        background=color_hex(profile.background_color),
        foreground=color_hex(profile.foreground_color),
        selection=color_hex(profile.selection_color),
        ansi=[color_hex(getattr(profile, f"ansi_{index}_color")) for index in range(16)],
        font_family=family,
        font_size=size,
    )
