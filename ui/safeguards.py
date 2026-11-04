"""The "How this works and how we keep it fair" panel. Plain words only; nothing here decides anything."""

from __future__ import annotations

import streamlit as st

from groups import NCS_URL
from ui import components

TITLE = "How this works and how we keep it fair"

_POINTS = (
    "**Fixed rules rank your careers, not AI.** Rules in our code pick your group, your careers, "
    "your skills gap and your courses.",
    "**The AI advisor only explains these results.** We check every career and course it names "
    "against our data.",
    "**Personal details never change the ranking.** We never use your name, gender, ethnicity, "
    "age or postcode. Your town doesn't change it either.",
    "**Every career shows a way in.** Some routes are longer, but none are closed.",
    "**Pay is always shown.** Unpaid placements are flagged.",
    "**Free and funded courses come first** when courses cover the same skills.",
    "**Every career and course links to its source.**",
)

_LIMITS = (
    "**Limits:** the AI can still word things wrongly. Our check catches careers and courses it "
    "makes up, but not every mistake. Check the source before you decide."
)

_HELP = f"**For a complicated situation,** talk to the {components.NCS_LINK}: {NCS_URL}"


def render_how_it_works() -> None:
    """A closed expander near the top of the page, before section 1."""
    with st.expander(TITLE):
        st.markdown("\n".join(f"- {point}" for point in _POINTS))
        st.markdown(_LIMITS)
        st.markdown(_HELP)
