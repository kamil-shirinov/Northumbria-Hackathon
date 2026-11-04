"""Engine rules pinned down on hand-made CSVs in tests/fixtures/, whatever data/ holds.

Fixture careers (sector, demand, skills):
  CAR01 Care worker       Health       high    Communication;Teamwork;Safeguarding;First aid
  CAR02 Junior developer  Tech         medium  Coding;Problem solving;Teamwork
  CAR03 Welder            Engineering  low     Welding;Health and safety;Technical drawing;Problem solving;Teamwork
  CAR04 Data analyst      Tech         low     Data analysis;Spreadsheets;Communication;Problem solving;Teamwork
  CAR05 Electrician       Engineering  high    Wiring;Fault finding
  CAR06 Plumber           Engineering  high    Plumbing;Fault finding   (same score as CAR05 for the id tie-break)
Fixture courses all teach Coding (CRS08 also teaches Problem solving); see courses.csv.
"""

import random
from pathlib import Path

import pytest

import engine
from groups import GROUPS, QUALIFICATIONS

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ALL = 100  # more than the fixture holds


@pytest.fixture(autouse=True)
def fixture_data():
    engine.reload_data(FIXTURES)
    yield
    engine.reload_data()


def ranked(profile, group="gcse", n=ALL):
    return engine.rank_careers(profile, group, n=n)


def ids(careers):
    return [c["career_id"] for c in careers]


def by_id(careers):
    return {c["career_id"]: c for c in careers}


# --------------------------------------------------------------------------- scores


def test_exact_scores_and_reasons():
    assert engine.WEIGHTS == {"interest": 60, "skills": 25, "demand": 15}
    profile = {"interests": ["Tech"], "skills": ["Teamwork", "Communication"]}
    careers = ranked(profile)
    found = by_id(careers)
    # CAR02: 60*1 + 25*(1/3) + 15*0.5 = 75.83 -> 75.8
    assert found["CAR02"]["score"] == 75.8
    assert found["CAR02"]["reasons"] == [
        "In your chosen area: Tech",
        "You already have 1 of 3 skills: Teamwork",
        "Medium demand in the North East",
    ]
    # CAR04: 60*1 + 25*(2/5) + 15*0 = 70.0
    assert found["CAR04"]["score"] == 70.0
    assert found["CAR04"]["reasons"] == [
        "In your chosen area: Tech",
        "You already have 2 of 5 skills: Communication, Teamwork",
        "Low demand in the North East",
    ]
    # CAR01: 60*0 + 25*(2/4) + 15*1 = 27.5
    assert found["CAR01"]["score"] == 27.5
    assert found["CAR01"]["reasons"] == [
        "Outside your chosen areas",
        "You already have 2 of 4 skills: Communication, Teamwork",
        "High demand in the North East",
    ]
    assert found["CAR05"]["reasons"][1] == "You have none of its 2 skills yet, but you can build them"
    assert ids(careers) == ["CAR02", "CAR04", "CAR01", "CAR05", "CAR06", "CAR03"]
    assert all(type(c["score"]) is float for c in careers)


def test_skills_reason_names_at_most_three_skills():
    profile = {"skills": ["Welding", "Health and safety", "Technical drawing", "Problem solving", "Teamwork"]}
    welder = by_id(ranked(profile))["CAR03"]
    assert welder["reasons"][1] == "You already have 5 of 5 skills: Welding, Health and safety, Technical drawing"


# --------------------------------------------------------------------------- order


def test_interest_outranks_skills():
    # Every Care worker skill but no interest in Health: 25 + 15 = 40, below any Engineering career (60+).
    profile = {"interests": ["Engineering"], "skills": ["Communication", "Teamwork", "Safeguarding", "First aid"]}
    careers = ranked(profile)
    assert by_id(careers)["CAR01"]["score"] == 40.0
    assert [c["sector"] for c in careers[:3]] == ["Engineering"] * 3
    assert min(c["score"] for c in careers[:3]) > by_id(careers)["CAR01"]["score"]


def test_skills_outrank_demand():
    # All Welder skills at low demand (25.0) beat no skills at high demand (15.0).
    profile = {"skills": ["Welding", "Health and safety", "Technical drawing", "Problem solving", "Teamwork"]}
    careers = ranked(profile)
    found = by_id(careers)
    assert careers[0]["career_id"] == "CAR03"
    assert found["CAR03"]["score"] == 25.0
    assert found["CAR05"]["score"] == 15.0
    assert ids(careers).index("CAR03") < ids(careers).index("CAR05")


def test_tie_breaks_demand_then_career_id():
    # CAR04 holds 3 of 5 skills at low demand: 25*0.6 = 15.0. CAR05 and CAR06 hold none at high demand: 15.0.
    profile = {"skills": ["Data analysis", "Spreadsheets", "Communication"]}
    careers = ranked(profile)
    tied = [c for c in careers if c["score"] == 15.0]
    assert ids(tied) == ["CAR05", "CAR06", "CAR04"]  # high demand before low, then CAR05 before CAR06


