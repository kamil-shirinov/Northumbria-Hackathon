"""The top bar: the Root logo first at the far left, then the Guide menu, and a demo-account menu on the right. Display only.

No name, photo, email or other personal data is shown or stored: the "account" is a labelled prototype.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

from ui import guide
from ui.theme import BRAND_KEY, TOPBAR_KEY

BRAND = "Root"  # the text shown if the logo file is missing; not a heading: the page's one h1 is in the hero
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "brand" / "root-logo.svg"  # read-only, never edited here
LOGO_HEIGHT_PX = 48
_DEFAULT_RATIO = 264 / 116  # width / height of the logo as delivered
DEMO_LABEL = ":material/account_circle: Demo account"
DEMO_TEXT = (
    "Prototype: you're signed in to a demo account. Nothing is saved, and we don't store names or personal details."
)


def _logo_width(svg: str) -> int:
    """Pixel width that makes the logo LOGO_HEIGHT_PX tall at its own proportions (from its viewBox)."""
    match = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"', svg)
    ratio = float(match.group(1)) / float(match.group(2)) if match and float(match.group(2)) else _DEFAULT_RATIO
    return round(LOGO_HEIGHT_PX * ratio)


def _render_brand() -> None:
    """The Root logo, or the plain text "Root" if the file can't be read."""
    try:
        svg = LOGO_PATH.read_text(encoding="utf-8")
        if not svg.lstrip().startswith(("<svg", "<?xml")):
            raise ValueError("not an SVG")  # st.image would treat other text as a file name and crash the page
        st.image(svg, width=_logo_width(svg), alt=BRAND)
    except (OSError, ValueError):  # OSError covers a missing file, UnicodeDecodeError is a ValueError
        st.markdown(f"**{BRAND}**")


def render_topbar() -> None:
    """The first thing on the page. One row on a laptop; it wraps onto a second row at 375px."""
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", key=TOPBAR_KEY):
        with st.container(horizontal=True, vertical_alignment="center", width="content"):
            with st.container(key=BRAND_KEY, width="content"):
                _render_brand()
            guide.render_guide()
        with st.popover(DEMO_LABEL):
            st.markdown(DEMO_TEXT)
