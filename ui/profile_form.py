"""Section 1: the profile form. Collects answers only; it makes no decisions."""

from __future__ import annotations

import streamlit as st

import engine

_YES, _NO = "Yes", "No"


def render_profile_form() -> dict | None:
    """Draw the form. Returns the profile (CONTRACT v1) on the run it is submitted, otherwise None."""
    options = engine.form_options()

    st.header("1. Your profile")
    st.caption("Answer a few questions. It takes about a minute.")
    st.caption("We don't ask for your name, age, gender, ethnicity, contact details or postcode.")

    qualifications = options.get("qualifications") or []
    if not qualifications:
        st.error("The form couldn't load its list of qualifications. Please refresh the page and try again.")
        return None
    qualification_labels = {q["id"]: q["label"] for q in qualifications}

    with st.form("profile_form"):
        qualification = st.selectbox(
            "What is your highest qualification?",
            list(qualification_labels),
            index=None,
            format_func=qualification_labels.get,
            placeholder="Choose one",
            key="pf_qualification",
        )
        has_experience = st.radio(
            "Do you have any work experience?",
            [_NO, _YES],
            horizontal=True,
            key="pf_has_experience",
        )
        years = st.number_input(
            "If yes, how many years in total?",
            min_value=0,
            max_value=60,
            value=0,
            step=1,
            help="Round down to whole years. Leave at 0 if you answered No.",
            key="pf_experience_years",
        )
        interests = st.multiselect(
            "Which kinds of work interest you?",
            options.get("interests") or [],
            placeholder="Pick as many as you like, or none",
            key="pf_interests",
        )
        skills = st.multiselect(
            "Which of these skills do you already have?",
            options.get("skills") or [],
            placeholder="Pick as many as you like, or none",
            help="Count skills from work, study, volunteering or everyday life.",
            key="pf_skills",
        )
        town = st.selectbox(
            "Which North East town are you in? (optional)",
            options.get("towns") or [],
            index=None,
            placeholder="Choose a town",
            help="This doesn't change which careers we show you.",
            key="pf_town",
        )
        submitted = st.form_submit_button("Show my careers", type="primary")

    if not submitted:
        return None
    if qualification is None:
        st.error("Please choose your highest qualification, then press “Show my careers” again.")
        return None

    worked = has_experience == _YES
    return {
        "qualification": qualification,
        "has_experience": worked,
        "experience_years": int(years) if worked else 0,
        "interests": list(interests),
        "skills": list(skills),
        "town": town or "",
    }
