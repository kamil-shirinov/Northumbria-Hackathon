"""Tests of CONTRACT v1 (see CLAUDE.md). They must pass on placeholder AND real data,
so nothing here may depend on a particular career, course or skill name."""

import copy
import csv
import os
from pathlib import Path

import pytest

import advisor
import engine
from groups import CAREER_CHANGER_MIN_YEARS, GROUPS, NCS_URL, NE_TOWNS, QUALIFICATIONS

DATA_DIR = Path(os.environ.get("CP_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")

CAREER_KEYS = {
    "career_id", "title", "sector", "ne_demand", "pay_min", "pay_max", "entry_route",
    "unpaid_placement", "skills", "source_url", "score", "reasons",
}
COURSE_KEYS = {
    "course_id", "title", "provider", "cost_gbp", "funded", "free_or_funded", "length_weeks",
    "format", "entry_requirements", "skills_taught", "closes", "unpaid_placement", "source_url",
}
ANSWER_KEYS = {"answer", "mentioned_ids", "unknown_mentions", "mode"}
PERSONAL = {"name": "Alex Example", "gender": "non-binary", "age": 41, "postcode": "NE1 1AA", "ethnicity": "prefer not to say"}


def read_csv(name):
    with open(DATA_DIR / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def split(cell):
    return [s.strip() for s in cell.split(";") if s.strip()]


def assert_plain(value, path="value"):
    """Only str, int, float, bool, None, list and dict: never pandas or numpy types."""
    assert type(value) in (str, int, float, bool, type(None), list, dict), f"{path} is {type(value)}"
    if isinstance(value, list):
        for i, item in enumerate(value):
            assert_plain(item, f"{path}[{i}]")
    elif isinstance(value, dict):
        for k, v in value.items():
            assert type(k) is str, f"{path} key {k!r}"
            assert_plain(v, f"{path}[{k!r}]")


@pytest.fixture(scope="module")
def options():
    return engine.form_options()


def make_profile(options, **overrides):
    """A profile with some interests and skills taken from the real option lists."""
    profile = {
        "qualification": "gcse",
        "has_experience": False,
        "experience_years": 0,
        "interests": options["interests"][:1],
        "skills": options["skills"][:2],
        "town": "Durham",
    }
    profile.update(overrides)
    return profile


PROFILES = [
    {"qualification": "no_quals", "has_experience": False, "experience_years": 0, "interests": [], "skills": [], "town": "Sunderland"},
    {"qualification": "gcse", "has_experience": True, "experience_years": 1, "interests": ["Not a real sector"], "skills": ["not a real skill"], "town": "Hexham"},
    {"qualification": "level3", "has_experience": True, "experience_years": 5, "interests": [], "skills": [], "town": "Durham"},
    {"qualification": "graduate", "has_experience": False, "experience_years": 0, "interests": [], "skills": [], "town": "Other North East"},
]


# --------------------------------------------------------------------------- form_options


def test_form_options_keys_and_types(options):
    assert set(options) == {"qualifications", "groups", "interests", "skills", "towns"}
    assert_plain(options)
    assert options["qualifications"] == [{"id": k, "label": v} for k, v in QUALIFICATIONS.items()]
    assert [g["id"] for g in options["groups"]] == list(GROUPS)
    for g in options["groups"]:
        assert set(g) == {"id", "label", "description"}
        assert all(isinstance(g[k], str) and g[k] for k in g)
    assert options["towns"] == NE_TOWNS


def test_form_options_lists_match_the_csv(options):
    careers = read_csv("careers.csv")
    sectors = {r["sector"].strip().casefold() for r in careers}
    skills = {s.casefold() for r in careers for s in split(r["skills"])}
    for key, expected in (("interests", sectors), ("skills", skills)):
        listed = options[key]
        assert listed and listed == sorted(listed)
        assert {x.casefold() for x in listed} == expected
        assert len({x.casefold() for x in listed}) == len(listed), f"{key} has duplicates"


# --------------------------------------------------------------------------- assign_group


@pytest.mark.parametrize("qualification", list(QUALIFICATIONS))
def test_assign_group_follows_qualification(qualification):
    for has_experience, years in ((False, 0), (True, 1), (True, CAREER_CHANGER_MIN_YEARS - 1)):
        profile = {"qualification": qualification, "has_experience": has_experience, "experience_years": years}
        assert engine.assign_group(profile) == qualification


@pytest.mark.parametrize("qualification", list(QUALIFICATIONS))
def test_assign_group_career_changer_rule(qualification):
    assert CAREER_CHANGER_MIN_YEARS == 3
    for years in (3, 4, 20):
        profile = {"qualification": qualification, "has_experience": True, "experience_years": years}
        assert engine.assign_group(profile) == "career_changer"
    # years without has_experience never count
    profile = {"qualification": qualification, "has_experience": False, "experience_years": 10}
    assert engine.assign_group(profile) == qualification


def test_assign_group_always_returns_a_known_group():
    assert engine.assign_group({}) in GROUPS
    assert engine.assign_group({"qualification": "???"}) in GROUPS


# --------------------------------------------------------------------------- rank_careers


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("group", list(GROUPS))
def test_rank_careers_shape(profile, group):
    expected = min(5, len(read_csv("careers.csv")))
    careers = engine.rank_careers(profile, group)
    assert len(careers) == expected
    assert_plain(careers)
    for c in careers:
        assert set(c) == CAREER_KEYS
        assert c["ne_demand"] in ("high", "medium", "low")
        assert isinstance(c["pay_min"], int) and isinstance(c["pay_max"], int) and c["pay_min"] <= c["pay_max"]
        assert isinstance(c["entry_route"], str) and c["entry_route"].strip()
        assert isinstance(c["source_url"], str) and c["source_url"].startswith("http")
        assert isinstance(c["unpaid_placement"], bool)
        assert isinstance(c["score"], float) and 0.0 <= c["score"] <= 100.0
        assert c["score"] == round(c["score"], 1)
        assert c["skills"] and all(isinstance(s, str) for s in c["skills"])
        assert c["reasons"] and all(isinstance(r, str) and r for r in c["reasons"])
    assert len({c["career_id"] for c in careers}) == len(careers)
    assert [c["score"] for c in careers] == sorted((c["score"] for c in careers), reverse=True)


def test_rank_careers_n_and_unknown_group(options):
    profile = make_profile(options)
    total = len(read_csv("careers.csv"))
    assert len(engine.rank_careers(profile, "gcse", n=2)) == min(2, total)
    assert len(engine.rank_careers(profile, "gcse", n=total + 10)) == total
    assert len(engine.rank_careers(profile, "gcse", n=0)) == 1  # never empty
    assert engine.rank_careers(profile, "nonsense") == engine.rank_careers(profile, engine.assign_group(profile))


def test_rank_careers_puts_an_interest_first(options):
    for sector in options["interests"]:
        profile = make_profile(options, interests=[sector], skills=[])
        top = engine.rank_careers(profile, "gcse", n=1)[0]
        assert top["sector"] == sector
        assert top["reasons"][0] == f"In your chosen area: {sector}"


def test_entry_route_comes_from_the_groups_column():
    careers = {r["career_id"]: r for r in read_csv("careers.csv")}
    for group in GROUPS:
        for c in engine.rank_careers({"qualification": "gcse"}, group, n=100):
            cell = careers[c["career_id"]][f"entry_route_{group}"].strip()
            if cell:
                assert c["entry_route"] == cell
            else:
                assert c["entry_route"].startswith("Longer route:") and NCS_URL in c["entry_route"]


# --------------------------------------------------------------------------- skills_gap


@pytest.mark.parametrize("profile", PROFILES)
def test_skills_gap_splits_the_careers_skills(profile):
    for career in engine.rank_careers(profile, "gcse", n=100):
        gap = engine.skills_gap(profile, career)
        assert set(gap) == {"have", "missing"}
        assert_plain(gap)
        assert len(gap["have"]) + len(gap["missing"]) == len(career["skills"])
        assert set(gap["have"]) | set(gap["missing"]) == set(career["skills"])
        assert not set(gap["have"]) & set(gap["missing"])
        # each list keeps the career's skill order
        assert gap["have"] == [s for s in career["skills"] if s in gap["have"]]
        assert gap["missing"] == [s for s in career["skills"] if s in gap["missing"]]


def test_skills_gap_ignores_case_and_spaces_and_takes_an_id():
    career = engine.rank_careers({}, "gcse", n=1)[0]
    skills = career["skills"]
    shouting = {"skills": [f"  {s.upper()} " for s in skills]}
    assert engine.skills_gap(shouting, career) == {"have": skills, "missing": []}
    assert engine.skills_gap({"skills": []}, career) == {"have": [], "missing": skills}
    assert engine.skills_gap({}, career["career_id"]) == {"have": [], "missing": skills}
    with pytest.raises(ValueError):
        engine.skills_gap({}, "NOPE99")


# --------------------------------------------------------------------------- recommend_courses


def expected_course_ids(missing):
    """Oracle: the contract's ordering, worked out straight from courses.csv."""
    wanted = {m.strip().casefold() for m in missing}
    scored = []
    for r in read_csv("courses.csv"):
        closes = len(wanted & {s.casefold() for s in split(r["skills_taught"])})
        if closes:
            cost, weeks = float(r["cost_gbp"]), float(r["length_weeks"])
            free_or_funded = cost == 0 or r["funded"].strip() == "yes"
            scored.append(((-closes, not free_or_funded, cost, weeks, r["course_id"]), r["course_id"]))
    return [cid for _, cid in sorted(scored)]


def test_recommend_courses_shape_and_order(options):
    missing = options["skills"]
    everything = engine.recommend_courses(missing, make_profile(options), n=1000)
    assert_plain(everything)
    for c in everything:
        assert set(c) == COURSE_KEYS
        assert c["closes"] and set(c["closes"]) <= set(missing)
        assert isinstance(c["cost_gbp"], float) and c["cost_gbp"] >= 0
        assert isinstance(c["length_weeks"], float) and c["length_weeks"] > 0
        assert isinstance(c["funded"], bool) and isinstance(c["free_or_funded"], bool)
        assert c["free_or_funded"] == (c["cost_gbp"] == 0 or c["funded"])
        assert c["source_url"].startswith("http")
    assert [c["course_id"] for c in everything] == expected_course_ids(missing)
    assert [c["course_id"] for c in engine.recommend_courses(missing, {}, n=2)] == expected_course_ids(missing)[:2]


def test_recommend_courses_only_closes_missing_skills(options):
    skill = options["skills"][0]
    for c in engine.recommend_courses([skill.upper()], {}, n=1000):
        assert c["closes"] == [skill.upper()]  # echoes the caller's spelling
        assert skill.casefold() in {s.casefold() for s in c["skills_taught"]}
    assert [c["course_id"] for c in engine.recommend_courses([skill], {}, n=1000)] == expected_course_ids([skill])


def test_recommend_courses_returns_empty_when_nothing_closes():
    assert engine.recommend_courses([], {}) == []
    assert engine.recommend_courses(["a skill nobody teaches"], {}) == []


def test_recommend_courses_order_holds_for_each_courses_own_skills():
    # Asking for exactly what one course teaches exercises the tie-breaks between similar courses.
    for r in read_csv("courses.csv"):
        skills = split(r["skills_taught"])
        courses = engine.recommend_courses(skills, {}, n=1000)
        assert [c["course_id"] for c in courses] == expected_course_ids(skills)
        assert r["course_id"] in {c["course_id"] for c in courses}


# --------------------------------------------------------------------------- personal data


@pytest.mark.parametrize("profile", PROFILES)
def test_personal_keys_and_town_never_change_engine_output(profile):
    noisy = {**copy.deepcopy(profile), **PERSONAL, "town": "Other North East", "unknown_key": [1, 2, 3]}

    def everything(p):
        group = engine.assign_group(p)
        out = {"group": group, "options": engine.form_options()}
        for g in GROUPS:
            careers = engine.rank_careers(p, g, n=100)
            out[g] = {
                "careers": careers,
                "gaps": [engine.skills_gap(p, c) for c in careers],
                "courses": [engine.recommend_courses(engine.skills_gap(p, c)["missing"], p, n=100) for c in careers],
            }
        return out

    assert everything(noisy) == everything(profile)


# --------------------------------------------------------------------------- advisor


def build_context(options, profile=None):
    profile = profile or make_profile(options)
    group = engine.assign_group(profile)
    careers = engine.rank_careers(profile, group)
    gap = engine.skills_gap(profile, careers[0])
    return profile, group, {
        "careers": careers,
        "selected_career": careers[0],
        "gap": gap,
        "courses": engine.recommend_courses(gap["missing"], profile),
    }


def all_ids():
    return {r["career_id"] for r in read_csv("careers.csv")} | {r["course_id"] for r in read_csv("courses.csv")}


def test_advisor_mock_answer_has_every_key_and_only_real_ids(options, monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    profile, group, context = build_context(options)
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    result = advisor.ask(group, profile, context, "What should I do first?", history)
    assert set(result) == ANSWER_KEYS
    assert_plain(result)
    assert result["mode"] == "mock"
    assert result["unknown_mentions"] == []
    assert result["answer"].strip()
    assert result["mentioned_ids"], "the answer should name the career"
    assert set(result["mentioned_ids"]) <= all_ids()
    for item_id in result["mentioned_ids"]:
        assert f"[{item_id}]" in result["answer"]
    assert "What should I do first?" in result["answer"]
    assert NCS_URL in result["answer"]


def test_advisor_mock_names_the_selected_career_pay_and_a_free_or_funded_course(options, monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    profile, group, context = build_context(options)
    selected = context["careers"][-1]
    context["selected_career"] = selected
    context["courses"] = engine.recommend_courses(options["skills"], profile, n=1000)
    assert context["courses"], "the data should have at least one course that teaches a career skill"
    result = advisor.ask(group, profile, context, "Tell me more", [])
    assert result["mentioned_ids"][0] == selected["career_id"]
    assert f"£{selected['pay_min']:,}" in result["answer"] and f"£{selected['pay_max']:,}" in result["answer"]
    first_free = next((c for c in context["courses"] if c["free_or_funded"]), context["courses"][0])
    assert result["mentioned_ids"][1] == first_free["course_id"]


@pytest.mark.parametrize("context", [{}, {"careers": [], "selected_career": None, "gap": None, "courses": []}, None])
def test_advisor_still_answers_with_an_empty_context(context, monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    result = advisor.ask("gcse", {}, context, "Anything?", [])
    assert set(result) == ANSWER_KEYS
    assert result["mode"] == "mock"
    assert result["answer"].strip()
    assert NCS_URL in result["answer"]
    assert result["mentioned_ids"] == [] and result["unknown_mentions"] == []


def test_advisor_constants():
    assert advisor.DEFAULT_MODEL == "claude-sonnet-5-5"
    assert advisor.models_from_env({}) == ("claude-sonnet-5-5", "claude-sonnet-5-5")
    assert advisor.MAX_TOKENS == 400


# --------------------------------------------------------------------------- engine rules on synthetic data
# These use their own tiny CSVs, so they pin down the rules whatever the real data says.

CAREER_COLS = [
    "career_id", "title", "sector", "ne_demand", "pay_min", "pay_max", "entry_route_no_quals", "entry_route_gcse",
    "entry_route_level3", "entry_route_graduate", "entry_route_career_changer", "skills", "source_url",
]
COURSE_COLS = [
    "course_id", "title", "provider", "cost_gbp", "funded", "length_weeks", "format", "entry_requirements",
    "skills_taught", "source_url",
]


@pytest.fixture()
def synthetic(tmp_path, monkeypatch):
    careers = [
        # blank gcse route -> "Longer route"; UNPAID in the level3 route (any case)
        ["CAR01", "Alpha job", "Sector A", "low", "20000", "21000", "route nq", "", "Placement is UNPAID", "route g", "route cc", " Cooking ; Cleaning ;Cooking", "http://a"],
        ["CAR02", "Beta job", "Sector B", "high", "20000", "21000", "r", "r", "r", "r", "r", "Cooking", "http://b"],
        ["CAR03", "Gamma job", "Sector B", "medium", "20000", "21000", "r", "r", "r", "r", "r", "Cooking;Cleaning;Driving", "http://c"],
        ["CAR04", "Delta job", "Sector A", "high", "20000", "21000", "r", "r", "r", "r", "r", "Cooking;Cleaning", "http://d"],
    ]
    courses = [
        ["CRS01", "Plain course", "P", "0", "no", "4", "Online", "None", "cooking", "http://x"],
        ["CRS02", "Placement course", "P", "100", "yes", "4", "Includes an unpaid placement", "None", "Cleaning", "http://y"],
        ["CRS03", "Paid both", "P", "50", "no", "2", "Online", "None", "Cooking;Cleaning", "http://z"],
        ["CRS04", "Funded both", "P", "900", "yes", "30", "Online", "None", "Cooking;Cleaning", "http://w"],
    ]
    for name, header, rows in (("careers.csv", CAREER_COLS, careers), ("courses.csv", COURSE_COLS, courses)):
        with open(tmp_path / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    monkeypatch.setenv("CP_DATA_DIR", str(tmp_path))
    engine.reload_data()
    yield
    monkeypatch.undo()
    engine.reload_data()


def test_synthetic_blank_route_becomes_a_longer_route(synthetic):
    careers = {c["career_id"]: c for c in engine.rank_careers({}, "gcse", n=10)}
    route = careers["CAR01"]["entry_route"]
    assert route.startswith("Longer route:") and NCS_URL in route
    assert careers["CAR01"]["unpaid_placement"] is False
    assert careers["CAR02"]["entry_route"] == "r"


def test_synthetic_unpaid_placement_is_detected_in_routes_and_courses(synthetic):
    careers = {c["career_id"]: c for c in engine.rank_careers({}, "level3", n=10)}
    assert careers["CAR01"]["unpaid_placement"] is True
    assert careers["CAR02"]["unpaid_placement"] is False
    courses = {c["course_id"]: c for c in engine.recommend_courses(["Cooking", "Cleaning"], {}, n=10)}
    assert courses["CRS02"]["unpaid_placement"] is True
    assert courses["CRS01"]["unpaid_placement"] is False


def test_synthetic_skills_are_split_trimmed_deduplicated_and_matched_loosely(synthetic):
    career = {c["career_id"]: c for c in engine.rank_careers({}, "gcse", n=10)}["CAR01"]
    assert career["skills"] == ["Cooking", "Cleaning"]
    assert engine.skills_gap({"skills": ["  COOKING"]}, "CAR01") == {"have": ["Cooking"], "missing": ["Cleaning"]}


def test_synthetic_rank_order_follows_the_weighted_score(synthetic):
    assert engine.WEIGHTS == {"interest": 60, "skills": 25, "demand": 15}
    profile = {"interests": ["sector b "], "skills": ["Cooking"]}
    ranked = engine.rank_careers(profile, "gcse", n=10)
    # Sector B is an interest (matched ignoring case and spaces):
    #   CAR02 60 + 25*1/1 + 15*1 = 100.0, CAR03 60 + 25*1/3 + 15*0.5 = 75.8
    # Sector A is not: CAR04 25*1/2 + 15*1 = 27.5, CAR01 25*1/2 + 0 = 12.5
    assert [(c["career_id"], c["score"]) for c in ranked] == [
        ("CAR02", 100.0), ("CAR03", 75.8), ("CAR04", 27.5), ("CAR01", 12.5),
    ]
    # No interests: CAR02 40.0, CAR04 27.5, CAR03 25/3 + 7.5 = 15.8, CAR01 12.5.
    ranked = engine.rank_careers({"skills": ["Cooking"]}, "gcse", n=10)
    assert [(c["career_id"], c["score"]) for c in ranked] == [
        ("CAR02", 40.0), ("CAR04", 27.5), ("CAR03", 15.8), ("CAR01", 12.5),
    ]


def test_synthetic_course_order_and_closes(synthetic):
    courses = engine.recommend_courses(["Cooking", "Cleaning"], {}, n=10)
    # Closing both skills beats closing one. Between the two that close both, funded CRS04 beats
    # paid CRS03 even though it costs more and takes longer. Between the two that close one, both
    # are free or funded, so the cheaper free CRS01 comes first.
    assert [c["course_id"] for c in courses] == ["CRS04", "CRS03", "CRS01", "CRS02"]
    assert courses[0]["closes"] == ["Cooking", "Cleaning"]
    assert engine.recommend_courses(["Cooking"], {}, n=10)[0]["course_id"] == "CRS01"
    assert len(engine.recommend_courses(["Cooking", "Cleaning"], {}, n=2)) == 2
