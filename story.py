from __future__ import annotations

import json
from typing import Sequence

from llm import backend, generate
from verify import PhotoResult

SAFETY_LINE = "Stay on public paths, keep your head up at crossings, and pocket the phone between photos."


def _clean(text: str | None) -> str | None:
    """Reject empty, rambling or markdown-heavy output so the template takes over."""
    if not text:
        return None
    text = text.strip().strip('"').replace("**", "")
    if not 40 <= len(text) <= 900 or text.count("#") > 2:
        return None
    return text


def quest_card(color: str, minutes: int, km: float, description: str = "") -> tuple[str, str]:
    stats = json.dumps({"color": color, "minutes": minutes, "distance_km": km, "photos_needed": 5, "typical_finds": description})
    prompt = (
        "You write quest cards for an outdoor walking game. Using only these facts, write 3 short friendly sentences "
        "inviting the player to find the color in 5 different places outside, with one concrete idea of where to look, "
        "then one safety reminder sentence. Never suggest trespassing, climbing, touching animals, or eating plants. "
        "Plain text, no lists, no headings, no emoji.\n"
        f"FACTS: {stats}"
    )
    text = _clean(generate(prompt))
    if text:
        return text, backend().label
    template = (
        f"Today the street is a search field for {color}. "
        f"Walk about {km:.1f} km over {minutes} minutes and notice where {color} hides in plain sight. "
        f"Five photos, five different spots, then home. {SAFETY_LINE}"
    )
    return template, "template"


def walk_story(color: str, minutes: int, results: Sequence[PhotoResult]) -> tuple[str, str]:
    accepted = [r for r in results if r.accepted]
    rejected = [r for r in results if not r.accepted]
    stats = {
        "color": color,
        "minutes_planned": minutes,
        "photos_counted": len(accepted),
        "photos_needed": 5,
        "won": len(accepted) >= 5,
        "things_found": [r.subject for r in accepted if r.subject],
        "photos_rejected": len(rejected),
        "rejection_reasons": [r.reason for r in rejected][:6],
    }
    prompt = (
        "Write a 4 sentence upbeat recap of a walk for a color-hunting game, in second person. "
        "Mention the things_found by name if there are any; if the list is empty, name no objects at all. "
        "Use only facts in the JSON. "
        "Do not invent places, objects, weather, or people. Plain text only, no emoji.\n"
        f"JSON: {json.dumps(stats)}"
    )
    text = _clean(generate(prompt))
    if text:
        return text, backend().label
    count, missed = len(accepted), len(rejected)
    if count >= 5:
        template = (
            f"The {minutes}-minute loop closed with five {color} signals. "
            f"Each one sat in a different spot along the way. "
            f"{missed} frame{'s' if missed != 1 else ''} did not count, which is part of the hunt. "
            f"The palette below is the walk, reduced to color."
        )
    else:
        template = (
            f"The loop looked for {color} and counted {count} of five. "
            f"{missed} frame{'s' if missed != 1 else ''} did not make the cut; the reasons are listed. "
            f"{5 - count} more distinct spot{'s' if 5 - count != 1 else ''} will close it. "
            f"The color is still out there."
        )
    return template, "template"
