from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from math import asin, atan2, cos, degrees, pi, radians, sin
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from verify import LatLon, haversine_meters

# Any OSRM server with a foot profile works; point OSRM_URL at a local Docker instance to run offline.
OSRM_URL = os.environ.get("OSRM_URL", "https://routing.openstreetmap.de/routed-foot").rstrip("/")
NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org").rstrip("/")
USER_AGENT = "color-loop/0.2 (hacktoberfest walking game)"
TARGET_KM = {15: 1.3, 30: 2.5, 45: 3.5}
TOLERANCE = 0.20
MAX_TRIES = 5


@dataclass
class Loop:
    start: LatLon
    points: list[LatLon]
    distance_m: float
    routed: bool  # False means a geometric sketch, not street-routed


def _get_json(url: str, timeout: float = 10) -> dict | list:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_or_geocode(text: str) -> tuple[LatLon, str] | None:
    """Accept 'lat, lon' directly, otherwise look the address up on Nominatim."""
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)\s*", text)
    if match:
        lat, lon = float(match[1]), float(match[2])
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return (lat, lon), f"{lat:.5f}, {lon:.5f}"
    query = urlencode({"q": text, "format": "json", "limit": 1})
    try:
        found = _get_json(f"{NOMINATIM_URL}/search?{query}")
    except (OSError, ValueError):
        return None
    if not found:
        return None
    return (float(found[0]["lat"]), float(found[0]["lon"])), found[0].get("display_name", text)


def destination(origin: LatLon, bearing_deg: float, distance_m: float) -> LatLon:
    earth_radius = 6_371_000
    lat, lon, bearing = radians(origin[0]), radians(origin[1]), radians(bearing_deg)
    angular = distance_m / earth_radius
    lat_two = asin(sin(lat) * cos(angular) + cos(lat) * sin(angular) * cos(bearing))
    lon_two = lon + atan2(sin(bearing) * sin(angular) * cos(lat), cos(angular) - sin(lat) * sin(lat_two))
    return degrees(lat_two), (degrees(lon_two) + 540) % 360 - 180


def circle_waypoints(start: LatLon, radius_m: float, bearing_deg: float) -> list[LatLon]:
    """Start, three points on a circle that passes through start, start again."""
    center = destination(start, bearing_deg, radius_m)
    back = (bearing_deg + 180) % 360
    return [start, *(destination(center, back + 90 * k, radius_m) for k in (1, 2, 3)), start]


def _sketch(start: LatLon, radius_m: float, bearing_deg: float) -> list[LatLon]:
    center = destination(start, bearing_deg, radius_m)
    back = (bearing_deg + 180) % 360
    return [destination(center, back + step * 10, radius_m) for step in range(37)]


def _osrm_route(waypoints: list[LatLon]) -> tuple[list[LatLon], float]:
    coordinates = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in waypoints)
    url = f"{OSRM_URL}/route/v1/foot/{quote(coordinates, safe=';,.-')}?overview=full&geometries=geojson"
    data = _get_json(url, timeout=12)
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(data.get("message", "no route"))
    route = data["routes"][0]
    return [(lat, lon) for lon, lat in route["geometry"]["coordinates"]], float(route["distance"])


def build_loop(start: LatLon, minutes: int, seed: int) -> Loop:
    target_m = TARGET_KM.get(minutes, minutes / 12) * 1000
    bearing = random.Random(seed).uniform(0, 360)
    # Streets wind, so start a bit smaller than a perfect circle of that circumference.
    radius = target_m / (2 * pi) / 1.25
    best: tuple[list[LatLon], float] | None = None
    for _ in range(MAX_TRIES):
        try:
            points, distance = _osrm_route(circle_waypoints(start, radius, bearing))
        except (OSError, ValueError, KeyError):
            break
        if best is None or abs(distance - target_m) < abs(best[1] - target_m):
            best = (points, distance)
        if abs(distance - target_m) <= TOLERANCE * target_m:
            break
        radius *= target_m / max(distance, 1)
    if best:
        return Loop(start, best[0], best[1], routed=True)
    sketch = _sketch(start, target_m / (2 * pi), bearing)
    length = sum(haversine_meters(a, b) for a, b in zip(sketch, sketch[1:]))
    return Loop(start, sketch, length, routed=False)


def to_gpx(loop: Loop, name: str) -> bytes:
    points = "".join(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"/>' for lat, lon in loop.points)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="Color Loop" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><name>{name}</name><trkseg>{points}</trkseg></trk></gpx>"
    ).encode("utf-8")
