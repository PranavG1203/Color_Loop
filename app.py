from __future__ import annotations

from datetime import date

import folium
import streamlit as st
import streamlit.components.v1 as components

from colors import color_by_name, color_of_day
from geo import location_button
from llm import backend
from palette import palette_colors, palette_png
from route import TARGET_KM, Loop, build_loop, parse_or_geocode, to_gpx
from story import quest_card, walk_story
from ui import CSS, hue_dial, html, loop_glyph, safe, score_bar, section, spacer
from verify import MIN_FRACTION, PhotoResult, judge_walk, summarize
from vision import observe, workers

st.set_page_config(page_title="Color Loop", page_icon="◯", layout="wide", initial_sidebar_state="collapsed")
html(CSS)

MAX_PHOTOS = 12
STEPS_PER_KM = 1300


@st.cache_data(show_spinner=False, ttl=86_400)
def locate(text: str):
    return parse_or_geocode(text)


@st.cache_data(show_spinner=False, ttl=86_400)
def loop_for(lat: float, lon: float, minutes: int, seed: int) -> Loop:
    return build_loop((lat, lon), minutes, seed)


# `model` is part of each cache key so connecting a model later refreshes the results.
@st.cache_data(show_spinner=False, ttl=3_600)
def quest_for(color: str, minutes: int, km: float, model: str) -> tuple[str, str]:
    return quest_card(color, minutes, km, color_by_name(color).description)


@st.cache_data(show_spinner=False, max_entries=20)
def judge(photos: tuple[tuple[str, bytes], ...], color: str, route: tuple | None, model: str) -> list[PhotoResult]:
    return judge_walk(photos, color_by_name(color), route, observe if AI.kind != "none" else None, workers())


@st.cache_data(show_spinner=False, max_entries=20)
def story_for(color: str, minutes: int, outcome: tuple, model: str) -> tuple[str, str]:
    results = [PhotoResult(name, ok, 0.0, reason, subject=subject) for name, ok, reason, subject in outcome]
    return walk_story(color, minutes, results)


def draw_map(loop: Loop) -> None:
    """Leaflet map (no WebGL needed) with grayscale OSM tiles and the loop in ink."""
    fmap = folium.Map(tiles="OpenStreetMap", zoom_control=True, attribution_control=True)
    folium.PolyLine(loop.points, color="#111214", weight=3, opacity=1).add_to(fmap)
    if not loop.routed:
        folium.PolyLine(loop.points, color="#111214", weight=1, dash_array="4 6").add_to(fmap)
    folium.CircleMarker(loop.start, radius=7, color="#111214", weight=2, fill=True, fill_color="#f7f8f9", fill_opacity=1).add_to(fmap)
    fmap.fit_bounds([[min(p[0] for p in loop.points), min(p[1] for p in loop.points)],
                     [max(p[0] for p in loop.points), max(p[1] for p in loop.points)]], padding=(24, 24))
    fmap.get_root().header.add_child(folium.Element(
        "<style>.leaflet-container{background:#eceef1;font-family:Inter,Helvetica,sans-serif}"
        ".leaflet-tile-pane{filter:grayscale(1) contrast(.92) brightness(1.04)}"
        ".leaflet-bar,.leaflet-bar a{border-radius:0!important;box-shadow:none!important;border-color:#111214!important;color:#111214}"
        "html,body{border:1px solid #111214;box-sizing:border-box}</style>"
    ))
    page = fmap.get_root().render()
    if hasattr(st, "iframe"):
        st.iframe(page, height=460)
    else:  # Streamlit < 1.52
        components.html(page, height=460)


AI = backend()
today = date.today()
target = color_of_day(today)
state = st.session_state
state.setdefault("seed", today.toordinal())
uploads = state.get("uploads") or []
stage = "JUDGE" if uploads else ("WALK" if state.get("start") else "PLAN")

# ── Top bar ────────────────────────────────────────────────────────────
nav = "".join(f'<span class="{"on" if step == stage else ""}">{i:02d}&nbsp;&nbsp;{step}</span>' for i, step in enumerate(("PLAN", "WALK", "JUDGE"), 1))
html(f"""
<div class="topbar">
<div class="brand"><svg width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="8" fill="none" stroke="#111214"/><rect x="6" y="6" width="6" height="6" fill="#111214"/></svg>COLOR LOOP</div>
<div class="nav">{nav}</div>
<div class="meta">{today:%Y.%m.%d}&nbsp;&nbsp;/&nbsp;&nbsp;<span class="model {"" if AI.kind != "none" else "off"}">{safe(AI.label)}</span></div>
</div>
""")

