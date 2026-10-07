"""One open-weight model (Gemma 3) behind two transports.

Local:  Ollama on this machine (`ollama pull gemma3:4b`). Photos never leave the laptop.
Hosted: the same Gemma weights served by Google AI Studio (free key in GEMMA_API_KEY),
        used on Streamlit Community Cloud where Ollama cannot run.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
STUDIO_URL = "https://generativelanguage.googleapis.com/v1beta/models"
STUDIO_MODEL = os.environ.get("GEMMA_MODEL", "gemma-3-27b-it")
IMAGE_SIDE = 640


@dataclass(frozen=True)
class Backend:
    kind: str  # "ollama", "studio" or "none"
    model: str

    @property
    def label(self) -> str:
        if self.kind == "ollama":
            return f"{self.model} / local ollama"
        if self.kind == "studio":
            return f"{self.model} / ai studio"
        return "no model connected"


def _studio_key() -> str | None:
    """Key from the environment, or from Streamlit secrets (Community Cloud / .streamlit/secrets.toml)."""
    key = os.environ.get("GEMMA_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("GEMMA_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
    except Exception:  # no secrets file, or not running inside Streamlit
        return None


_cached: tuple[float, Backend] | None = None


def backend() -> Backend:
    """Prefer local Ollama, then AI Studio. Re-checked every minute so a model started later is picked up."""
    global _cached
    if _cached and time.monotonic() - _cached[0] < 60:
        return _cached[1]
    _cached = (time.monotonic(), _find_backend())
    return _cached[1]


def _find_backend() -> Backend:
    try:
        with urlopen(f"{OLLAMA_HOST}/api/tags", timeout=0.8) as response:
            models = [m["name"] for m in json.loads(response.read()).get("models", [])]
        if any(name.split(":")[0] == OLLAMA_MODEL.split(":")[0] for name in models):
            return Backend("ollama", OLLAMA_MODEL)
    except (OSError, ValueError, KeyError):
        pass
    if _studio_key():
        return Backend("studio", STUDIO_MODEL)
    return Backend("none", "")


def _jpeg_b64(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as image:
        small = image.convert("RGB")
        small.thumbnail((IMAGE_SIDE, IMAGE_SIDE))
        out = BytesIO()
        small.save(out, format="JPEG", quality=85)
    return base64.b64encode(out.getvalue()).decode()


def _post(url: str, body: dict, timeout: float) -> dict:
    request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parallel_calls() -> int:
    """Ollama runs one request at a time on a laptop; the hosted API takes a few at once."""
    return 1 if backend().kind == "ollama" else 4


def generate(prompt: str, image: bytes | None = None, json_mode: bool = False, max_tokens: int = 300) -> str | None:
    """Run the prompt (optionally with one photo) on Gemma. None means no answer."""
    chosen = backend()
    try:
        if chosen.kind == "ollama":
            # CPU-only laptops need ~40 s per photo, so the local timeout is generous.
            options = {"temperature": 0.3, "num_predict": max_tokens}
            body = {"model": chosen.model, "prompt": prompt, "stream": False, "options": options, "keep_alive": "15m"}
            if json_mode:
                body["format"] = "json"
            if image:
                body["images"] = [_jpeg_b64(image)]
            return _post(f"{OLLAMA_HOST}/api/generate", body, 180).get("response", "").strip() or None
        if chosen.kind == "studio":
            parts: list[dict] = [{"text": prompt}]
            if image:
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": _jpeg_b64(image)}})
            config = {"temperature": 0.3, "maxOutputTokens": max_tokens}
            body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}
            data = _post(f"{STUDIO_URL}/{chosen.model}:generateContent?key={_studio_key()}", body, 60)
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            return text.strip() or None
    except HTTPError:
        return None
    except (OSError, ValueError, KeyError, IndexError):
        return None
    return None


def parse_json(text: str | None) -> dict | None:
    """Pull the first JSON object out of a model reply (Gemma often wraps it in a code fence)."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None
