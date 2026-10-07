"""Gemma looks at each photo that passed the color test.

It names what the colored thing is and checks the photo was taken outside, not of a screen.
Code still measures the color; the model answers the questions pixels cannot.
"""
from __future__ import annotations

from dataclasses import dataclass

from llm import backend, generate, parallel_calls, parse_json

PROMPT = """You check photos for an outdoor walking game. The player was asked to photograph something {color}.
Look at the photo and answer with JSON only, no other text:
{{"subject": "<2 to 5 words naming the main {color} thing, or none>",
"outdoors": <true if the photo was taken outside, false if indoors>,
"screen": <true if this is a photo of a screen, monitor, phone or printed picture>}}"""


@dataclass(frozen=True)
class Observation:
    subject: str
    outdoors: bool
    screen: bool


def observe(image: bytes, color: str) -> Observation | None:
    """Ask Gemma about one photo. None means the model was unavailable or answered badly."""
    data = parse_json(generate(PROMPT.format(color=color), image=image, json_mode=True, max_tokens=80))
    if not data or not isinstance(data.get("outdoors"), bool):
        return None
    subject = str(data.get("subject") or "").strip().lower()[:48]
    if subject in ("", "none", "n/a"):
        subject = f"something {color}"
    return Observation(subject, data["outdoors"], bool(data.get("screen")))


def available() -> bool:
    return backend().kind != "none"


def workers() -> int:
    return parallel_calls()
