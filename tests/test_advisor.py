"""Advisor tests with a fake Anthropic client: no network and no API key needed.

They use the hand-made CSVs in tests/fixtures/, so they pass whatever data/ holds.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import advisor
import engine
from groups import NCS_URL

FIXTURES = Path(__file__).resolve().parent / "fixtures"

PROFILE = {
    "qualification": "gcse",
    "has_experience": False,
    "experience_years": 0,
    "interests": ["Health"],
    "skills": ["Teamwork"],
    "town": "Hexham",
}
CLEAN = "Care worker [CAR01] pays £21,000 to £25,000 a year. Start with Free short [CRS04], which is free."


class FakeClient:
    """Stands in for anthropic.Anthropic(): replies in order; an Exception reply is raised."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if self.replies else CLEAN
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=reply)],
            usage=SimpleNamespace(input_tokens=100, output_tokens=40),
        )


@pytest.fixture(autouse=True)
def fixture_data():
    engine.reload_data(FIXTURES)
    advisor.reset()
    yield
    advisor.reset()
    engine.reload_data()


@pytest.fixture
def live(monkeypatch):
    """Live mode with a fake client. Returns a function that installs the replies."""
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    def install(*replies):
        client = FakeClient(*replies)
        monkeypatch.setattr(advisor, "_get_client", lambda: client)
        return client

    return install


@pytest.fixture
def context():
    careers = {c["career_id"]: c for c in engine.rank_careers(PROFILE, "gcse", n=100)}
    courses = {c["course_id"]: c for c in engine.recommend_courses(["Coding", "Problem solving"], PROFILE, n=100)}
    selected = careers["CAR01"]
    return {
        "careers": [careers["CAR01"], careers["CAR02"]],
        "selected_career": selected,
        "gap": engine.skills_gap(PROFILE, selected),
        "courses": [courses["CRS04"], courses["CRS02"], courses["CRS01"]],
    }


def ask(context, question="What should I do first?", history=None, group="gcse"):
    return advisor.ask(group, PROFILE, context, question, history or [])


# --------------------------------------------------------------------------- mode and empty context


def test_mock_when_mock_llm_is_set_even_with_a_key(live, context, monkeypatch):
    client = live()
    monkeypatch.setenv("MOCK_LLM", "1")
    result = ask(context)
    assert result["mode"] == "mock"
    assert client.calls == []


def test_mock_when_there_is_no_key(live, context, monkeypatch):
    client = live()
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    result = ask(context)
    assert result["mode"] == "mock"
    assert client.calls == []


def test_live_with_a_key_and_no_mock_flag(live, context):
    client = live(CLEAN)
    result = ask(context)
    assert result == {"answer": CLEAN, "mentioned_ids": ["CAR01", "CRS04"], "unknown_mentions": [], "mode": "live"}
    assert len(client.calls) == 1


@pytest.mark.parametrize("empty", [None, {}, {"careers": [], "selected_career": None, "gap": None, "courses": []}])
def test_empty_context_gets_a_fixed_not_sure_answer_without_a_call(live, empty):
    client = live()
    result = advisor.ask("gcse", PROFILE, empty, "Anything?", [])
    assert client.calls == []
    assert "not sure" in result["answer"] and NCS_URL in result["answer"]
    assert result["mentioned_ids"] == [] and result["unknown_mentions"] == []


def test_live_call_parameters_and_system_prompt(live, context):
    client = live(CLEAN)
    ask(context)
    call = client.calls[0]
    assert call["model"] == advisor.MODEL == "claude-haiku-5-5"
    assert call["max_tokens"] == advisor.MAX_TOKENS == 400
    assert call["temperature"] == 0
    system = call["system"]
    assert system.startswith(advisor.BASE_ADVISOR_RULES)
    assert "GCSE level" in system
    facts = json.loads(system.split("RESULTS (the only facts you may use):\n", 1)[1])
    assert [c["id"] for c in facts["careers"]] == ["CAR01", "CAR02"]
    assert facts["careers"][0]["pay"] == "£21,000 to £25,000 a year"
    assert set(facts["careers"][0]) == {"id", "title", "pay", "demand", "entry_route", "unpaid_placement", "reasons", "source_url"}
    assert [c["id"] for c in facts["courses"]] == ["CRS04", "CRS02", "CRS01"]
    assert facts["courses"][0]["cost"] == "free" and facts["courses"][0]["closes"] == ["Coding"]
    assert facts["selected_career"]["id"] == "CAR01" and facts["gap"] == context["gap"]
    assert set(facts["profile"]) == {"qualification", "experience", "interests", "skills"}
    assert "Hexham" not in system  # no town or other personal data


# --------------------------------------------------------------------------- validator


