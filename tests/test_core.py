import sys
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from colors import COLOR_TARGETS, color_by_name, color_of_day  # noqa: E402
from palette import palette_png  # noqa: E402
from route import circle_waypoints, destination, parse_or_geocode, to_gpx, Loop  # noqa: E402
from verify import (  # noqa: E402
    PhotoResult,
    distance_to_path,
    evaluate_photo,
    haversine_meters,
    judge_walk,
    summarize,
)

RED = color_by_name("red")
BLUE = color_by_name("blue")


def photo(rgb, when=None, where=None, fmt="JPEG") -> bytes:
    """Build an in-memory photo with optional EXIF time and GPS."""
    image = Image.new("RGB", (120, 90), rgb)
    exif = Image.Exif()
    if when:
        exif.get_ifd(0x8769)[36867] = when.strftime("%Y:%m:%d %H:%M:%S")
    if where:
        lat, lon = where
        gps = exif.get_ifd(0x8825)
        gps[1], gps[2] = ("N" if lat >= 0 else "S"), (abs(lat), 0.0, 0.0)
        gps[3], gps[4] = ("E" if lon >= 0 else "W"), (abs(lon), 0.0, 0.0)
    out = BytesIO()
    image.save(out, format=fmt, exif=exif)
    return out.getvalue()


def test_color_of_day_is_deterministic_and_cycles():
    assert color_of_day(date(2026, 10, 7)) == color_of_day(date(2026, 10, 7))
    week = {color_of_day(date(2026, 10, d)).name for d in range(1, 7)}
    assert len(week) == len(COLOR_TARGETS)


def test_matching_photo_is_accepted_and_gray_is_rejected():
    assert evaluate_photo(BytesIO(photo((210, 40, 40))), RED).accepted
    gray = evaluate_photo(BytesIO(photo((128, 128, 128))), RED)
    assert not gray.accepted and "too little red" in gray.reason


def test_wrong_color_is_rejected():
    assert not evaluate_photo(BytesIO(photo((210, 40, 40))), BLUE).accepted


def test_exif_time_and_gps_are_read():
    when = datetime(2026, 10, 7, 9, 30, 0)
    result = evaluate_photo(BytesIO(photo((40, 80, 200), when, (52.52, -13.4))), BLUE)
    assert result.taken_at == when
    assert abs(result.location[0] - 52.52) < 1e-6 and abs(result.location[1] + 13.4) < 1e-6


def test_haversine():
    assert haversine_meters((0, 0), (0, 0)) == 0
    assert 110_000 < haversine_meters((0, 0), (1, 0)) < 112_000


def test_distance_to_path():
    path = [(0.0, 0.0), (0.0, 0.01)]
    assert distance_to_path((0.0, 0.005), path) < 1
    assert 100 < distance_to_path((0.001, 0.005), path) < 120


def test_spread_rule_rejects_close_photos():
    t = datetime(2026, 10, 7, 9, 0, 0)
    photos = [
        ("a.jpg", photo((210, 40, 40), t, (52.5200, 13.4050))),
        ("b.jpg", photo((210, 40, 40), t.replace(minute=5), (52.5201, 13.4050))),  # ~11 m away
    ]
    results = judge_walk(photos, RED)
    assert [r.accepted for r in results] == [True, False]
    assert "from a.jpg" in results[1].reason


def test_dedupe_rule_rejects_burst_shots():
    t = datetime(2026, 10, 7, 9, 0, 0)
    photos = [("a.jpg", photo((210, 40, 40), t)), ("b.jpg", photo((210, 40, 40), t.replace(second=10)))]
    results = judge_walk(photos, RED)
    assert [r.accepted for r in results] == [True, False]
    assert "duplicate" in results[1].reason


def test_route_rule_rejects_far_photos():
    route = [(52.52, 13.40), (52.52, 13.41)]
    photos = [("far.jpg", photo((210, 40, 40), None, (52.53, 13.405)))]
    result = judge_walk(photos, RED, route)[0]
    assert not result.accepted and "off the planned loop" in result.reason


def test_five_spread_photos_win():
    photos = [
        (f"{i}.jpg", photo((210, 40, 40), datetime(2026, 10, 7, 9, i * 5), (52.52 + i * 0.003, 13.40)))
        for i in range(5)
    ]
    results = judge_walk(photos, RED)
    summary = summarize(results, 30)
    assert summary.won and summary.accepted == 5 and summary.has_gps and summary.within_time


def test_results_sorted_by_time():
    late, early = datetime(2026, 10, 7, 10), datetime(2026, 10, 7, 9)
    photos = [("late.jpg", photo((210, 40, 40), late)), ("early.jpg", photo((210, 40, 40), early))]
    assert [r.name for r in judge_walk(photos, RED)] == ["early.jpg", "late.jpg"]


def test_loop_waypoints_start_and_end_home():
    start = (52.52, 13.405)
    points = circle_waypoints(start, 300, 45)
    assert points[0] == start and points[-1] == start and len(points) == 5
    for point in points[1:-1]:
        assert 100 < haversine_meters(start, point) < 700
    assert abs(haversine_meters(start, destination(start, 90, 1000)) - 1000) < 1


def test_coordinates_parse_without_network():
    assert parse_or_geocode("52.52, 13.405")[0] == (52.52, 13.405)


def test_outputs_render():
    results = [PhotoResult("a", True, 0.3, "ok", (200, 40, 40))]
    assert palette_png(results, "red").startswith(b"\x89PNG")
    assert b"<trkpt" in to_gpx(Loop((0, 0), [(0, 0), (0, 0.01)], 1000, True), "test")


class FakeEyes:
    """Stands in for Gemma so the judge tests stay offline and deterministic."""

    def __init__(self, outdoors=True, screen=False, subject="red door"):
        self.answer = type("Seen", (), {"outdoors": outdoors, "screen": screen, "subject": subject})()
        self.calls = 0

    def __call__(self, image, color):
        self.calls += 1
        return self.answer


def test_vision_names_outdoor_finds():
    eyes = FakeEyes()
    results = judge_walk([("a.jpg", photo((210, 40, 40))), ("g.jpg", photo((128, 128, 128)))], RED, observe=eyes)
    assert eyes.calls == 1  # only photos that pass the color test reach the model
    counted = next(r for r in results if r.name == "a.jpg")
    assert counted.accepted and counted.subject == "red door" and counted.ai_checked


def test_vision_rejects_indoor_and_screen_shots():
    indoor = judge_walk([("a.jpg", photo((210, 40, 40)))], RED, observe=FakeEyes(outdoors=False))[0]
    screen = judge_walk([("a.jpg", photo((210, 40, 40)))], RED, observe=FakeEyes(screen=True))[0]
    assert not indoor.accepted and "indoors" in indoor.reason
    assert not screen.accepted and "screen" in screen.reason


def test_unavailable_model_falls_back_to_code_rules():
    result = judge_walk([("a.jpg", photo((210, 40, 40)))], RED, observe=lambda image, color: None)[0]
    assert result.accepted and not result.ai_checked


def test_parse_json_handles_code_fences():
    from llm import parse_json

    assert parse_json('```json\n{"outdoors": true, "subject": "red door"}\n```') == {"outdoors": True, "subject": "red door"}
    assert parse_json("no json here") is None
