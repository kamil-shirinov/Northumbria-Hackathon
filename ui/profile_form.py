"""Section 1: the profile form. Collects answers only; it makes no decisions."""

from __future__ import annotations

import streamlit as st

import engine

from ui import components

_YES, _NO = "Yes", "No"
_PENDING_KEY = "pf_example_profile"  # an example profile waiting to be returned on the next run
_MAX_YEARS = 60  # the form's own upper limit for years of experience
_EXAMPLES_PER_ROW = 3


def _build_profile(qualification, worked: bool, years, interests, skills, town) -> dict:
    """The one place a profile (CONTRACT v1) is built, for the form and for the examples."""
    return {
        "qualification": qualification,
        "has_experience": worked,
        "experience_years": int(years) if worked else 0,
        "interests": list(interests),
        "skills": list(skills),
        "town": town or "",
    }


def _pick(items: list, start: int, count: int) -> list:
    """Up to `count` distinct items from `items`, starting at `start` and wrapping round. [] if no items."""
    if not items:
        return []
    return [items[(start + k) % len(items)] for k in range(min(count, len(items)))]


def build_examples(options: dict) -> list[dict]:
    """One example profile per group, built only from `options` (the engine.form_options() lists).

    Nothing here names a skill, interest or town: they are picked by position from the lists the engine
    returns now, so the examples keep working when the data changes. Each example is checked against
    engine.assign_group and dropped if the engine would not put it in that group.
    Returns [{"group": id, "label": str, "profile": dict}].
    """
    qualification_ids = [q["id"] for q in options.get("qualifications") or []]
    if not qualification_ids:
        return []
    interests = options.get("interests") or []
    skills = options.get("skills") or []
    towns = options.get("towns") or []

    examples = []
    for index, group in enumerate(options.get("groups") or []):
        group_id = group["id"]
        if group_id in qualification_ids:
            tries = [(group_id, 0)]  # this qualification, no work experience
        else:
            # A group that is not a qualification (career changer): the first qualification and the fewest
            # years the engine accepts, so this does not depend on the engine's threshold.
            tries = [(qualification_ids[0], years) for years in range(1, _MAX_YEARS + 1)]
        for qualification, years in tries:
            profile = _build_profile(
                qualification,
                years > 0,
                years,
                _pick(interests, index, 2),
                _pick(skills, index * 2, 3),
                towns[index % len(towns)] if towns else "",
            )
            if engine.assign_group(profile) == group_id:
                examples.append({"group": group_id, "label": group.get("label") or group_id, "profile": profile})
                break
    return examples


def _apply_example(profile: dict) -> None:
    """Button callback. Runs before the next script run, so it may set the form's widget state."""
    st.session_state["pf_qualification"] = profile["qualification"]
    st.session_state["pf_has_experience"] = _YES if profile["has_experience"] else _NO
    st.session_state["pf_experience_years"] = profile["experience_years"]
    st.session_state["pf_interests"] = list(profile["interests"])
    st.session_state["pf_skills"] = list(profile["skills"])
    st.session_state["pf_town"] = profile["town"] or None
    st.session_state[_PENDING_KEY] = profile


def _describe(profile: dict, qualification_labels: dict) -> str:
    """Plain text for the button's tooltip, so the user can see what the example contains."""
    parts = [qualification_labels.get(profile["qualification"], profile["qualification"])]
    if profile["has_experience"]:
        parts.append(f"{profile['experience_years']} years of work experience")
    else:
        parts.append("no work experience")
    if profile["interests"]:
        parts.append("interested in " + ", ".join(profile["interests"]))
    if profile["skills"]:
        parts.append("skills: " + ", ".join(profile["skills"]))
    return components.escape("; ".join(parts))


def _render_examples(options: dict, qualification_labels: dict) -> None:
    examples = build_examples(options)
    if not examples:
        return
    st.markdown("**Want to see how it works first?** Try an example. It fills in the form and shows its results.")
    for start in range(0, len(examples), _EXAMPLES_PER_ROW):
        row = examples[start : start + _EXAMPLES_PER_ROW]
        for column, example in zip(st.columns(_EXAMPLES_PER_ROW), row):
            column.button(
                example["label"],
                key=f"pf_example_{example['group']}",
                on_click=_apply_example,
                args=(example["profile"],),
                help=_describe(example["profile"], qualification_labels),
                use_container_width=True,
            )


def render_profile_form() -> dict | None:
    """Draw the form. Returns the profile (CONTRACT v1) on the run it is submitted or an example is chosen, otherwise None."""
    options = engine.form_options()

    st.header("1. Your profile")
    st.caption("Answer a few questions. It takes about a minute.")
    st.caption("We don't ask for your name, age, gender, ethnicity, contact details or postcode.")

    qualifications = options.get("qualifications") or []
    if not qualifications:
        st.error("The form couldn't load its list of qualifications. Please refresh the page and try again.")
        return None
    qualification_labels = {q["id"]: q["label"] for q in qualifications}

    _render_examples(options, qualification_labels)

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
            max_value=_MAX_YEARS,
            step=1,  # starts at min_value (0); no `value=` here because an example sets this widget's state
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

    # An example was chosen on this run: the form above is already filled in, so use its profile as submitted.
    example = st.session_state.pop(_PENDING_KEY, None)
    if example is not None:
        return example

    if not submitted:
        return None
    if qualification is None:
        st.error("Please choose your highest qualification, then press “Show my careers” again.")
        return None

    return _build_profile(qualification, has_experience == _YES, years, interests, skills, town)
