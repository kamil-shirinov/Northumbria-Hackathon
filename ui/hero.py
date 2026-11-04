"""The hero band: the page's one h1, the tagline, and a decorative pathway that draws itself. Display only.

The pathway is inline SVG (no images, fonts or scripts), marked aria-hidden because the tagline already says the
same thing in words. It goes through st.markdown, not st.html: Streamlit's st.html strips SVG. It is one line with
no blank lines, so markdown passes it through as a single block of HTML.
"""

from __future__ import annotations

import streamlit as st

from ui.theme import HERO_KEY

TITLE = "Root"
TAGLINE = "Find North East careers, the skills they need, and the courses that get you there."

_TEXT = "#111827"  # dark text: over 14:1 on the whole light-blue to pink band
_LINE = "#C2185B"  # the pink accent from .streamlit/config.toml

# A winding line through the three dots (each is where a segment ends); labels sit just below their dots.
_PATH = "M8 40 C24 40 24 52 40 52 C95 52 95 28 150 28 C205 28 205 52 260 52 C275 52 275 38 292 38"
_DOTS = (("Skills", 40, 52, 72), ("Courses", 150, 28, 48), ("Job", 260, 52, 72))  # label, x, y, label y

PATHWAY_SVG = (
    '<div class="cp-pathway">'
    '<svg viewBox="0 0 300 80" aria-hidden="true">'
    # The mask reveals the dotted line. Its stroke-dashoffset is what animates (see ui/theme.py).
    '<defs><mask id="cp-reveal" maskUnits="userSpaceOnUse" x="0" y="0" width="300" height="80">'
    f'<path class="cp-draw" d="{_PATH}" pathLength="1" fill="none" stroke="#FFFFFF" stroke-width="14" '
    'stroke-linecap="round" stroke-dasharray="1" stroke-dashoffset="0"/>'
    "</mask></defs>"
    f'<path d="{_PATH}" fill="none" stroke="{_LINE}" stroke-width="3.5" stroke-linecap="round" '
    'stroke-dasharray="0.1 9" mask="url(#cp-reveal)"/>'
    + "".join(f'<circle cx="{x}" cy="{y}" r="6" fill="{_LINE}"/>' for _, x, y, _ in _DOTS)
    + "".join(
        f'<text x="{x}" y="{label_y}" text-anchor="middle" font-size="13" font-weight="600" fill="{_TEXT}">{label}</text>'
        for label, x, _, label_y in _DOTS
    )
    + "</svg></div>"
)


def render_hero() -> None:
    """Title and tagline on the left, the pathway on the right; they stack on a phone."""
    with st.container(key=HERO_KEY):
        text_col, art_col = st.columns([3, 2], vertical_alignment="center")
        with text_col:
            st.title(TITLE, anchor=False)
            st.markdown(TAGLINE)
        with art_col:
            st.markdown(PATHWAY_SVG, unsafe_allow_html=True)
