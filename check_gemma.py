"""Quick check that Gemma answers: `python check_gemma.py [photo.jpg]`.

Reads the same settings as the app (environment or .streamlit/secrets.toml).
Prints which backend is used and any error. Never prints the API key.
"""
from __future__ import annotations

import sys
import time
from io import BytesIO

from PIL import Image

import llm
from vision import observe


def main() -> int:
    chosen = llm.backend()
    print(f"backend : {chosen.label}")
    if chosen.kind == "none":
        print("No model found. Set GEMMA_API_KEY in .streamlit/secrets.toml, or run `ollama pull gemma3:4b`.")
        return 1

    start = time.time()
    text = llm.generate("Reply with exactly: Gemma is ready.", max_tokens=20)
    print(f"text    : {text!r} ({time.time() - start:.1f}s)")
    if text is None:
        print(f"error   : {llm.last_error}")
        return 1

    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as handle:
            photo = handle.read()
    else:
        buffer = BytesIO()
        Image.new("RGB", (320, 240), (200, 40, 40)).save(buffer, format="JPEG")
        photo = buffer.getvalue()
    start = time.time()
    seen = observe(photo, "red")
    print(f"vision  : {seen} ({time.time() - start:.1f}s)")
    if seen is None:
        print(f"error   : {llm.last_error or 'reply was not the expected JSON'}")
        return 1
    print("OK, Gemma is connected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
