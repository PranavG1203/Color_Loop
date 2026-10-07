# Color Loop

Each day has a color. Walk a 1.5 to 3 km loop from your door, photograph that color in five different spots, and close the loop. The phone plans the route and judges the photos. Between those two moments it stays in your pocket.

Open-source AI sits in the judge. **Gemma**, Google's open-weight vision model family, looks at every photo that passes the color test. It names what you found ("red postbox") and rejects shots taken indoors or of a screen, so the game can only be won outside. Plain, testable code measures the color and applies the distance rules. Gemma answers what pixels can't. It also writes the quest card and a walk story built only from what it actually saw.

## How it works

| Piece | File | What it does |
| --- | --- | --- |
| Color of the day | `colors.py` | Date-seeded pick from six hue windows, so everyone gets the same color. |
| Loop route | `route.py` | Three waypoints on a circle through your start, routed on foot by OSRM over OpenStreetMap, rescaled until it is within 20% of the target distance. GPX export. |
| Judge | `verify.py` | HSV pixel share (≥10% in the hue window, saturation ≥35%, value 20–95%), EXIF time and GPS, ≤150 m from the loop, ≥150 m between counted spots, burst shots within 20 s count once. Every rejection has a reason. |
| Palette | `palette.py` | Mean color of matching pixels per counted photo, exported as a PNG. |
| Vision check | `vision.py` | Gemma gets each color-passing photo and returns `{subject, outdoors, screen}` as JSON. Indoor or screen shots are rejected with a reason. |
| Model backend | `llm.py` | Open Gemma weights over two transports: local Ollama (`gemma3:4b`, photos never leave the laptop) or Google AI Studio (`gemma-4-26b-a4b-it`, for the hosted app, with minimal thinking for speed). |
| Story | `story.py` | Gemma gets JSON stats plus the things it saw, and writes the quest card and recap. Falls back to a template if no model answers. |
| UI | `app.py`, `ui.py` | Streamlit page in a monochrome, grid-based style. |

All thresholds are constants at the top of `verify.py`.

If your phone strips GPS from uploads, the judge falls back to time plus color, and the result says so.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0
```

Open `http://<laptop-ip>:8501` on your phone (same Wi-Fi).

Run Gemma locally (fully offline judging, photos stay on your machine):

```powershell
ollama pull gemma3:4b
```

The app finds Ollama automatically. Without it, set `GEMMA_API_KEY` to use AI Studio instead.

### Environment variables

| Variable | Default |
| --- | --- |
| `OSRM_URL` | `https://routing.openstreetmap.de/routed-foot` (point it at a local OSRM Docker instance to run fully offline) |
| `NOMINATIM_URL` | `https://nominatim.openstreetmap.org` |
| `OLLAMA_HOST` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `gemma3:4b` |
| `GEMMA_API_KEY` | unset (free key from aistudio.google.com/apikey) |
| `GEMMA_MODEL` | `gemma-4-26b-a4b-it` |
| `GEMMA_BACKEND` | `auto` (prefer Ollama, then AI Studio); `studio` or `ollama` to force one |

## Deploy to Streamlit Community Cloud

1. Push this folder to a public GitHub repository.
2. At share.streamlit.io, choose **Create app**, pick the repo, and set the main file to `app.py`.
3. Under **Advanced settings → Secrets**, paste the contents of `.streamlit/secrets.toml.example` with your free AI Studio key.
4. Deploy.

Ollama can't run on Community Cloud, so the hosted app calls open Gemma 4 through AI Studio. Run `python check_gemma.py` to confirm a key works. The top bar shows which model is connected. Routing uses the public FOSSGIS foot router. Photos are processed in memory on the Streamlit server and are not stored. For the fully local, private setup, run it on your laptop as above.

## Tests

```powershell
pip install pytest
python -m pytest -q
```

## License

MIT. See [LICENSE](LICENSE).
