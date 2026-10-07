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
STUDIO_MODEL = "gemma-4-26b-a4b-it"  # open-weight Gemma 4 MoE; override with GEMMA_MODEL
THINKING_ROOM = 1024  # Gemma 4 reasons before answering; those tokens count against the output limit
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


def _setting(*names: str) -> str | None:
    """Environment first, then Streamlit secrets (Community Cloud / .streamlit/secrets.toml)."""
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    try:
        import streamlit as st

        for name in names:
            if st.secrets.get(name):
                return str(st.secrets[name])
    except Exception:  # no secrets file, or not running inside Streamlit
        pass
    return None


def _studio_key() -> str | None:
    return _setting("GEMMA_API_KEY", "GOOGLE_API_KEY")


# Last failure from the model, shown in the UI so a bad key or quota is visible instead of silent.
last_error: str | None = None


_cached: tuple[float, Backend] | None = None


def backend() -> Backend:
    """Prefer local Ollama, then AI Studio. Re-checked every minute so a model started later is picked up."""
    global _cached
    if _cached and time.monotonic() - _cached[0] < 60:
        return _cached[1]
    _cached = (time.monotonic(), _find_backend())
    return _cached[1]


def _find_backend() -> Backend:
    """GEMMA_BACKEND = auto (default) | ollama | studio. 'studio' lets you test the hosted path locally."""
    choice = (_setting("GEMMA_BACKEND") or "auto").lower()
    model = _setting("GEMMA_MODEL") or STUDIO_MODEL
    if choice == "studio":
        return Backend("studio", model) if _studio_key() else Backend("none", "")
    try:
        with urlopen(f"{OLLAMA_HOST}/api/tags", timeout=0.8) as response:
            models = [m["name"] for m in json.loads(response.read()).get("models", [])]
        if any(name.split(":")[0] == OLLAMA_MODEL.split(":")[0] for name in models):
            return Backend("ollama", OLLAMA_MODEL)
    except (OSError, ValueError, KeyError):
        pass
    if choice != "ollama" and _studio_key():
        return Backend("studio", model)
    return Backend("none", "")


def _jpeg_b64(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as image:
        small = image.convert("RGB")
        small.thumbnail((IMAGE_SIDE, IMAGE_SIDE))
        out = BytesIO()
        small.save(out, format="JPEG", quality=85)
    return base64.b64encode(out.getvalue()).decode()


def _post(url: str, body: dict, timeout: float, headers: dict | None = None) -> dict:
    request = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parallel_calls() -> int:
    """Ollama runs one request at a time on a laptop; the hosted API takes a few at once."""
    return 1 if backend().kind == "ollama" else 4


def generate(prompt: str, image: bytes | None = None, json_mode: bool = False, max_tokens: int = 300) -> str | None:
    """Run the prompt (optionally with one photo) on Gemma. None means no answer; see last_error."""
    global last_error
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
            # Short, factual tasks: minimal thinking is ~10x faster and stops long reasoning eating the token limit.
            config = {"temperature": 0.3, "maxOutputTokens": max_tokens + THINKING_ROOM, "thinkingConfig": {"thinkingLevel": "minimal"}}
            body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": config}
            # Key goes in a header, never the URL, so it cannot leak into logs or error messages.
            data = _post(f"{STUDIO_URL}/{chosen.model}:generateContent", body, 60, {"x-goog-api-key": _studio_key() or ""})
            candidate = (data.get("candidates") or [{}])[0]
            # Skip the model's reasoning parts ("thought": true) and keep only the answer.
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            if not text.strip():
                last_error = f"empty reply (finish reason: {candidate.get('finishReason', 'unknown')})"
                return None
            last_error = None
            return text.strip()
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("error", {}).get("message", "")
        except (OSError, ValueError, AttributeError):
            detail = ""
        last_error = f"HTTP {error.code}: {detail[:200] or error.reason}"
        return None
    except (OSError, ValueError, KeyError, IndexError) as error:
        last_error = f"{type(error).__name__}: {str(error)[:200]}"
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