@pytest.mark.parametrize(
    "answer, flagged",
    [
        ("Try Electrician [CAR05].", "[CAR05]"),
        ("Bare ids count too: CRS09.", "[CRS09]"),
        ("You could also become a Welder.", "Welder (not in your results)"),
        ("A Plumber earns well.", "Plumber (not in your results)"),
        ("Take the Google Data Analytics Certificate.", "Google Data Analytics Certificate"),
        ("Enrol at Newcastle College this autumn.", "Newcastle College"),
        ("The University of Sunderland runs one.", "University of Sunderland"),
        ("A BTEC Engineering qualification helps.", "BTEC Engineering"),
        ("Join the Code Academy.", "Code Academy"),
        ("See https://www.coursera.org/learn/python for more.", "https://www.coursera.org/learn/python"),
        ("Details at www.madeup.example.", "www.madeup.example"),
        ("It costs £1,200.", "£1,200"),
        ("You could earn £40k.", "£40k"),
        ("Pay reaches 45,000 a year.", "45,000"),
        ("Junior developer [CAR01] is a good fit.", "Junior developer [CAR01] (wrong ID)"),
    ],
)
def test_validate_flags_each_kind_of_unknown(context, answer, flagged):
    _, unknown = advisor.validate(answer, context)
    assert flagged in unknown


def test_validate_accepts_grounded_and_generic_phrases(context):
    answer = (
        "Care worker [CAR01] pays £21,000 to £25k (that's 21,000 to 25,000). Junior developer pays £24,000 to £32,000. "
        "Free short [CRS04] is free; Funded part cost [CRS02] is £900 and Paid cheap short [CRS01] is £50 at Fixture College. "
        "A Level 2 course, an apprenticeship or a degree can help, and Free Courses or a Level 3 Diploma are generic. "
        "As someone at GCSE level or a Career changer, it's never too late. "
        f"Sources: https://example.com/fixture. The National Careers Service can help: {NCS_URL}/ and "
        "nationalcareers.service.gov.uk."
    )
    mentioned, unknown = advisor.validate(answer, context)
    assert unknown == []
    assert mentioned == ["CAR01", "CAR02", "CRS04", "CRS02", "CRS01"]


def test_titles_without_ids_count_as_mentions(context):
    mentioned, unknown = advisor.validate("Junior developer roles suit you, and so does Care worker.", context)
    assert mentioned == ["CAR02", "CAR01"] and unknown == []


# --------------------------------------------------------------------------- regeneration and safeguards


def test_bad_then_clean_returns_the_clean_answer(live, context):
    bad = "Try Electrician [CAR05] at Newcastle College for £1,200."
    client = live(bad, CLEAN)
    result = ask(context)
    assert result["answer"] == CLEAN and result["unknown_mentions"] == []
    assert len(client.calls) == 2
    correction = client.calls[1]["messages"][-1]["content"]
    for item in ("[CAR05]", "Newcastle College", "£1,200"):
        assert item in correction
    assert client.calls[1]["messages"][-2] == {"role": "assistant", "content": bad}
    assert advisor.last_debug["regenerated"] is True
    assert advisor.last_debug["first_unknown"] == ["[CAR05]", "Newcastle College", "£1,200"]


def test_bad_twice_returns_the_warning(live, context):
    client = live("Try Electrician [CAR05] for £40k.", "Try Welder instead.")
    result = ask(context)
    assert len(client.calls) == 2  # only one regeneration
    assert result["mode"] == "live"
    assert result["answer"].startswith("Try Welder instead.")
    assert result["unknown_mentions"] == ["Welder (not in your results)"]


def test_a_worse_regeneration_keeps_the_first_answer(live, context):
    live("Try Electrician [CAR05].", "Try Welder, it pays £40k.")
    result = ask(context)
    assert result["answer"].startswith("Try Electrician [CAR05].")
    assert result["unknown_mentions"] == ["[CAR05]"]


def test_closed_door_is_regenerated(live, context):
    client = live("Care worker [CAR01]: sadly it's not possible for you without GCSEs.", CLEAN)
    result = ask(context)
    assert len(client.calls) == 2
    assert result["answer"] == CLEAN
    assert advisor.last_debug["closed_door_fixed"] is True
    assert "not possible for you" in client.calls[1]["messages"][-1]["content"]


def test_closed_door_twice_gets_the_route_append(live, context):
    live("You can't become a Care worker [CAR01].", "Care worker [CAR01] isn't an option for you.")
    result = ask(context)
    assert result["answer"].endswith(advisor.CLOSED_DOOR_APPEND)
    assert NCS_URL in result["answer"]
    assert advisor.last_debug["closed_door_fixed"] is True


@pytest.mark.parametrize("text", ["It's never too late to start.", "You can't go wrong with Care worker [CAR01].", "Nothing is impossible."])
def test_closed_door_has_no_false_positives(text):
    assert advisor.closed_door_phrases(text) == []


