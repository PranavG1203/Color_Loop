from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from math import asin, cos, isfinite, radians, sin, sqrt
from pathlib import Path
from typing import Any, BinaryIO, Callable, Sequence

import cv2
import numpy as np
from PIL import Image

from colors import ColorTarget

# All judge thresholds live here so tuning stays in one place.
MIN_FRACTION = 0.10      # share of pixels that must match the target hue
MIN_SATURATION = 90      # ~0.35 on a 0-255 scale
VALUE_RANGE = (50, 245)  # ~0.2 to ~0.95
SPREAD_METERS = 150      # counted photos must be this far apart
ROUTE_METERS = 150       # max distance from the planned loop
DEDUPE_SECONDS = 20      # photos closer in time are treated as duplicates
MAX_SIDE = 900           # downscale before analysis; color share is scale-free

LatLon = tuple[float, float]
# (photo bytes, color name) -> object with .subject, .outdoors, .screen, or None if unavailable
Observer = Callable[[bytes, str], Any]


@dataclass
class PhotoResult:
    name: str
    accepted: bool
    score: float
    reason: str
    color: tuple[int, int, int] | None = None
    taken_at: datetime | None = None
    location: LatLon | None = None
    subject: str | None = None  # what Gemma says the colored thing is
    ai_checked: bool = False


@dataclass
class WalkSummary:
    accepted: int
    won: bool
    has_gps: bool
    span_minutes: float | None
    within_time: bool
    ai_checked: int = 0


def _hue_mask(hsv: np.ndarray, target: ColorTarget) -> np.ndarray:
    hue = hsv[:, :, 0]
    mask = np.zeros(hue.shape, dtype=np.uint8)
    for low, high in target.hue_ranges:
        mask |= cv2.inRange(hue, low, high)
    saturation = hsv[:, :, 1] >= MIN_SATURATION
    value = (hsv[:, :, 2] >= VALUE_RANGE[0]) & (hsv[:, :, 2] <= VALUE_RANGE[1])
    return (mask > 0) & saturation & value


def _rational(value) -> float:
    return float(value[0]) / float(value[1]) if isinstance(value, tuple) else float(value)


def read_exif(image: Image.Image) -> tuple[datetime | None, LatLon | None]:
    exif = image.getexif()
    taken_at = None
    raw_time = exif.get_ifd(0x8769).get(36867) or exif.get(306)
    if raw_time:
        try:
            taken_at = datetime.strptime(str(raw_time).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            taken_at = None
    location = None
    gps = exif.get_ifd(0x8825)
    if gps.get(2) and gps.get(4):
        try:
            lat = sum(_rational(part) / 60**i for i, part in enumerate(gps[2]))
            lon = sum(_rational(part) / 60**i for i, part in enumerate(gps[4]))
            lat = -lat if gps.get(1) == "S" else lat
            lon = -lon if gps.get(3) == "W" else lon
            # Phones write 0/0 when they had no fix; newer Pillow turns that into nan, not an error.
            if _valid_location(lat, lon):
                location = (lat, lon)
        except (TypeError, ValueError, ZeroDivisionError):
            location = None
    return taken_at, location


def _valid_location(lat: float, lon: float) -> bool:
    return isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180 and (lat, lon) != (0.0, 0.0)


def inspect_image(image: Image.Image, target: ColorTarget) -> tuple[float, tuple[int, int, int]]:
    rgb_image = image.convert("RGB")
    rgb_image.thumbnail((MAX_SIDE, MAX_SIDE))
    rgb = np.asarray(rgb_image)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = _hue_mask(hsv, target)
    pixels = rgb[mask]
    color = tuple(np.mean(pixels, axis=0).astype(int).tolist()) if len(pixels) else target.swatch
    return float(mask.mean()), color


def evaluate_photo(file: str | Path | BinaryIO, target: ColorTarget, minimum_score: float = MIN_FRACTION) -> PhotoResult:
    """Color test plus EXIF read for a single photo. Location rules are applied in judge_walk."""
    name = str(getattr(file, "name", file if isinstance(file, (str, Path)) else "photo"))
    try:
        with Image.open(file) as image:
            taken_at, location = read_exif(image)
            score, color = inspect_image(image, target)
    except (OSError, ValueError) as error:
        return PhotoResult(name, False, 0.0, f"could not read image ({error})")
    if score < minimum_score:
        reason = f"too little {target.name}: {score:.0%}, need {minimum_score:.0%}"
        return PhotoResult(name, False, score, reason, color, taken_at, location)
    return PhotoResult(name, True, score, f"{score:.0%} {target.name}", color, taken_at, location)


def haversine_meters(first: LatLon, second: LatLon) -> float:
    earth_radius = 6_371_000
    lat_one, lon_one = map(radians, first)
    lat_two, lon_two = map(radians, second)
    delta_lat = lat_two - lat_one
    delta_lon = lon_two - lon_one
    value = sin(delta_lat / 2) ** 2 + cos(lat_one) * cos(lat_two) * sin(delta_lon / 2) ** 2
    return 2 * earth_radius * asin(sqrt(value))


def distance_to_path(point: LatLon, path: Sequence[LatLon]) -> float:
    """Shortest distance in meters from a point to a polyline (local flat projection)."""
    if not path:
        return float("inf")
    meters_per_lat = 111_320
    meters_per_lon = 111_320 * cos(radians(point[0]))

    def project(p: LatLon) -> tuple[float, float]:
        return ((p[1] - point[1]) * meters_per_lon, (p[0] - point[0]) * meters_per_lat)

    best = float("inf")
    projected = [project(p) for p in path]
    for (ax, ay), (bx, by) in zip(projected, projected[1:] or projected):
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length))
        best = min(best, sqrt((ax + t * dx) ** 2 + (ay + t * dy) ** 2))
    return best


