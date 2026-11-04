"""Section 4: the skills the user has and the skills still to learn for the selected career."""

from __future__ import annotations

import streamlit as st

from ui import components


def _bullets(skills: list[str], prefix: str = "") -> str:
    return "\n".join(f"- {prefix}{components.escape(s)}" for s in skills)


def render_skills_gap(gap: dict, career: dict | None = None) -> None:
    """Show "You have" and "Still to learn". `career` (optional) only names the career in a caption."""
    st.header("4. Your skills gap", anchor=False)
    if career:
        st.caption(f"For: {components.escape(career.get('title', ''))}")

    have = list((gap or {}).get("have") or [])
    missing = list((gap or {}).get("missing") or [])
    total = len(have) + len(missing)

    if total == 0:
        components.empty_message("We haven't listed any skills for this career yet.")
        return

    st.markdown(f"**You have {len(have)} of {total} skills**")
    st.progress(len(have) / total)

    have_col, missing_col = st.columns(2)
    with have_col:
        st.subheader("You have", anchor=False)  # one level below the section heading
        if have:
            st.markdown(_bullets(have, "✓ "))
        else:
            st.write("None of these yet. That's fine, everyone starts somewhere.")
    with missing_col:
        st.subheader("Still to learn", anchor=False)
        if missing:
            st.markdown(_bullets(missing))
        else:
            st.write("Nothing. You already have every skill listed for this career.")
