"""Career Pathways: one page, sections 1 to 6. Page setup, session state and calls only.

Every decision comes from engine.py; everything drawn comes from ui/.
"""

from __future__ import annotations

import streamlit as st

import engine
from ui import careers as careers_ui
from ui import components
from ui import courses as courses_ui
from ui import group as group_ui
from ui import profile_form
from ui import skills_gap as skills_gap_ui

st.set_page_config(page_title="Career Pathways: North East", page_icon="🧭", layout="centered")

st.session_state.setdefault("profile", None)
st.session_state.setdefault("group", None)
st.session_state.setdefault("career", None)

st.title("Career Pathways")
st.write("Find careers in the North East that fit you, see which skills you still need, and find courses to close the gap.")

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
career = careers_ui.render_careers(engine.rank_careers(profile, group, n=5), group)
st.session_state.career = career

if career is not None:
    # 4. Skills gap
    gap = engine.skills_gap(profile, career)
    skills_gap_ui.render_skills_gap(gap, career)

    # 5. Courses
    missing = gap["missing"]
    courses_ui.render_courses(engine.recommend_courses(missing, profile, n=5), missing, career)

# 6. Advisor (placeholder)
components.advisor_placeholder()
components.footer()
