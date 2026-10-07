# Color Loop: Design Doc and Build Plan

Hacktoberfest Open-Source AI Challenge, Week 1: Touch Grass

## 1. One-line pitch

Each day has a color. Walk a 1.5 to 3 km loop from your door, photograph that color at 5 different spots, and win. The phone gives you the route and checks the result. It is never something you look at while walking.

## 2. Goals and non-goals

**Goals**

- Real, optimal-effort walk: about 20 to 40 minutes, 2,000 to 4,000 steps.
- Screen time of about 2 minutes before and 2 minutes after, near zero during.
- Win condition is simple and explainable: plain code, not an AI judge.
- Open pieces do real work: local LLM, open routing engine, open map data.
- Runs with no cloud and no API keys.

**Non-goals (cut these to finish)**

- Accounts, databases, social feeds.
- Native mobile app.
- Species or object recognition.
- Perfect GPS handling on every phone.

## 3. User flow

1. **Before (about 30 s):** open the web page, pick 15, 30 or 45 minutes. See today's color and a loop on a map. Optionally print the quest card.
2. **During:** walk. When you see the color, take a photo with your normal camera app (about 5 s each).
3. **After (about 1 min):** upload the photos. The app shows which counted, a palette strip, a win or not-yet result, and a short walk story.

## 4. Architecture

Everything runs on your laptop. The phone is just a browser on the same Wi-Fi.

- **Frontend:** one page (Streamlit is the fastest option; plain FastAPI plus HTML also works).
- **Backend:** Python.
- **Route builder:** OSRM or Valhalla with a walking profile, using an OpenStreetMap extract for your city.
- **Color judge:** Pillow, NumPy and OpenCV (HSV analysis). No AI.
- **Story writer:** a small open model (Qwen2.5 3B or Llama 3.2 3B) served by Ollama.

**Key design decision:** deterministic code decides win or lose. The LLM only writes the quest flavor text and the walk story. This is why a 3B model is enough, and it makes the project easy to test.

## 5. Component details

### 5.1 Color of the day (no AI)

Pick from a fixed list using the date as a seed, so everyone in a run club gets the same color: red, orange, yellow, green, blue, pink, purple, white-ish, brown. Start with 5 to 6 colors that have clean hue ranges (red, orange, yellow, green, blue, purple).

### 5.2 Loop route

Simplest reliable approach:

1. Take the start point (typed address or lat/lon).
2. Target distance D (15 min is about 1.3 km, 30 min about 2.5 km, 45 min about 3.5 km at a casual pace).
3. Create 3 waypoints on a rough circle of circumference D around the start, at a random starting bearing.
4. Ask the routing engine for a foot route: start, wp1, wp2, wp3, start.
5. If the actual distance is within 20 percent of the target, accept it. Otherwise scale the radius and retry (up to 5 tries).

Alternative if you want less setup: use GraphHopper's round-trip feature, which does this in one call.

Safety: use the foot profile only, and show the map before walking so people can sanity check it.

### 5.3 Photo verification (plain code)

For each uploaded photo:

1. **Read EXIF:** GPS lat/lon and timestamp.
2. **Color test:** convert to HSV, then compute the fraction of pixels with hue in the target range, saturation above about 0.35 and value between about 0.2 and 0.95. Pass if the fraction is at least 10 to 15 percent.
3. **Distance test:** the photo must be within about 150 m of the planned route (or within the radius from home).
4. **Spread test:** each accepted photo must be at least 150 m from every previously accepted photo (sort by timestamp first).
5. **Dedupe:** reject photos with the same timestamp within 20 s of each other.

**Win:** 5 accepted photos. Bonus badges: finished within the time chosen, or beat your last distance.

Return a reason for every failed photo ("too little blue", "too close to your last spot"). Players accept a rejection when they understand it.

**Known issue:** phones and browsers often strip GPS from uploaded photos. See risks in section 9. Plan B is to rely on timestamps plus the color test and skip location checks.

### 5.4 Palette strip

For each accepted photo, compute the dominant pixels of the target hue range and average them. Draw 5 swatches in a row as a PNG. That image is your demo and your shareable result.

### 5.5 LLM prompts

The model only sees structured stats and writes short text.

**Quest card prompt (input: color, minutes, distance, weather, sunset time):** write 3 friendly sentences and one safety reminder. Never suggest trespassing, climbing or eating plants.

**Walk story prompt (input: JSON of distance, time, accepted photos, failed photos with reasons, color):** write a 4 sentence upbeat recap. Do not invent facts that are not in the JSON.

## 6. Tech stack (all open)