# ── Hero: today's color ────────────────────────────────────────────────
hero, _, dial = st.columns([7, 1, 4], gap="small")
with hero:
    html(f"""
<div class="hero">
<div class="lbl"><span class="idx">00</span>Today's signal &nbsp;/&nbsp; same for everyone</div>
<div class="big">{target.name}</div>
<div class="chip"><i style="background:{target.hex}"></i>{target.hex} &nbsp;/&nbsp; REFERENCE</div>
<div style="height:22px"></div>
<div class="body">Find {target.name} in five different places along a short loop: {target.description}. Open map data plans the route, code measures the color, and an open Gemma model checks every shot was taken outside. The phone stays in your pocket in between.</div>
</div>
""")
with dial:
    spacer(72)
    windows = " + ".join(f"{a:03d}–{b:03d}°" for a, b in target.degrees)
    html(f"""
<div class="diagram">{hue_dial(target)}
<div class="cap"><span class="lbl">HUE WINDOW</span><span class="lbl"><b>{windows}</b></span></div>
<div class="cap" style="margin-top:4px"><span class="lbl">SAT / VAL</span><span class="lbl"><b>≥35% / 20–95%</b></span></div>
</div>
""")

spacer(88)

# ── 01 Plan ────────────────────────────────────────────────────────────
section("01", "Plan the loop", "≈ 30 seconds")
spacer(18)
controls, _, readout = st.columns([5, 1, 6], gap="small")
with controls:
    minutes = st.radio("Walk window", [15, 30, 45], index=1, horizontal=True, format_func=lambda m: f"{m} MIN")
    html('<div class="lbl" style="margin-top:6px">Start point</div>')
    fix = location_button()
    if fix:
        state.start = f"{fix['lat']:.6f}, {fix['lon']:.6f}"
        state.start_label = f"Your location · ±{fix['accuracy']:.0f} m"
        st.rerun()
    typed = "" if state.get("start_label") else state.get("start", "")
    start_text = st.text_input("Or type an address", value=typed, placeholder="Street address or place name")
    go, again = st.columns(2, gap="small")
    if go.button("Draw loop", width="stretch") and start_text.strip() and start_text.strip() != state.get("start"):
        state.start, state.start_label = start_text.strip(), None
        st.rerun()
    if again.button("New direction", width="stretch", disabled=not state.get("start")):
        state.seed += 1
km = TARGET_KM[minutes]
with readout:
    html(f"""
<div class="metrics">
<div class="metric"><strong>{minutes}</strong><span class="lbl">Minutes</span></div>
<div class="metric"><strong>{km:.1f}</strong><span class="lbl">Km target</span></div>
<div class="metric"><strong>{km * STEPS_PER_KM / 1000:.1f}k</strong><span class="lbl">Steps approx</span></div>
<div class="metric"><strong>05</strong><span class="lbl">Frames to win</span></div>
</div>
""")

spacer(28)
loop: Loop | None = None
map_col, _, card_col = st.columns([7, 1, 4], gap="small")
with map_col:
    if state.get("start"):
        with st.spinner("Routing on OpenStreetMap…"):
            found = locate(state.start)
            if found:
                (lat, lon), place = found
                loop = loop_for(lat, lon, minutes, state.seed)
        if loop:
            draw_map(loop)
            routed = "FOOT ROUTE / OSRM" if loop.routed else "SKETCH ONLY / ROUTER UNREACHABLE, FOLLOW STREETS NEARBY"
            html(f'<div class="rule soft"><span class="lbl">{safe((state.get("start_label") or place)[:70])}</span><span class="lbl"><b>{loop.distance_m / 1000:.2f} KM</b> &nbsp;/&nbsp; {routed}</span></div>')
        else:
            html('<div class="empty"><span class="lbl"><b>Address not found</b></span><span class="quiet">Try a fuller address, or use your location.</span></div>')
    else:
        html(f'<div class="empty"><div style="width:62%">{loop_glyph()}</div><span class="lbl">Use your location to draw a walking loop</span></div>')
with card_col:
    quest, source = quest_for(target.name, minutes, km, AI.label)
    html(f"""
<div class="card">
<div class="rule"><span class="lbl"><b>Quest card</b></span><span class="lbl">{safe(source)}</span></div>
<p>{safe(quest)}</p>
<div class="rule soft"><span class="lbl">Rules</span><span class="lbl">{int(MIN_FRACTION * 100)}% color · 150 m apart · on the loop</span></div>
</div>
""")
    if loop:
        spacer(6)
        st.download_button("Download route · GPX", to_gpx(loop, f"Color Loop / {target.name}"), "color-loop.gpx", "application/gpx+xml", width="stretch")
        html('<div class="quiet" style="margin-top:6px">Open the GPX in any map app (OsmAnd, Organic Maps) so you never need this page while walking.</div>')

spacer(88)

# ── 02 Walk ────────────────────────────────────────────────────────────
section("02", "Walk", "20–40 minutes, screen off")
spacer(18)
steps, _, glyph = st.columns([5, 1, 6], gap="small")
with steps:
    html(f"""
<div class="log">
<div class="row" style="grid-template-columns:34px 1fr"><span class="n">A</span><span>Put the phone away. Follow the loop from memory or the GPX.</span></div>
<div class="row" style="grid-template-columns:34px 1fr"><span class="n">B</span><span>When you see {target.name}, take one photo with your normal camera. Fill at least a tenth of the frame.</span></div>
<div class="row" style="grid-template-columns:34px 1fr"><span class="n">C</span><span>Keep at least 150 m between counted spots. Photos within 20 s of each other count once.</span></div>
<div class="row" style="grid-template-columns:34px 1fr"><span class="n">D</span><span>Back home, upload the originals. Gemma checks each one is outdoors and names what you found.</span></div>
</div>
""")
with glyph:
    html(f'<div class="diagram">{loop_glyph()}<div class="cap"><span class="lbl">Five checkpoints</span><span class="lbl"><b>one loop</b></span></div></div>')

