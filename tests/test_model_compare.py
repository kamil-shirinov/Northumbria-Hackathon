"""eval/model_compare.py: config parsing, the spend cap, the winner rule and full runs with a
fake client (no network, no key). Uses tests/fixtures, so it passes whatever data/ holds."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import advisor
import engine
from eval import model_compare as mc

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def fixture_data():
    engine.reload_data(FIXTURES)
    advisor.reset()
    yield
    advisor.reset()
    engine.reload_data()


class ModelAwareClient:
    """Haiku's first answer cites an ID that isn't in the results; its regeneration and every
    Sonnet answer cite the first career in the results. Tokens per call are configurable."""

    def __init__(self, input_tokens=1000, output_tokens=100):
        self.calls = []
        self.messages = self
        self.tokens = (input_tokens, output_tokens)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        first = len(kwargs["messages"]) == 1
        career = re.search(r'"id":"(CAR\d+)"', kwargs["system"]).group(1)
        if kwargs["model"] == mc.HAIKU and first:
            text = "Try Rocket pilot [CAR99]."
        else:
            text = f"Start with [{career}], the top career in your results."
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=self.tokens[0], output_tokens=self.tokens[1]),
        )


@pytest.fixture
def live_client(monkeypatch):
    monkeypatch.delenv("MOCK_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    def install(**kwargs):
        client = ModelAwareClient(**kwargs)
        monkeypatch.setattr(advisor, "_get_client", lambda: client)
        return client

    return install


# --------------------------------------------------------------------------- config parsing


def test_the_three_configs():
    assert [(c.name, c.model, c.regen_model) for c in mc.CONFIGS] == [
        ("haiku", "claude-haiku-5-5", "claude-haiku-5-5"),
        ("sonnet", "claude-sonnet-5-5", "claude-sonnet-5-5"),
        ("cascade", "claude-haiku-5-5", "claude-sonnet-5-5"),
    ]


@pytest.mark.parametrize("text, names", [
    (None, ["haiku", "sonnet", "cascade"]),
    ("", ["haiku", "sonnet", "cascade"]),
    (" , ", ["haiku", "sonnet", "cascade"]),
    ("cascade", ["cascade"]),
    ("Cascade, HAIKU ", ["haiku", "cascade"]),
    ("sonnet,sonnet", ["sonnet"]),
])
def test_parse_configs(text, names):
    assert [c.name for c in mc.parse_configs(text)] == names


def test_parse_configs_rejects_unknown_names():
    with pytest.raises(ValueError, match="opus"):
        mc.parse_configs("haiku,opus")


def test_cli_rejects_unknown_configs():
    with pytest.raises(SystemExit):
        mc.main(["--configs", "gpt"])


# --------------------------------------------------------------------------- cost and spend cap


def test_prices_and_cost():
    assert mc.PRICES == {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}
    assert mc.cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert mc.cost_usd("claude-sonnet-5-5", 1000, 100) == pytest.approx(0.003)
    assert mc.cost_usd("some-new-model", 1_000_000, 0) == pytest.approx(2.00)  # priced as the dearest
    assert mc.SPEND_CAP_USD == 1.50


def test_spend_guard_uses_the_prior_then_the_dearest_answer_seen():
    guard = mc.SpendGuard(cap=0.02)
    sonnet = mc.CONFIGS[1]
    assert guard.estimate(sonnet) == pytest.approx(0.012)  # 4000 in + 400 out on Sonnet
    assert guard.allows(sonnet)
    guard.add(sonnet, 0.004)
    guard.add(sonnet, 0.001)
    assert guard.estimate(sonnet) == pytest.approx(0.004) and guard.spent == pytest.approx(0.005)
    assert guard.allows(sonnet)  # 0.005 + 0.004 <= 0.02
    guard.add(sonnet, 0.01)
    assert not guard.allows(sonnet)  # 0.015 + 0.01 > 0.02
    assert not mc.SpendGuard(cap=0.01).allows(sonnet)  # the prior alone is over


def test_run_stops_before_the_cap_and_every_config_answers_the_same_questions(live_client):
    client = live_client(input_tokens=20_000, output_tokens=400)
    # Per answer: haiku (+ haiku regen) $0.0044, sonnet $0.044, cascade $0.0462 → $0.0946 a round.
    # Round 3 fits haiku and sonnet ($0.2376) but not cascade (+$0.0462 > $0.25).
    report = mc.run(cap=0.25)
    assert report["stopped_at"] == "P2-ordinary (cascade)"
    assert report["spent"] == pytest.approx(0.2376) and report["spent"] <= 0.25
    assert [len(report["rows"][c.name]) for c in mc.CONFIGS] == [3, 3, 2]
    assert len(client.calls) == 3 * 2 + 3 * 1 + 2 * 2


def test_zero_cap_asks_nothing(live_client, tmp_path):
    client = live_client()
    report = mc.run(cap=0.0)
    assert client.calls == [] and report["stopped_at"] == "P1-ordinary (haiku)"
    assert all(s["grounded"] == 0 and s["answers"] == 0 for s in report["summaries"])
    text = mc.write_report(report, tmp_path / "r.md").read_text(encoding="utf-8")
    assert "Stopped early" in text and "not run (spend cap)" in text


# --------------------------------------------------------------------------- winner rule


def _summary(name, grounded, fairness, cost):
    return {"config": name, "grounded": grounded, "fairness_passed": fairness, "cost_per_answer": cost}


def test_winner_most_grounded_first():
    assert mc.pick_winner([_summary("a", 15, 6, 0.001), _summary("b", 16, 2, 0.05)]) == "b"


def test_winner_then_most_fairness_passes():
    assert mc.pick_winner([_summary("a", 16, 5, 0.001), _summary("b", 16, 6, 0.05)]) == "b"


def test_winner_then_lowest_cost_per_answer():
    assert mc.pick_winner([_summary("a", 16, 6, 0.01), _summary("b", 16, 6, 0.002)]) == "b"


def test_winner_full_tie_goes_to_the_first_listed_and_none_for_no_configs():
    assert mc.pick_winner([_summary("a", 16, 6, 0.0), _summary("b", 16, 6, 0.0)]) == "a"
    assert mc.pick_winner([]) is None
    assert mc.pick_winner([_summary("a", 0, 0, float("inf")), _summary("b", 0, 0, 0.0)]) == "b"


def test_fairness_pass_rule():
    base = {"mentioned_ids": ["CAR01", "CRS02"], "closed_door_final": False}
    assert mc.fairness_pass(base, {**base, "mentioned_ids": ["CRS02", "CAR01"]})
    assert not mc.fairness_pass(base, {**base, "mentioned_ids": ["CAR01"]})
    assert not mc.fairness_pass(base, {**base, "closed_door_final": True})


# --------------------------------------------------------------------------- personas and pairs


def test_personas_cover_all_groups_and_several_towns_with_no_personal_data():
    personas = mc.build_personas()
    assert len(personas) == 8
    groups = {engine.assign_group(p["profile"]) for p in personas}
    assert groups == {"no_quals", "gcse", "level3", "graduate", "career_changer"}
    assert len({p["profile"]["town"] for p in personas}) >= 5
    allowed = {"qualification", "has_experience", "experience_years", "interests", "skills", "town"}
    for p in personas:
        assert set(p["profile"]) == allowed
        assert p["profile"]["interests"] and p["profile"]["skills"]


def test_tasks_16_persona_answers_and_6_pairs_differing_only_in_the_attribute():
    tasks = mc.build_tasks()
    persona = [t for t in tasks if t["kind"] == "persona"]
    fairness = [t for t in tasks if t["kind"] == "fairness"]
    assert len(persona) == 16 and len(fairness) == 12
    assert sum(t["question"] == mc.ORDINARY_QUESTION for t in persona) == 8
    awkward = set(mc.read_questions())
    assert all(t["question"] in awkward for t in persona if t["id"].endswith("awkward"))
    attributes = [t["attribute"] for t in fairness[::2]]
    assert attributes == ["gender", "age", "ethnicity", "disability", "area", "religion"]
    for a, b, pair in zip(fairness[::2], fairness[1::2], mc.FAIRNESS_PAIRS):
        assert a["context"] is b["context"] and a["profile"] is b["profile"]
        town = a["profile"]["town"]
        va, vb = (v.format(town=town) for v in pair["variants"])
        assert a["question"].replace(va, "X") == b["question"].replace(vb, "X")
        assert a["question"] != b["question"]


# --------------------------------------------------------------------------- full runs


def test_full_live_run_with_a_fake_client(live_client, tmp_path):
    client = live_client(input_tokens=1000, output_tokens=100)
    report = mc.run()
    assert report["run_mode"] == "live" and report["stopped_at"] is None
    s = {x["config"]: x for x in report["summaries"]}

    # Every config answered all 28; Haiku's first answers were regenerated by the regen model.
    assert all(x["answers"] == 28 and x["persona_answers"] == 16 for x in s.values())
    assert s["haiku"]["regenerations"] == 16 and s["cascade"]["regenerations"] == 16
    assert s["sonnet"]["regenerations"] == 0
    assert all(x["grounded"] == 16 and x["fairness_passed"] == 6 for x in s.values())
    assert set(s["haiku"]["by_model"]) == {mc.HAIKU}
    assert set(s["sonnet"]["by_model"]) == {mc.SONNET}
    assert s["cascade"]["by_model"] == {
        mc.HAIKU: {"calls": 28, "input_tokens": 28_000, "output_tokens": 2_800},
        mc.SONNET: {"calls": 28, "input_tokens": 28_000, "output_tokens": 2_800},
    }
    regen_models = [c["model"] for c in client.calls if len(c["messages"]) == 3]
    assert regen_models.count(mc.SONNET) == 28 and regen_models.count(mc.HAIKU) == 28

    # Same call settings as the app: thinking off (between_tools on Sonnet), effort low, no temperature.
    assert all(c["thinking"] == ({"type": "between_tools"} if c["model"] == mc.SONNET else {"type": "disabled"})
               and c["output_config"] == {"effort": "low"}
               and "temperature" not in c for c in client.calls)

    # Cost: haiku 2×$0.00015, sonnet $0.003, cascade $0.00315 per answer → haiku wins on cost.
    assert s["haiku"]["cost_per_answer"] == pytest.approx(0.0003)
    assert s["sonnet"]["cost_per_answer"] == pytest.approx(0.003)
    assert s["cascade"]["cost_per_answer"] == pytest.approx(0.00315)
    assert report["winner"] == "haiku"
    assert report["spent"] == pytest.approx(28 * (0.0003 + 0.003 + 0.00315))
    assert s["sonnet"]["latency_max_s"] >= s["sonnet"]["latency_median_s"] >= 0

    # The module's models are restored after the run.
    assert (advisor.MODEL, advisor.REGEN_MODEL) == ("claude-sonnet-5-5", "claude-sonnet-5-5")

    text = mc.write_report(report, tmp_path / "model_comparison.md").read_text(encoding="utf-8")
    assert "MOCK MODE" not in text and "**Winner: haiku**" in text
    assert "## Persona answers" in text and "## Fairness pairs" in text
    assert len(re.findall(r"^\| P\d-", text, re.M)) == 16 and len(re.findall(r"^\| F\d[ab] ", text, re.M)) == 12
    assert "regenerated (first: [CAR99])" in text


def test_fairness_failure_is_detected(live_client):
    client = live_client()

    def create(**kwargs):
        client.calls.append(kwargs)
        question = kwargs["messages"][0]["content"]
        text = "Start with [CAR01]." if "I'm a man" in question else "That is not possible for you."
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn",
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))

    client.create = create
    report = mc.run(mc.parse_configs("sonnet"))
    (summary,) = report["summaries"]
    assert summary["fairness"][0] is False


def test_mock_run_writes_only_the_mock_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MOCK_LLM", "1")
    live_file, mock_file = tmp_path / "model_comparison.md", tmp_path / "model_comparison_mock.md"
    monkeypatch.setattr(mc, "RESULTS_LIVE", live_file)
    monkeypatch.setattr(mc, "RESULTS_MOCK", mock_file)
    assert mc.main([]) == 0
    assert mock_file.exists() and not live_file.exists()
    text = mock_file.read_text(encoding="utf-8")
    assert "MOCK MODE" in text and "**Winner: haiku**" in text
    assert capsys.readouterr().out.startswith("Winner: haiku")


def test_results_paths():
    assert mc.results_path("live").name == "model_comparison.md"
    assert mc.results_path("mock").name == "model_comparison_mock.md"
    gitignore = (Path(__file__).resolve().parent.parent / ".gitignore").read_text(encoding="utf-8")
    assert "eval/results/model_comparison_mock.md" in gitignore.splitlines()
    assert "eval/results/model_comparison.md" not in gitignore.splitlines()
