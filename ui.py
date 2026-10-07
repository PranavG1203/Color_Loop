from __future__ import annotations

from html import escape
from math import cos, radians, sin

import streamlit as st

from colors import ColorTarget

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400;500&display=swap');
:root{--ink:#111214;--muted:#7d828a;--faint:#b9bec5;--line:#cfd3d8;--canvas:#eceef1;--plate:#f7f8f9;
--font:'Inter','Helvetica Neue',Helvetica,Arial,sans-serif;}
html,body,.stApp,[class*="css"],button,input,textarea{font-family:var(--font)!important;color:var(--ink);}
.stApp{background-color:var(--canvas);
background-image:linear-gradient(rgba(17,18,20,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(17,18,20,.045) 1px,transparent 1px),
linear-gradient(rgba(17,18,20,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(17,18,20,.025) 1px,transparent 1px);
background-size:120px 120px,120px 120px,24px 24px,24px 24px;}
header[data-testid="stHeader"]{background:transparent;height:0;}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
.block-container{max-width:1320px;padding:28px clamp(16px,4vw,56px) 96px!important;}
[data-testid="stVerticalBlock"]{gap:0.9rem;}
p,li{font-weight:300;}
a{color:var(--ink)!important;}

/* type */
.lbl{font-size:10.5px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);}
.lbl b{color:var(--ink);font-weight:500;}
.idx{font-variant-numeric:tabular-nums;color:var(--ink);margin-right:14px;}
.rule{border-top:1px solid var(--ink);padding-top:10px;display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;}
.rule.soft{border-top-color:var(--line);}
.body{font-size:15px;font-weight:300;line-height:1.6;color:#3a3d42;max-width:440px;}
.quiet{font-size:12px;font-weight:300;color:var(--muted);line-height:1.6;}

/* top bar */
.topbar{display:flex;justify-content:space-between;align-items:stretch;border-top:1px solid var(--ink);border-bottom:1px solid var(--line);flex-wrap:wrap;}
.brand{display:flex;align-items:center;gap:12px;padding:12px 0;font-size:12px;font-weight:500;letter-spacing:.2em;}
.nav{display:flex;}
.nav span{display:flex;align-items:center;padding:0 18px;font-size:10.5px;font-weight:500;letter-spacing:.14em;color:var(--muted);border-left:1px solid var(--line);}
.nav span.on{background:var(--ink);color:#fff;border-left-color:var(--ink);}
.meta{display:flex;align-items:center;font-size:10.5px;letter-spacing:.14em;color:var(--muted);padding:12px 0;}

.model{color:var(--ink);font-weight:500;}
.model.off{color:var(--muted);}
.notice{border:1px solid var(--ink);border-left-width:4px;padding:14px 18px;display:flex;flex-direction:column;gap:6px;margin-bottom:6px;}
.notice b{font-weight:500;color:var(--ink);}

/* hero */
.hero{padding:72px 0 8px;}
.big{font-size:clamp(84px,15vw,212px);line-height:.78;font-weight:200;letter-spacing:-.065em;margin:28px 0 30px -6px;text-transform:lowercase;}
.chip{display:inline-flex;align-items:center;gap:10px;font-size:11px;letter-spacing:.12em;color:var(--muted);}
.chip i{display:inline-block;width:14px;height:14px;border:1px solid var(--ink);}
.diagram{border:1px solid var(--ink);background:var(--plate);padding:18px;}
.diagram svg{display:block;width:100%;height:auto;}
.diagram .cap{display:flex;justify-content:space-between;margin-top:12px;}

/* metrics */
.metrics{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--ink);}
.metric{padding:14px 16px 4px 0;border-right:1px solid var(--line);margin-right:16px;}
.metric:last-child{border-right:0;}
.metric strong{display:block;font-size:clamp(40px,5vw,64px);line-height:1;font-weight:200;letter-spacing:-.04em;font-variant-numeric:tabular-nums;}
.metric span{display:block;margin-top:10px;}

/* card */
.card{border:1px solid var(--ink);background:var(--plate);padding:22px 22px 18px;}
.card p{font-size:16px;line-height:1.55;font-weight:300;margin:14px 0 18px;}
.empty{border:1px solid var(--line);aspect-ratio:16/10;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:12px;}

/* log */
.log{border-top:1px solid var(--ink);}
.row{display:grid;grid-template-columns:34px minmax(0,1.3fr) minmax(0,1fr) 108px;gap:16px;align-items:center;padding:13px 0;border-bottom:1px solid var(--line);font-size:13px;}
.row .n{color:var(--muted);font-variant-numeric:tabular-nums;font-size:11px;}
.row .name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.row .why{color:var(--muted);font-weight:300;font-size:12px;}
.bar{position:relative;height:1px;background:var(--line);margin-top:8px;}
.bar b{position:absolute;left:0;top:-1px;height:3px;background:var(--ink);}
.bar em{position:absolute;top:-5px;width:1px;height:11px;background:var(--ink);}
.tag{justify-self:end;font-size:10px;font-weight:500;letter-spacing:.14em;padding:6px 10px;border:1px solid var(--faint);color:var(--muted);}
.tag.on{background:var(--ink);border-color:var(--ink);color:#fff;}
.verdict{font-size:clamp(64px,9vw,128px);font-weight:200;line-height:.85;letter-spacing:-.06em;font-variant-numeric:tabular-nums;}
.verdict small{font-size:.32em;color:var(--faint);letter-spacing:-.02em;}
.badges{display:flex;gap:0;flex-wrap:wrap;margin-top:18px;}
.badges span{font-size:10px;font-weight:500;letter-spacing:.14em;padding:7px 11px;border:1px solid var(--faint);color:var(--muted);margin:0 -1px -1px 0;}
.badges span.on{background:var(--ink);color:#fff;border-color:var(--ink);}
.story{border-left:1px solid var(--ink);padding:2px 0 2px 22px;font-size:clamp(18px,2vw,22px);line-height:1.45;font-weight:300;letter-spacing:-.01em;}
.strip{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;}
.strip .blank{background:linear-gradient(to top right,transparent calc(50% - .5px),var(--line) 50%,transparent calc(50% + .5px));}
.strip label{display:block;margin-top:8px;}

/* widgets as instruments */
[data-testid="stWidgetLabel"] p{font-size:10.5px!important;font-weight:500!important;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)!important;}
div[role="radiogroup"]{gap:0!important;flex-wrap:nowrap;}
div[role="radiogroup"] label[data-baseweb="radio"]{margin:0 -1px 0 0!important;padding:12px 20px!important;border:1px solid var(--faint);background:transparent;min-width:84px;justify-content:center;}
div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child{display:none!important;}
div[role="radiogroup"] label[data-baseweb="radio"] p{font-size:11px!important;font-weight:500!important;letter-spacing:.14em;color:var(--muted);}
div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked){background:var(--ink);border-color:var(--ink);position:relative;z-index:1;}
div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p{color:#fff!important;}
[data-testid="stRadioGroup"]{gap:0!important;flex-wrap:nowrap!important;}
[data-testid="stRadioGroup"] > div{margin:0 -1px 0 0!important;}
[data-testid="stRadioOption"]{padding:12px 20px!important;border:1px solid var(--faint);background:transparent;min-width:84px;justify-content:center;margin:0!important;cursor:pointer;}
[data-testid="stRadioOption"] > div > div:not([data-testid]){display:none!important;}
[data-testid="stRadioOption"] p{font-size:11px!important;font-weight:500!important;letter-spacing:.14em;color:var(--muted);margin:0!important;}
[data-testid="stRadioOption"][data-selected="true"]{background:var(--ink);border-color:var(--ink);position:relative;z-index:1;}
[data-testid="stRadioOption"][data-selected="true"] p{color:#fff!important;}
[data-testid="stTextInputRootElement"]{border:0!important;border-bottom:1px solid var(--ink)!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;}
[data-testid="stTextInputField"]{background:transparent!important;padding-left:0!important;font-size:15px!important;font-weight:300;}
.stTextInput div[data-baseweb="input"],.stTextInput div[data-baseweb="base-input"]{border-radius:0!important;background:transparent!important;}
.stTextInput div[data-baseweb="input"]{border:0!important;border-bottom:1px solid var(--ink)!important;}
.stTextInput input{font-size:15px!important;font-weight:300;padding-left:0!important;background:transparent!important;}
.stButton button,.stDownloadButton button,[data-testid="stFileUploaderDropzone"] button{border-radius:0!important;border:1px solid var(--ink)!important;background:transparent!important;color:var(--ink)!important;
font-size:10.5px!important;font-weight:500!important;letter-spacing:.14em;text-transform:uppercase;min-height:44px;padding:0 20px!important;box-shadow:none!important;}
.stButton button p,.stDownloadButton button p{font-size:10.5px!important;font-weight:500!important;letter-spacing:.14em;}
.stButton button[kind="primary"],.stButton button:hover,.stDownloadButton button:hover{background:var(--ink)!important;color:#fff!important;}
.stButton button:hover p,.stButton button[kind="primary"] p,.stDownloadButton button:hover p{color:#fff!important;}
[data-testid="stFileUploaderDropzone"]{border-radius:0!important;border:1px solid var(--ink)!important;background:var(--plate)!important;padding:28px 22px!important;}
[data-testid="stFileUploaderDropzone"] svg{color:var(--ink);}
[data-testid="stFileUploaderFile"]{border-bottom:1px solid var(--line);}
[data-testid="stAlert"]{border-radius:0;}
@media (max-width:760px){
.nav{order:3;width:100%;border-top:1px solid var(--line);}.nav span{flex:1;justify-content:center;padding:10px 0;}.nav span:first-child{border-left:0;}
.metrics{grid-template-columns:repeat(2,1fr);}.metric:nth-child(2){border-right:0;}
.row{grid-template-columns:28px minmax(0,1fr) 92px;}.row .score{display:none;}
.hero{padding-top:44px;}
}
</style>
"""


def html(markup: str) -> None:
    """Render raw HTML. Lines are flattened so markdown never treats indentation as code."""
    st.markdown("".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def section(index: str, title: str, aside: str = "") -> None:
    html(f'<div class="rule"><span class="lbl"><span class="idx">{index}</span><b>{title}</b></span><span class="lbl">{aside}</span></div>')


def spacer(px: int) -> None:
    html(f'<div style="height:{px}px"></div>')


def _point(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = radians(deg - 90)
    return cx + r * cos(a), cy + r * sin(a)


def _arc(cx: float, cy: float, r: float, start: float, end: float) -> str:
    x1, y1 = _point(cx, cy, r, start)
    x2, y2 = _point(cx, cy, r, end)
    large = 1 if (end - start) % 360 > 180 else 0
    return f"M{x1:.2f},{y1:.2f} A{r},{r} 0 {large} 1 {x2:.2f},{y2:.2f}"


def hue_dial(target: ColorTarget) -> str:
    """Line-art hue wheel with the target range drawn as a heavy arc."""
    cx = cy = 160
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="128" fill="none" stroke="#111214" stroke-width="1"/>',
        f'<circle cx="{cx}" cy="{cy}" r="92" fill="none" stroke="#cfd3d8" stroke-width="1"/>',
        f'<circle cx="{cx}" cy="{cy}" r="40" fill="none" stroke="#cfd3d8" stroke-width="1" stroke-dasharray="2 4"/>',
        f'<line x1="{cx - 150}" y1="{cy}" x2="{cx + 150}" y2="{cy}" stroke="#cfd3d8" stroke-width="1"/>',
        f'<line x1="{cx}" y1="{cy - 150}" x2="{cx}" y2="{cy + 150}" stroke="#cfd3d8" stroke-width="1"/>',
    ]
    for deg in range(0, 360, 10):
        inner = 120 if deg % 30 else 112
        x1, y1 = _point(cx, cy, inner, deg)
        x2, y2 = _point(cx, cy, 128, deg)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111214" stroke-width="1"/>')
    for deg in range(0, 360, 90):
        x, y = _point(cx, cy, 145, deg)
        parts.append(f'<text x="{x:.1f}" y="{y + 3:.1f}" font-size="8" letter-spacing="1" text-anchor="middle" fill="#7d828a">{deg:03d}</text>')
    for start, end in target.degrees:
        parts.append(f'<path d="{_arc(cx, cy, 104, start, end)}" fill="none" stroke="#111214" stroke-width="16"/>')
        for edge in (start, end):
            x1, y1 = _point(cx, cy, 40, edge)
            x2, y2 = _point(cx, cy, 128, edge)
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111214" stroke-width=".75"/>')
    parts.append(f'<rect x="{cx - 14}" y="{cy - 14}" width="28" height="28" fill="{target.hex}" stroke="#111214" stroke-width="1"/>')
    return f'<svg viewBox="0 0 320 320" xmlns="http://www.w3.org/2000/svg" font-family="Inter,Helvetica,sans-serif">{"".join(parts)}</svg>'


def loop_glyph(found: int = 0) -> str:
    """Wireframe of a loop with five checkpoints; filled squares are counted frames."""
    path = "M200,212 C80,214 54,150 74,96 C96,38 170,26 214,30 C290,36 344,70 336,128 C328,186 280,210 200,212 Z"
    stops = [(84, 150), (118, 50), (212, 30), (318, 82), (300, 180)]
    parts = [
        '<line x1="0" y1="120" x2="400" y2="120" stroke="#cfd3d8"/>',
        '<line x1="200" y1="0" x2="200" y2="240" stroke="#cfd3d8"/>',
        f'<path d="{path}" fill="none" stroke="#111214" stroke-width="1" stroke-dasharray="4 4"/>',
        '<line x1="200" y1="204" x2="200" y2="220" stroke="#111214"/>',
        '<text x="208" y="232" font-size="8" letter-spacing="1.5" fill="#7d828a">START / END</text>',
    ]
    for index, (x, y) in enumerate(stops):
        fill = "#111214" if index < found else "#f7f8f9"
        parts.append(f'<rect x="{x - 6}" y="{y - 6}" width="12" height="12" fill="{fill}" stroke="#111214"/>')
        parts.append(f'<text x="{x + 12}" y="{y - 8}" font-size="8" letter-spacing="1" fill="#111214">{index + 1:02d}</text>')
    return f'<svg viewBox="0 0 400 240" xmlns="http://www.w3.org/2000/svg" font-family="Inter,Helvetica,sans-serif">{"".join(parts)}</svg>'


def score_bar(score: float, threshold: float, scale: float = 0.5) -> str:
    width = min(score / scale, 1) * 100
    mark = threshold / scale * 100
    return f'<div class="bar"><b style="width:{width:.1f}%"></b><em style="left:{mark:.1f}%"></em></div>'


def safe(text: str) -> str:
    return escape(text, quote=True)