def _apply_observations(
    results: list[PhotoResult], photos: Sequence[tuple[str, bytes]], target: ColorTarget, observe: Observer, workers: int
) -> None:
    """Ask the vision model about every photo that passed the color test, in parallel."""
    pending = [(result, data) for result, (_, data) in zip(results, photos) if result.accepted]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        answers = list(pool.map(lambda item: observe(item[1], target.name), pending))
    for (result, _), seen in zip(pending, answers):
        if seen is None:
            continue
        result.ai_checked, result.subject = True, seen.subject
        if seen.screen:
            result.accepted, result.reason = False, f"{seen.subject} looks like a screen or print, not the real world"
        elif not seen.outdoors:
            result.accepted, result.reason = False, f"{seen.subject} looks indoors; this game is played outside"
        else:
            result.reason = f"{seen.subject} · {result.score:.0%} {target.name} · outdoors"


def judge_walk(
    photos: Sequence[tuple[str, bytes]],
    target: ColorTarget,
    route: Sequence[LatLon] | None = None,
    observe: Observer | None = None,
    workers: int = 4,
) -> list[PhotoResult]:
    """Run every rule from the design doc and return results in walk order.

    Order: pixel color test (code) -> outdoor / not-a-screen check (Gemma, when connected)
    -> on-route, duplicate and spread rules (code).
    """
    results = []
    for name, data in photos:
        buffer = BytesIO(data)
        buffer.name = name
        results.append(evaluate_photo(buffer, target))
    if observe:
        _apply_observations(results, photos, target, observe, workers)
    results.sort(key=lambda r: (r.taken_at is None, r.taken_at or datetime.min))

    counted: list[PhotoResult] = []
    for result in results:
        if not result.accepted:
            continue
        reason = None
        if route and result.location:
            off_route = distance_to_path(result.location, route)
            if isfinite(off_route) and off_route > ROUTE_METERS:
                reason = f"{off_route:.0f} m off the planned loop"
        if reason is None and result.taken_at:
            for previous in counted:
                if previous.taken_at and abs((result.taken_at - previous.taken_at).total_seconds()) < DEDUPE_SECONDS:
                    reason = f"duplicate of {previous.name}, under {DEDUPE_SECONDS} s apart"
                    break
        if reason is None and result.location:
            for previous in counted:
                if previous.location:
                    gap = haversine_meters(result.location, previous.location)
                    if gap < SPREAD_METERS:
                        reason = f"only {gap:.0f} m from {previous.name}, need {SPREAD_METERS} m"
                        break
        if reason:
            result.accepted, result.reason = False, reason
        else:
            counted.append(result)
    return results


def summarize(results: Sequence[PhotoResult], minutes: int) -> WalkSummary:
    counted = [r for r in results if r.accepted][:5]
    times = [r.taken_at for r in counted if r.taken_at]
    span = (max(times) - min(times)).total_seconds() / 60 if len(times) >= 2 else None
    won = len(counted) >= 5
    return WalkSummary(
        accepted=len(counted),
        won=won,
        has_gps=any(r.location for r in results),
        span_minutes=span,
        within_time=won and span is not None and span <= minutes,
        ai_checked=sum(r.ai_checked for r in results),
    )
