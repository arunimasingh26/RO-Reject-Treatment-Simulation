"""Assemble the HTML/CSS/JS bundle and embed it in Streamlit."""
from __future__ import annotations

import json
import pathlib

WEB = pathlib.Path(__file__).resolve().parent / "web"
JS_ORDER = ("layout.js", "colour.js", "units.js", "data.js", "scene.js", "playback.js")


def build_html(payload: dict) -> str:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    js = "\n".join((WEB / "js" / f).read_text(encoding="utf-8") for f in JS_ORDER)
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return html.replace("/*CSS*/", css).replace("/*DATA*/", data).replace("/*JS*/", js)


def render_plant(payload: dict, height: int = 900) -> None:
    import streamlit.components.v1 as components

    components.html(build_html(payload), height=height, scrolling=False)
