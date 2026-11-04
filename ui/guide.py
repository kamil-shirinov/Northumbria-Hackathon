"""The "Guide" menu button at the top left: what skills, courses and work experience mean. Plain words only; nothing here decides anything."""

from __future__ import annotations

import streamlit as st

from ui import components
from ui.theme import CARD_KEY_PREFIX

LABEL = ":material/menu: Guide"  # a three-line icon plus visible text

# (heading, text), in the order shown
_BOXES = (
    (
        "Skills",
        "Short, specialised certificates. Quick to get and focused on one thing, such as first aid or food "
        "hygiene. They prove a specific skill to employers.",
    ),
    (
        "Courses",
        "Longer, practical learning over weeks or months. They build several skills at once, often with a "
        "qualification at the end.",
    ),
    (
        "Work experience",
        "Practical, hands-on experience, such as placements, apprenticeships, volunteering or part-time jobs. "
        "It shows employers you can do the job. Paid roles are best, and we flag unpaid placements.",
    ),
)


def render_guide() -> None:
    """A popover button above the title. Its headings are h3, one level below the page's section headings, and it adds no h1."""
    with st.popover(LABEL):
        for index, (heading, text) in enumerate(_BOXES):
            with st.container(border=True, key=f"{CARD_KEY_PREFIX}guide_{index}"):
                st.subheader(heading, anchor=False)
                st.markdown(text)
        st.markdown(f"Not sure which is right for you? Ask the {components.NCS_LINK}.")
