"""Section 5: courses that close the skills gap, shown in the order the engine gives them."""

from __future__ import annotations

import streamlit as st

from ui import components


def _card(course: dict) -> None:
    title = course.get("title", course.get("course_id", "Course"))
    cost = f"**Cost:** {components.cost_text(course.get('cost_gbp'))}"
    if course.get("funded"):
        cost += f" {components.badge('Funded', 'green')}"

    with st.container(border=True):
        st.subheader(components.escape(title), anchor=False)
        st.caption(components.escape(course.get("provider") or "Provider not listed"))
        st.markdown(cost)
        st.markdown(
            f"**Length:** {components.weeks_text(course.get('length_weeks'))}  \n"
            f"**Format:** {components.escape(course.get('format') or 'Not listed')}  \n"
            f"**Entry requirements:** {components.escape(course.get('entry_requirements') or 'None listed')}"
        )
        closes = course.get("closes") or []
        if closes:
            st.markdown(f"**Covers your missing skills:** {components.escape(', '.join(closes))}")
        if course.get("unpaid_placement"):
            components.unpaid_flag("course")
        components.source_link(course.get("source_url"), subject=title)


def render_courses(courses: list[dict], missing: list[str], career: dict | None = None) -> None:
    """Show one card per course, in the given order. `career` (optional) is used only when there are none."""
    st.header("5. Courses to close the gap", anchor=False)

    if not missing:
        st.success("You already have every skill listed for this career, so there's no course to take for it.")
        return

    if not courses:
        route = str((career or {}).get("entry_route") or "").strip()
        st.info(
            "We don't have a listed course for the skills you still need yet. "
            + (f"A good next step is your route in: {components.escape(route)} " if route else "")
            + f"The {components.NCS_LINK} can also help you find a way to learn them."
        )
        return

    st.caption(
        f"Best match first. These courses teach skills you still need: {components.escape(', '.join(missing))}."
    )
    st.caption("Free and funded courses come first when courses cover the same skills.")
    for course in courses:
        _card(course)
