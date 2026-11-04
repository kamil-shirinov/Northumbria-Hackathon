"""Root: one page, sections 1 to 6. Page setup, session state and calls only.

Every decision comes from engine.py; everything drawn comes from ui/.
"""

from __future__ import annotations

import streamlit as st

import engine
from ui import careers as careers_ui
from ui import chat as chat_ui
from ui import components
from ui import courses as courses_ui
from ui import group as group_ui
from ui import hero
from ui import profile_form
from ui import safeguards
from ui import skills_gap as skills_gap_ui
from ui import theme
from ui import topbar

st.set_page_config(page_title="Root: North East careers", page_icon="🧭", layout="wide")
theme.apply_theme()

st.session_state.setdefault("profile", None)
st.session_state.setdefault("group", None)
st.session_state.setdefault("career", None)

# The top bar comes first: the Guide menu and brand on the left, the demo account on the right.
topbar.render_topbar()

# The hero band: the page's one h1, the tagline and the pathway.
hero.render_hero()

# How the page works and how it stays fair, before the form
safeguards.render_how_it_works()

# 1. Profile
submitted = profile_form.render_profile_form()
if submitted is not None:
    st.session_state.profile = submitted
    # A new profile starts again from the assigned group and the first career.
    st.session_state.pop(group_ui.GROUP_KEY, None)
    st.session_state.pop(careers_ui.CAREER_KEY, None)

profile = st.session_state.profile
if profile is None:
    st.info("Fill in the form above and press “Show my careers” to see your results.")
    components.footer()
    st.stop()

# 2. Group
group = group_ui.render_group(engine.assign_group(profile))
st.session_state.group = group

# 3. Careers
ranked = engine.rank_careers(profile, group, n=5)
career = careers_ui.render_careers(ranked, group)
st.session_state.career = career

gap, courses = None, []
if career is not None:
    # 4. Skills gap
    gap = engine.skills_gap(profile, career)
    skills_gap_ui.render_skills_gap(gap, career)

    # 5. Courses
    courses = engine.recommend_courses(gap["missing"], profile, n=5)
    courses_ui.render_courses(courses, gap["missing"], career)

# 6. Advisor chat. The context is exactly what is on the page, in the shape CONTRACT v1 defines.
context = {"careers": ranked, "selected_career": career, "gap": gap, "courses": courses}
chat_ui.render_chat(group, profile, context, ranked, courses)
components.footer()
