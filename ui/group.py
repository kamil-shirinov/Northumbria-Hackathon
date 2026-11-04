"""Section 2: the group the engine picked, which the user can change."""

from __future__ import annotations

import streamlit as st

from groups import GROUPS
from ui import components

GROUP_KEY = "group_choice"  # widget state; app.py clears it when a new profile is submitted


def _label(group_id: str) -> str:
    return GROUPS.get(group_id, {}).get("label", group_id)


def render_group(assigned: str) -> str:
    """Show the assigned group and let the user pick another. Returns the chosen group id."""
    st.header("2. Your group")

    group_ids = list(GROUPS)
    if st.session_state.get(GROUP_KEY) not in GROUPS:
        st.session_state[GROUP_KEY] = assigned if assigned in GROUPS else group_ids[0]

    st.markdown(f"Based on your answers, we've placed you in **{components.escape(_label(assigned))}**.")
    chosen = st.selectbox(
        "If that doesn't feel right, choose a different group",
        group_ids,
        format_func=_label,
        key=GROUP_KEY,
    )

    description = GROUPS.get(chosen, {}).get("description")
    st.info(f"**{components.escape(_label(chosen))}**" + (f": {components.escape(description)}" if description else ""))
    if chosen != assigned:
        st.caption(f"You changed this from {_label(assigned)}.")
    st.caption("Everything below uses the group shown here.")
    return chosen