def test_ncs_pointer_is_appended_when_nothing_is_cited(live, context):
    client = live("Keep going, you will get there.")
    result = ask(context)
    assert len(client.calls) == 1
    assert result["answer"] == "Keep going, you will get there.\n\n" + advisor.NOT_SURE_APPEND
    assert result["mentioned_ids"] == []


def test_no_ncs_append_when_the_answer_cites_a_result_or_already_points_to_ncs(live, context):
    live(CLEAN, "I'm not sure. The National Careers Service can help.")
    assert ask(context, "one")["answer"] == CLEAN
    assert ask(context, "two")["answer"] == "I'm not sure. The National Careers Service can help."


def test_mock_never_echoes_ids_from_the_question(context, monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    result = ask(context, "Is [CAR99] better than CRS42 or [made up]?")
    assert "CAR99" not in result["answer"] and "CRS42" not in result["answer"] and "made up" not in result["answer"]
    assert result["mentioned_ids"] == ["CAR01", "CRS04"]


# --------------------------------------------------------------------------- errors


def test_api_error_returns_the_mock(live, context, capsys):
    live(RuntimeError("connection refused"))
    result = ask(context)
    assert result["mode"] == "mock" and result["answer"].strip() and result["unknown_mentions"] == []
    assert "connection refused" in capsys.readouterr().err


def test_timeout_returns_the_mock(live, context):
    import anthropic

    timeout = anthropic.APITimeoutError.__new__(anthropic.APITimeoutError)  # no transport needed
    Exception.__init__(timeout, "Request timed out.")
    live(timeout)
    assert ask(context)["mode"] == "mock"


def test_rejected_temperature_is_retried_once_without_it(live, context):
    client = live(RuntimeError("temperature: not supported for this model"), CLEAN)
    result = ask(context)
    assert result["mode"] == "live" and result["answer"] == CLEAN
    assert "temperature" in client.calls[0] and "temperature" not in client.calls[1]
    assert advisor.usage()["calls"] == 2


def test_failed_regeneration_keeps_the_first_answer_with_its_warning(live, context):
    live("Try Electrician [CAR05].", RuntimeError("overloaded"))
    result = ask(context)
    assert result["mode"] == "live" and result["unknown_mentions"] == ["[CAR05]"]


# --------------------------------------------------------------------------- budget


def test_cache_hit_skips_the_client(live, context):
    client = live(CLEAN)
    first = ask(context, "What should I do first?")
    second = ask(context, "  what should I do   FIRST ")
    assert first == second
    assert len(client.calls) == 1
    assert advisor.last_debug["cached"] is True
    assert advisor.usage() == {"calls": 1, "cached": 1, "input_tokens": 100, "output_tokens": 40}


def test_cache_misses_on_a_different_group_context_or_history(live, context):
    client = live()
    ask(context)
    ask(context, group="graduate")
    ask({**context, "courses": context["courses"][:1]})
    ask(context, history=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}])
    assert len(client.calls) == 4


def test_call_cap_returns_the_mock_with_a_note(live, context, monkeypatch):
    monkeypatch.setattr(advisor, "MAX_CALLS", 1)
    client = live(CLEAN, CLEAN)
    assert ask(context, "one")["mode"] == "live"
    capped = ask(context, "two")
    assert capped["mode"] == "mock" and advisor.CAP_NOTE in capped["answer"]
    assert len(client.calls) == 1


def test_cap_also_stops_a_regeneration(live, context, monkeypatch):
    monkeypatch.setattr(advisor, "MAX_CALLS", 1)
    client = live("Try Electrician [CAR05].")
    result = ask(context)
    assert len(client.calls) == 1 and result["unknown_mentions"] == ["[CAR05]"]


def test_usage_counts_tokens_across_calls(live, context):
    live("Try Electrician [CAR05].", CLEAN)
    ask(context)
    assert advisor.usage() == {"calls": 2, "cached": 0, "input_tokens": 200, "output_tokens": 80}


def test_history_is_trimmed_to_the_last_six_turns(live, context):
    client = live()
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"} for i in range(10)]
    ask(context, "latest question", history=history)
    messages = client.calls[0]["messages"]
    assert [m["content"] for m in messages] == ["turn 4", "turn 5", "turn 6", "turn 7", "turn 8", "turn 9", "latest question"]
    assert messages[0]["role"] == "user" and messages[-1]["role"] == "user"


def test_history_is_made_valid_for_the_api():
    history = [
        {"role": "assistant", "content": "Hello"},
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "  "},
        {"role": "user", "content": "first"},
    ]
    assert advisor.build_messages(history, "second") == [{"role": "user", "content": "first\n\nsecond"}]