| Need | Tool |
| --- | --- |
| Language | Python 3.11+ |
| UI | Streamlit (or FastAPI plus one HTML page) |
| LLM runtime | Ollama (llama.cpp under the hood) |
| Model | qwen2.5:3b or llama3.2:3b |
| Map data | OpenStreetMap city extract (Geofabrik) |
| Routing | OSRM or Valhalla (Docker) |
| Images | Pillow, OpenCV, NumPy |
| EXIF | Pillow or exifread |
| Map display | folium or pydeck with OSM tiles (or a pre-rendered image for offline) |

## 7. Suggested repo layout

```
color-loop/
  app.py            # UI
  colors.py         # color list, hue ranges, color of the day
  route.py          # loop generation via OSRM/Valhalla
  verify.py         # EXIF, HSV test, spread test, win logic
  palette.py        # palette strip image
  story.py          # Ollama prompts
  tests/            # unit tests for verify.py
  sample_photos/    # a few test images per color
  README.md
```

## 8. Build plan (about 2 weekends, or one very focused one)

**Step 0: Setup (30 min)**

- Install Python, Docker and Ollama. Run `ollama pull qwen2.5:3b`.
- Create the repo and a virtual environment.

**Step 1: Color judge first (2 hours). This is the heart of the project.**

- Write `colors.py` with hue ranges.
- Write `verify.py` with the HSV fraction test.
- Test it on 10 to 20 photos you already have. Tune the thresholds until red leaves pass and red cars on gray roads do not feel wrong. Write down what you tune; it is great blog content.

**Step 2: EXIF, spread and win logic (1 to 2 hours)**

- Read GPS and timestamp, add the haversine distance, apply spread and dedupe rules.
- Write unit tests with fake coordinates.

**Step 3: Palette strip (1 hour)**

- Generate the swatch PNG from accepted photos.

**Step 4: Story and quest text (1 to 2 hours)**

- Call Ollama from `story.py` with the JSON prompts above.
- Add a fallback template string in case the model is slow or returns junk.

**Step 5: UI (2 hours)**

- Streamlit page: choose duration, show color and quest card, upload photos, show results, palette and story.
- Run it so your phone can open it: `streamlit run app.py --server.address 0.0.0.0`, then visit `http://<laptop-ip>:8501` from your phone.

**Step 6: Route builder (3 to 4 hours, the riskiest part)**

- Download your city extract and start OSRM with the foot profile, or use Valhalla.
- Implement the waypoint-circle loop with retries.
- Show it on a map. Add a printable quest card (browser print to PDF is enough).
- **If this stalls:** ship without it. Use a hand-drawn or Google-free OSM link for "walk roughly 2 km from home" and keep the rest. The color judge and story are the real product.

**Step 7: Field test (the bonus points)**

- Do at least two real walks on different days and colors.
- Record: screen time (use your phone's screen-time stats), distance, steps, accepted and rejected photos and why, any threshold changes you made.
- Take a few photos of yourself actually outside.

**Step 8: Write the post**

- Use the Dev.to template. See section 10.

## 9. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Photo GPS stripped by browser or phone | Test early with your phone. On iPhone, allow location in the photo picker options. Fall back to timestamps plus color only. |
| Color thresholds feel unfair (shadows, sunsets, signs) | Tune on real photos, show failure reasons, keep thresholds in one config. |
| Routing setup eats your time | Use GraphHopper round trip, or ship without routing. |
| Small LLM invents details | Feed only JSON stats, add "do not invent", keep a template fallback. |
| Walking safety | Foot profile only, map preview, standing safety line in the quest card. |
| Scope creep | Defer group mode, streaks and photos of species until after submission. |

## 10. Post outline (maps to the submission template)

- **What I Built:** the Color Loop concept, who it is for, and your measured screen time per walk.
- **Demo:** short video of a walk, plus the palette strip.
- **Code:** GitHub repo.
- **How I Built It:** Ollama and a 3B model, OSM data and OSRM or Valhalla, and the deterministic judge. Explain why the LLM does not judge.
- **Why Open Innovation Matters:** works offline on a laptop, your photos and location never leave the machine, zero cost per walk, swap models freely, and routes and local flavor can be customized because the data and tools are open.
- **Field Test Notes:** your honest results, including failures and tuning.
- **Agent Session (optional):** save the build session with DevRelay and embed it.

## 11. Definition of done

- [ ] Pick a duration and see today's color
- [ ] Upload photos and see accepted or rejected with reasons
- [ ] Win at 5 valid spread-out photos
- [ ] Palette strip generated
- [ ] Walk story generated by the local model
- [ ] Runs with Wi-Fi off (aside from first-time downloads)
- [ ] Two real walks documented
- [ ] Post published with repo link

## 12. Stretch goals (only after the above)

- Weekly seven-color streak
- Run club mode with a shared color and combined palette
- Voice read-aloud of the quest (Piper TTS)
- Seasonal color sets
- Fully offline map tiles
