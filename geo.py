"""'Use my location' button: asks the browser for GPS and hands lat/lon back to Python.

Browsers only allow geolocation on HTTPS or localhost, which covers Streamlit Community Cloud.
"""
from __future__ import annotations

import streamlit as st

CSS = """
button{all:unset;box-sizing:border-box;width:100%;min-height:44px;display:flex;align-items:center;justify-content:center;gap:10px;
background:#111214;color:#fff;border:1px solid #111214;cursor:pointer;font:500 10.5px/1 Inter,'Helvetica Neue',sans-serif;
letter-spacing:.14em;text-transform:uppercase;}
button:hover{background:#2a2c30;}
button[disabled]{background:transparent;color:#7d828a;border-color:#b9bec5;cursor:progress;}
svg{flex:none}
p{margin:8px 0 0;font:300 12px/1.5 Inter,'Helvetica Neue',sans-serif;color:#7d828a;min-height:0;}
"""

HTML = """
<button type="button">
<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1">
<circle cx="7" cy="7" r="4.5"/><circle cx="7" cy="7" r="1.2" fill="currentColor"/>
<line x1="7" y1="0" x2="7" y2="2.5"/><line x1="7" y1="11.5" x2="7" y2="14"/>
<line x1="0" y1="7" x2="2.5" y2="7"/><line x1="11.5" y1="7" x2="14" y2="7"/></svg>
<span>Use my location</span></button>
<p></p>
"""

JS = """
export default function({ parentElement, setTriggerValue }) {
  const button = parentElement.querySelector('button');
  const label = parentElement.querySelector('span');
  const note = parentElement.querySelector('p');
  button.onclick = () => {
    if (!navigator.geolocation) { note.textContent = 'This browser has no location access. Type an address instead.'; return; }
    button.disabled = true; label.textContent = 'Locating…'; note.textContent = '';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        button.disabled = false; label.textContent = 'Use my location';
        setTriggerValue('located', { lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy });
      },
      (err) => {
        button.disabled = false; label.textContent = 'Use my location';
        note.textContent = err.code === 1
          ? 'Location permission was blocked. Allow it in the browser, or type an address.'
          : 'Could not get a GPS fix. Try again outside, or type an address.';
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
  };
}
"""

_locate_button = st.components.v2.component("color_loop_gps", html=HTML, css=CSS, js=JS)


def location_button(key: str = "gps") -> dict | None:
    """Render the button. Returns {'lat', 'lon', 'accuracy'} on the run right after a GPS fix."""
    result = _locate_button(key=key, on_located_change=lambda: None)
    return getattr(result, "located", None)
