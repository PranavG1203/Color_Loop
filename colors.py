from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ColorTarget:
    name: str
    hue_ranges: tuple[tuple[int, int], ...]  # OpenCV hue scale, 0-179
    swatch: tuple[int, int, int]
    description: str

    @property
    def hex(self) -> str:
        return "#{:02X}{:02X}{:02X}".format(*self.swatch)

    @property
    def degrees(self) -> tuple[tuple[int, int], ...]:
        return tuple((low * 2, high * 2 + 2) for low, high in self.hue_ranges)


COLOR_TARGETS: tuple[ColorTarget, ...] = (
    ColorTarget("red", ((0, 12), (170, 179)), (205, 54, 54), "warm signals, doors, leaves"),
    ColorTarget("orange", ((13, 28),), (218, 116, 42), "rust, brick, late light"),
    ColorTarget("yellow", ((29, 42),), (218, 180, 48), "markings, flowers, sunlit walls"),
    ColorTarget("green", ((43, 85),), (72, 143, 82), "leaves, moss, painted gates"),
    ColorTarget("blue", ((86, 130),), (59, 112, 174), "signs, windows, sky"),
    ColorTarget("purple", ((131, 169),), (123, 83, 151), "murals, fabric, twilight"),
)


def color_of_day(day: date | None = None) -> ColorTarget:
    """Same color for everyone on the same date, so a run club shares a quest."""
    current_day = day or date.today()
    return COLOR_TARGETS[current_day.toordinal() % len(COLOR_TARGETS)]


def color_by_name(name: str) -> ColorTarget:
    return next(target for target in COLOR_TARGETS if target.name == name)