def test_no_interests_picked():
    for interests in (None, [], ["", "  "]):
        profile = {"skills": ["Coding"]}
        if interests is not None:
            profile["interests"] = interests
        careers = ranked(profile)
        assert all(c["reasons"][0] == "Pick some interests to tailor this list" for c in careers)
        assert all(c["score"] <= 40.0 for c in careers)
        # CAR02: 25/3 + 7.5 = 15.8 beats the high-demand careers with no skills held (15.0).
        assert careers[0]["career_id"] == "CAR02" and careers[0]["score"] == 15.8


def test_unmatched_interest_says_outside_your_chosen_areas():
    careers = ranked({"interests": ["Not a real sector"]})
    assert all(c["reasons"][0] == "Outside your chosen areas" for c in careers)


# --------------------------------------------------------------------------- fairness


def everything(profile, group=None):
    group = group or engine.assign_group(profile)
    careers = ranked(profile, group)
    gaps = [engine.skills_gap(profile, c) for c in careers]
    return {
        "group": group,
        "careers": careers,
        "gaps": gaps,
        "courses": [engine.recommend_courses(g["missing"], profile, n=ALL) for g in gaps],
    }


def test_shuffled_interests_and_skills_give_identical_output():
    interests = ["Tech", "Health", "Engineering"]
    skills = ["Teamwork", "Coding", "Communication", "Problem solving", "Spreadsheets", "Wiring"]
    base = everything({"qualification": "gcse", "interests": interests, "skills": skills})
    rng = random.Random(7)
    for _ in range(10):
        shuffled_interests, shuffled_skills = interests[:], skills[:]
        rng.shuffle(shuffled_interests)
        rng.shuffle(shuffled_skills)
        profile = {"qualification": "gcse", "interests": shuffled_interests, "skills": shuffled_skills}
        assert everything(profile) == base


def without_route(careers):
    """Everything but the entry route (and the unpaid flag that is read from it)."""
    return [{k: v for k, v in c.items() if k not in ("entry_route", "unpaid_placement")} for c in careers]


def test_qualification_and_group_change_only_the_entry_route():
    profile = {"interests": ["Tech"], "skills": ["Teamwork", "Coding"], "has_experience": False, "experience_years": 0}
    base = without_route(ranked({**profile, "qualification": "gcse"}, "gcse"))
    routes = set()
    for qualification in QUALIFICATIONS:
        for group in GROUPS:
            careers = ranked({**profile, "qualification": qualification}, group)
            assert without_route(careers) == base
            for c in careers:
                assert c["entry_route"] == f"{c['title']} route for {group}"
            routes.add(careers[0]["entry_route"])
    assert len(routes) == len(GROUPS)
    # Experience changes the group, and through it only the entry route too.
    changer = {**profile, "qualification": "no_quals", "has_experience": True, "experience_years": 10}
    assert engine.assign_group(changer) == "career_changer"
    assert without_route(ranked(changer, engine.assign_group(changer))) == base


# --------------------------------------------------------------------------- n


def test_n_larger_than_the_data():
    assert len(ranked({}, n=ALL)) == 6
    assert len(ranked({}, n=6)) == 6
    assert len(ranked({}, n=2)) == 2
    assert len(ranked({}, n=0)) == 1  # never empty
    assert len(engine.recommend_courses(["Coding"], {}, n=ALL)) == 9


# --------------------------------------------------------------------------- courses


def course_ids(missing, n=ALL):
    return [c["course_id"] for c in engine.recommend_courses(missing, {}, n=n)]


def test_course_order_with_equal_closes_across_free_funded_and_paid():
    # All close one skill. Free or funded first (by cost, then weeks, then id), then paid the same way.
    assert course_ids(["Coding"]) == [
        "CRS04", "CRS07",  # free, 4 weeks: id breaks the tie
        "CRS03",           # free, 10 weeks
        "CRS09",           # fully funded (pays 0), 12 weeks
        "CRS05",           # funded, learner pays £200
        "CRS02",           # funded, learner pays £900
        "CRS01",           # paid £50, 2 weeks
        "CRS06",           # paid £50, 8 weeks
        "CRS08",           # paid £500
    ]
    found = {c["course_id"]: c for c in engine.recommend_courses(["Coding"], {}, n=ALL)}
    assert [found[i]["free_or_funded"] for i in ("CRS04", "CRS09", "CRS05", "CRS02", "CRS01")] == [
        True, True, True, True, False,
    ]
    assert course_ids(["Coding"], n=3) == ["CRS04", "CRS07", "CRS03"]


def test_closing_more_skills_beats_free():
    assert course_ids(["Coding", "Problem solving"])[0] == "CRS08"
    assert engine.recommend_courses(["Coding", "Problem solving"], {}, n=1)[0]["closes"] == ["Coding", "Problem solving"]


def test_empty_missing_gives_no_courses():
    assert engine.recommend_courses([], {}) == []
    assert engine.recommend_courses(["Juggling"], {}) == []