spacer(88)

# ── 03 Judge ───────────────────────────────────────────────────────────
section("03", "Return with evidence", "Pixels by code · eyes by Gemma")
spacer(18)
if AI.kind == "none":
    html('<div class="notice"><span class="lbl"><b>Vision model offline</b></span><span class="quiet">Color, spacing and route rules still run, but nothing checks that photos were taken outside. Run <b>ollama pull gemma3:4b</b> locally, or add a free <b>GEMMA_API_KEY</b> from Google AI Studio to the app secrets.</span></div>')
spacer(18)
st.file_uploader(
    "Field photos", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="uploads",
    help=f"Up to {MAX_PHOTOS} photos. Originals keep their time and location.",
)

if uploads:
    photos = tuple((f.name, f.getvalue()) for f in uploads[:MAX_PHOTOS])
    route = tuple(loop.points) if loop and loop.routed else None
    with st.spinner("Measuring pixels, then asking Gemma what it sees. On a laptop CPU this takes about 40 s per photo…" if AI.kind == "ollama" else "Measuring pixels, then asking Gemma what it sees…"):
        results = judge(photos, target.name, route, AI.label)
    summary = summarize(results, minutes)

    spacer(24)
    rows = "".join(
        f'<div class="row"><span class="n">{i:02d}</span>'
        f'<div style="min-width:0"><div class="name">{safe(r.name)}</div><div class="why">{safe(r.reason)}</div></div>'
        f'<div class="score"><span class="quiet">{r.score:.0%} {target.name} pixels</span>{score_bar(r.score, MIN_FRACTION)}</div>'
        f'<span class="tag {"on" if r.accepted else ""}">{"COUNTED" if r.accepted else "REJECTED"}</span></div>'
        for i, r in enumerate(results, 1)
    )
    html(f'<div class="log">{rows}</div>')

    spacer(56)
    verdict, _, story_col = st.columns([4, 1, 7], gap="small")
    with verdict:
        badges = [
            ("LOOP CLOSED" if summary.won else f"{5 - summary.accepted} TO GO", summary.won),
            (f"WITHIN {minutes} MIN", summary.within_time),
            ("GPS CHECKED" if summary.has_gps else "NO GPS / TIME + COLOR ONLY", summary.has_gps),
            (f"SEEN BY GEMMA · {summary.ai_checked}" if summary.ai_checked else "NOT SEEN BY AI", summary.ai_checked > 0),
        ]
        badge_html = "".join(f'<span class="{"on" if on else ""}">{text}</span>' for text, on in badges)
        html(f"""
<div class="lbl">Accepted frames</div>
<div class="verdict" style="margin-top:18px">{summary.accepted:02d}<small>/05</small></div>
<div class="badges">{badge_html}</div>
""")
    with story_col:
        outcome = tuple((r.name, r.accepted, r.reason, r.subject) for r in results)
        with st.spinner("Gemma is writing your field note…"):
            text, source = story_for(target.name, minutes, outcome, AI.label)
        html(f'<div class="rule soft" style="margin-bottom:18px"><span class="lbl"><b>Field note</b></span><span class="lbl">{safe(source)}</span></div><div class="story">{safe(text)}</div>')

    spacer(56)
    swatches = palette_colors(results)
    cells = "".join(
        f'<div><div style="background:rgb{swatches[i]};aspect-ratio:3/4;border:1px solid #111214"></div><label class="lbl">{i + 1:02d} &nbsp;#{"%02X%02X%02X" % swatches[i]}</label></div>'
        if i < len(swatches) else f'<div><div class="blank" style="aspect-ratio:3/4;border:1px solid var(--line)"></div><label class="lbl">{i + 1:02d} &nbsp;—</label></div>'
        for i in range(5)
    )
    section("04", "Palette", "Mean of matching pixels per frame")
    spacer(18)
    html(f'<div class="strip" style="grid-template-columns:repeat(5,1fr)">{cells}</div>')
    spacer(18)
    _, dl = st.columns([8, 4])
    dl.download_button("Download palette · PNG", palette_png(results, target.name), f"color-loop-{today:%Y%m%d}.png", "image/png", width="stretch")
else:
    html('<div class="quiet" style="margin-top:4px">Photos are analysed in memory for this session and are not stored.</div>')

spacer(96)
html('<div class="rule soft"><span class="lbl">Color Loop / open source / Gemma 3 · OpenStreetMap · OSRM · OpenCV · Ollama</span><span class="lbl">Touch grass</span></div>')
