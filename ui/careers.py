"""Section 3: career cards. The user picks one; the skills gap and courses follow it."""

from __future__ import annotations

import streamlit as st

from groups import GROUPS
from ui import components

CAREER_KEY = "career_choice"  # selected career_id; app.py clears it when a new profile is submitted


def _choose(career_id: str) -> None:
    st.session_state[CAREER_KEY] = career_id


def _route_text(career: dict) -> str:
    route = str(career.get("entry_route") or "").strip()
    if route:
        return components.escape(route)
    return f"There's no set route listed yet, but there is always a way in. The {components.NCS_LINK} can help you find one."


def _card(career: dict, group_label: str, selected: bool) -> None:
    career_id = career["career_id"]
    title = career.get("title", career_id)
    with st.container(border=True):
        st.subheader(components.escape(title), anchor=False)
        st.markdown(
            f"{components.badge(career.get('sector') or 'Sector not listed', 'blue')} "
            f"{components.demand_badge(career.get('ne_demand'))}"
        )
        st.markdown(f"**Typical pay:** {components.pay_range(career.get('pay_min'), career.get('pay_max'))}")
        st.markdown(f"**Your route in ({components.escape(group_label)}):** {_route_text(career)}")
        if career.get("unpaid_placement"):
            components.unpaid_flag("route")
        reasons = career.get("reasons") or []
        if reasons:
            st.markdown("**Why it fits you:**\n" + "\n".join(f"- {components.escape(r)}" for r in reasons))
        components.source_link(career.get("source_url"), subject=title)
        if selected:
            st.markdown(components.badge("✓ Selected: see sections 4 and 5", "green"))
        else:
            st.button(
                f"Choose {components.escape(title)}",  # the title, so each button makes sense on its own
                key=f"pick_career_{career_id}",
                on_click=_choose,
                args=(career_id,),
                help=f"Show the skills gap and courses for {title}",
            )


def render_careers(careers: list[dict], group: str) -> dict | None:
    """Show one card per career. Returns the selected career, which defaults to the first."""
    st.header("3. Careers for you", anchor=False)

    if not careers:
        components.empty_message("We couldn't find any careers to show yet.")
        return None

    group_label = GROUPS.get(group, {}).get("label", group)
    st.caption(
        f"Ranked for your profile, with the route in for the “{group_label}” group. "
        "Typical pay is shown, and unpaid placements are flagged."
    )

    ids = [c["career_id"] for c in careers]
    if st.session_state.get(CAREER_KEY) not in ids:
        st.session_state[CAREER_KEY] = ids[0]
    selected_id = st.session_state[CAREER_KEY]

    for career in careers:
        _card(career, group_label, selected=career["career_id"] == selected_id)

    return next(c for c in careers if c["career_id"] == selected_id)
