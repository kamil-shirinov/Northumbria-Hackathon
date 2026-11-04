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


def response(*blocks, stop_reason="end_turn", input_tokens=100, output_tokens=40):
    """A fake API response. Each block is ("text", "...") or ("thinking", "...")."""
    content = [
        SimpleNamespace(type=kind, text=body) if kind == "text" else SimpleNamespace(type=kind, thinking=body)
        for kind, body in blocks
    ]
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class BadRequest(Exception):
    """Like anthropic.BadRequestError: carries status_code 400."""

    status_code = 400


class FakeClient:
    """Stands in for anthropic.Anthropic(): replies in order. A str reply becomes one text block,
    an Exception reply is raised and any other reply (see response()) is returned as it is."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if self.replies else CLEAN
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, str):
            return response(("text", reply))
        return reply


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
    assert call["model"] == advisor.MODEL == "claude-sonnet-5-5"
    assert call["max_tokens"] == advisor.MAX_TOKENS == 400
    assert "temperature" not in call
    assert call["thinking"] == {"type": "between_tools"}  # Sonnet 5.5 rejects "disabled"
    assert call["output_config"] == {"effort": "low"}
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


# --------------------------------------------------------------------------- thinking, stop reasons


def test_thinking_then_text_reads_only_the_text_blocks(live, context):
    live(response(("thinking", "Let me look at the results."), ("text", "Care worker [CAR01] pays £21,000 "),
                  ("text", "to £25,000 a year.")))
    result = ask(context)
    assert result["mode"] == "live"
    assert result["answer"].startswith("Care worker [CAR01] pays £21,000 to £25,000 a year.")
    assert "Let me look" not in result["answer"]


def test_max_tokens_with_no_text_retries_once_with_adaptive_thinking(live, context, capsys):
    client = live(response(("thinking", "..."), stop_reason="max_tokens"), CLEAN)
    result = ask(context)
    assert result["mode"] == "live" and result["answer"] == CLEAN
    assert len(client.calls) == 2
    retry = client.calls[1]
    assert retry["thinking"] == {"type": "adaptive"} and retry["output_config"] == {"effort": "low"}
    assert retry["max_tokens"] == advisor.ADAPTIVE_MAX_TOKENS == 2000
    assert "temperature" not in retry
    err = capsys.readouterr().err
    assert "max_tokens" in err and "thinking" in err


def test_max_tokens_twice_falls_back_to_mock_and_logs_why(live, context, capsys):
    client = live(response(("thinking", "..."), stop_reason="max_tokens"),
                  response(("thinking", "..."), stop_reason="max_tokens"))
    assert ask(context)["mode"] == "mock"
    assert len(client.calls) == 2
    err = capsys.readouterr().err
    assert "empty answer" in err and "stop_reason='max_tokens'" in err and "['thinking']" in err


def test_empty_answer_logs_stop_reason_and_block_types(live, context, capsys):
    live(response(("thinking", "hmm"), stop_reason="end_turn"))
    assert ask(context)["mode"] == "mock"
    err = capsys.readouterr().err
    assert "stop_reason='end_turn'" in err and "blocks=['thinking']" in err


def test_refusal_returns_the_safe_answer_in_live_mode(live, context, capsys):
    client = live(response(stop_reason="refusal"))
    result = ask(context)
    assert result == {"answer": advisor.REFUSAL_ANSWER, "mentioned_ids": [], "unknown_mentions": [], "mode": "live"}
    assert "not sure" in result["answer"] and NCS_URL in result["answer"]
    assert len(client.calls) == 1
    assert "refused" in capsys.readouterr().err


def test_refused_regeneration_keeps_the_first_answer(live, context):
    live("Try Electrician [CAR05].", response(stop_reason="refusal"))
    result = ask(context)
    assert result["mode"] == "live" and result["unknown_mentions"] == ["[CAR05]"]


def test_400_on_disabled_thinking_retries_with_adaptive_and_remembers(live, context, monkeypatch):
    client = live(BadRequest("thinking.type: 'disabled' is not supported for this model"), CLEAN, CLEAN, CLEAN)
    result = ask(context, "one")
    assert result["mode"] == "live" and result["answer"] == CLEAN
    assert client.calls[0]["thinking"] == {"type": "between_tools"}
    assert client.calls[1]["thinking"] == {"type": "adaptive"}
    assert client.calls[1]["output_config"] == {"effort": "low"} and client.calls[1]["max_tokens"] == 2000
    ask(context, "two")  # remembered for this model: straight to adaptive
    assert client.calls[2]["thinking"] == {"type": "adaptive"}
    monkeypatch.setattr(advisor, "MODEL", "claude-haiku-5-5")
    ask(context, "three")  # but not for another model
    assert client.calls[3]["thinking"] == {"type": "disabled"} and client.calls[3]["max_tokens"] == 400
    assert advisor.usage()["calls"] == 4


def test_other_400s_are_not_retried(live, context):
    client = live(BadRequest("messages: roles must alternate"))
    assert ask(context)["mode"] == "mock"
    assert len(client.calls) == 1


def test_old_sdk_without_the_arguments_gets_them_in_extra_body(live, context, monkeypatch):
    class OldSDKClient:
        def __init__(self):
            self.calls = []
            self.messages = self

        def create(self, *, model, max_tokens, system, messages, extra_body=None):
            self.calls.append({"model": model, "max_tokens": max_tokens, "extra_body": extra_body})
            return response(("text", CLEAN))

    live()
    client = OldSDKClient()
    monkeypatch.setattr(advisor, "_get_client", lambda: client)
    assert ask(context)["answer"] == CLEAN
    assert client.calls[0]["extra_body"] == {"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}}


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
    assert advisor.usage() == {
        "calls": 1, "cached": 1, "input_tokens": 100, "output_tokens": 40,
        "by_model": {"claude-sonnet-5-5": {"calls": 1, "input_tokens": 100, "output_tokens": 40}},
    }


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
    assert advisor.usage() == {
        "calls": 2, "cached": 0, "input_tokens": 200, "output_tokens": 80,
        "by_model": {"claude-sonnet-5-5": {"calls": 2, "input_tokens": 200, "output_tokens": 80}},
    }


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


def test_the_users_own_words_are_not_flagged(context):
    question = "Should I go to Newcastle College? I earn £18,000 now. Is Welder better? See https://my.example/page"
    answer = (
        "Newcastle College isn't in your results, and nor is Welder. Compared with your £18,000, "
        "Care worker [CAR01] pays £21,000 to £25,000. I can't check https://my.example/page. Electrician [CAR05]?"
    )
    _, unknown = advisor.validate(answer, context, question)
    assert unknown == ["[CAR05]"]  # ids are always checked


def test_live_validation_allows_names_from_the_question(live, context):
    client = live("Newcastle College isn't in your results. Care worker [CAR01] is.")
    result = ask(context, "Should I go to Newcastle College?")
    assert result["unknown_mentions"] == [] and len(client.calls) == 1


# --------------------------------------------------------------------------- MOCK_LLM values

MOCK_FLAGS = ["1", "true", "TRUE", "True", "yes", "YES", "Yes", " yes "]
LIVE_FLAGS = ["0", "false", "FALSE", "False", "no", "NO", "No", "", "  "]


@pytest.mark.parametrize("flag", MOCK_FLAGS)
def test_mock_llm_mock_values_mean_mock_even_with_a_key(live, context, monkeypatch, flag):
    client = live(CLEAN)
    monkeypatch.setenv("MOCK_LLM", flag)
    assert advisor.mode() == "mock"
    assert ask(context)["mode"] == "mock"
    assert client.calls == []


@pytest.mark.parametrize("flag", LIVE_FLAGS)
def test_mock_llm_live_values_mean_live_with_a_key(live, context, monkeypatch, flag):
    client = live(CLEAN)
    monkeypatch.setenv("MOCK_LLM", flag)
    assert advisor.mode() == "live"
    assert ask(context)["mode"] == "live"
    assert len(client.calls) == 1


def test_mock_llm_unset_means_live_with_a_key(live, context):
    live(CLEAN)
    assert advisor.mode() == "live" and ask(context)["mode"] == "live"


@pytest.mark.parametrize("flag", LIVE_FLAGS + [None])
def test_no_key_is_always_mock(live, context, monkeypatch, flag):
    client = live(CLEAN)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    if flag is not None:
        monkeypatch.setenv("MOCK_LLM", flag)
    assert advisor.mode() == "mock" and ask(context)["mode"] == "mock"
    assert client.calls == []


def test_an_unrecognised_mock_llm_value_is_not_mock_and_warns(live, monkeypatch, capsys):
    live()
    monkeypatch.setenv("MOCK_LLM", "maybe")
    monkeypatch.setattr(advisor, "_warned_values", set())
    assert advisor.mode() == "live"
    assert "MOCK_LLM='maybe'" in capsys.readouterr().err


def _assert_valid_for_api(messages):
    assert messages and messages[0]["role"] == "user" and messages[-1]["role"] == "user"
    assert all(a["role"] != b["role"] for a, b in zip(messages, messages[1:]))


def test_trimmed_history_that_starts_with_assistant_drops_it(live, context):
    client = live()
    # 7 alternating turns from user: the last-6 window (turns 1-6) starts on assistant turn 1,
    # which is dropped; turn 6 is a user turn, so it merges with the new question
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"} for i in range(7)]
    ask(context, "latest question", history=history)
    messages = client.calls[0]["messages"]
    _assert_valid_for_api(messages)
    assert [m["content"] for m in messages] == ["turn 2", "turn 3", "turn 4", "turn 5", "turn 6\n\nlatest question"]


@pytest.mark.parametrize("roles", [
    "aaaaaa", "uuuuuu", "auau", "uuaauu", "aauuaa", "uaauua", "auuaau", "uaua", "", "a", "u",
    "uauauauaua", "aaauuu", "uuuaaa",
])
def test_any_history_shape_gives_alternating_messages_ending_with_the_question(roles):
    role = {"u": "user", "a": "assistant"}
    history = [{"role": role[r], "content": f"{r}{i}"} for i, r in enumerate(roles)]
    messages = advisor.build_messages(history, "question")
    _assert_valid_for_api(messages)
    assert messages[-1]["content"].endswith("question")
    # only the last 6 turns are used, and every non-leading-assistant turn in them is kept, in order
    window = history[-advisor.HISTORY_TURNS:]
    while window and window[0]["role"] == "assistant":
        window.pop(0)
    text = "\n\n".join(m["content"] for m in messages)
    assert text == "\n\n".join([t["content"] for t in window] + ["question"])


def test_consecutive_same_role_turns_are_merged():
    history = [
        {"role": "user", "content": "u1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a1"},
        {"role": "assistant", "content": "a2"},
    ]
    assert advisor.build_messages(history, "q") == [
        {"role": "user", "content": "u1\n\nu2"},
        {"role": "assistant", "content": "a1\n\na2"},
        {"role": "user", "content": "q"},
    ]


# --------------------------------------------------------------------------- model configuration


@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, ("claude-sonnet-5-5", "claude-sonnet-5-5")),
        ({"ADVISOR_MODEL": "", "ADVISOR_REGEN_MODEL": "  "}, ("claude-sonnet-5-5", "claude-sonnet-5-5")),
        ({"ADVISOR_MODEL": " claude-haiku-5-5 "}, ("claude-haiku-5-5", "claude-haiku-5-5")),
        ({"ADVISOR_REGEN_MODEL": "claude-haiku-5-5"}, ("claude-sonnet-5-5", "claude-haiku-5-5")),
        ({"ADVISOR_MODEL": "claude-sonnet-5-5", "ADVISOR_REGEN_MODEL": "claude-haiku-5-5"},
         ("claude-sonnet-5-5", "claude-haiku-5-5")),
    ],
)
def test_models_from_env(env, expected):
    assert advisor.models_from_env(env) == expected


def test_models_are_read_from_the_environment_at_import(monkeypatch):
    import importlib

    monkeypatch.setenv("ADVISOR_MODEL", "claude-haiku-5-5")
    monkeypatch.delenv("ADVISOR_REGEN_MODEL", raising=False)
    try:
        importlib.reload(advisor)
        assert (advisor.MODEL, advisor.REGEN_MODEL) == ("claude-haiku-5-5", "claude-haiku-5-5")
    finally:
        monkeypatch.delenv("ADVISOR_MODEL")
        importlib.reload(advisor)
    assert (advisor.MODEL, advisor.REGEN_MODEL) == ("claude-sonnet-5-5", "claude-sonnet-5-5")


def test_regeneration_uses_the_regen_model_and_usage_splits_by_model(live, context, monkeypatch):
    monkeypatch.setattr(advisor, "MODEL", "claude-haiku-5-5")
    monkeypatch.setattr(advisor, "REGEN_MODEL", "claude-sonnet-5-5")
    client = live("Try Electrician [CAR05].", CLEAN)
    result = ask(context)
    assert result["answer"] == CLEAN and result["unknown_mentions"] == []
    assert [c["model"] for c in client.calls] == ["claude-haiku-5-5", "claude-sonnet-5-5"]
    assert advisor.usage()["by_model"] == {
        "claude-haiku-5-5": {"calls": 1, "input_tokens": 100, "output_tokens": 40},
        "claude-sonnet-5-5": {"calls": 1, "input_tokens": 100, "output_tokens": 40},
    }
    calls = advisor.last_debug["calls"]
    assert [(c["model"], c["purpose"], c["ok"]) for c in calls] == [
        ("claude-haiku-5-5", "answer", True), ("claude-sonnet-5-5", "regeneration", True),
    ]
    assert all(isinstance(c["latency_s"], float) and c["latency_s"] >= 0 for c in calls)
    assert calls[0]["input_tokens"] == 100 and calls[0]["output_tokens"] == 40


def test_last_debug_records_a_failed_call(live, context):
    live(RuntimeError("overloaded"))
    assert ask(context)["mode"] == "mock"
    (call,) = advisor.last_debug["calls"]
    assert call["model"] == "claude-sonnet-5-5" and call["ok"] is False and "overloaded" in call["error"]


def test_cached_answer_records_no_calls(live, context):
    live(CLEAN)
    ask(context)
    assert len(advisor.last_debug["calls"]) == 1
    ask(context)
    assert advisor.last_debug["cached"] is True and advisor.last_debug["calls"] == []


def test_cache_is_per_model(live, context, monkeypatch):
    client = live(CLEAN, CLEAN)
    ask(context)
    monkeypatch.setattr(advisor, "MODEL", "claude-haiku-5-5")
    ask(context)
    assert [c["model"] for c in client.calls] == ["claude-sonnet-5-5", "claude-haiku-5-5"]
    assert [c["thinking"] for c in client.calls] == [{"type": "between_tools"}, {"type": "disabled"}]


def test_temperature_is_never_sent(live, context, monkeypatch):
    monkeypatch.setattr(advisor, "REGEN_MODEL", "claude-sonnet-5-5")
    client = live("Try Electrician [CAR05].", CLEAN)
    ask(context)
    assert len(client.calls) == 2 and all("temperature" not in c for c in client.calls)
