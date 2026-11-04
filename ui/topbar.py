"""The top bar: the Guide menu and the brand on the left, a demo-account menu on the right. Display only.

No name, photo, email or other personal data is shown or stored: the "account" is a labelled prototype.
"""

from __future__ import annotations

import streamlit as st

from ui import guide
from ui.theme import BRAND_KEY, TOPBAR_KEY

BRAND = "Career Pathways"  # plain bold text, not a heading: the page's one h1 is in the hero
DEMO_LABEL = ":material/account_circle: Demo account"
DEMO_TEXT = (
    "Prototype: you're signed in to a demo account. Nothing is saved, and we don't store names or personal details."
)


def render_topbar() -> None:
    """The first thing on the page. One row on a laptop; it wraps onto a second row at 375px."""
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center", key=TOPBAR_KEY):
        with st.container(horizontal=True, vertical_alignment="center", width="content"):
            guide.render_guide()
            with st.container(key=BRAND_KEY, width="content"):
                st.markdown(f"**{BRAND}**")
        with st.popover(DEMO_LABEL):
            st.markdown(DEMO_TEXT)
