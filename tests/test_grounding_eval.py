"""The grounding eval writes mock runs to grounding_mock.md and only live runs to grounding.md,
so a cloud session (no key) can never overwrite the demo laptop's live results."""

from types import SimpleNamespace

import pytest

import advisor
from eval import grounding_test
from tests.test_advisor import LIVE_FLAGS, MOCK_FLAGS


def test_results_path_by_mode():
    assert grounding_test.results_path("live") == grounding_test.RESULTS_LIVE
    assert grounding_test.results_path("mock") == grounding_test.RESULTS_MOCK
    assert grounding_test.RESULTS_LIVE.name == "grounding.md"
    assert grounding_test.RESULTS_MOCK.name == "grounding_mock.md"


def test_mock_run_writes_only_the_mock_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MOCK_LLM", "1")
    live_file, mock_file = tmp_path / "grounding.md", tmp_path / "grounding_mock.md"
    monkeypatch.setattr(grounding_test, "RESULTS_LIVE", live_file)
    monkeypatch.setattr(grounding_test, "RESULTS_MOCK", mock_file)
    monkeypatch.setattr(grounding_test, "HERE", tmp_path)
    advisor.reset()
    assert grounding_test.main() == 0
    assert mock_file.exists() and not live_file.exists()
    assert "MOCK MODE" in mock_file.read_text(encoding="utf-8")
    assert capsys.readouterr().out.startswith("Grounding: ")


@pytest.mark.parametrize("flag, expected", [(f, "mock") for f in MOCK_FLAGS] + [(f, "live") for f in LIVE_FLAGS] + [(None, "live")])
def test_eval_file_follows_mock_llm_with_a_key(monkeypatch, flag, expected):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    if flag is None:
        monkeypatch.delenv("MOCK_LLM", raising=False)
    else:
        monkeypatch.setenv("MOCK_LLM", flag)
    assert advisor.mode() == expected
    want = grounding_test.RESULTS_LIVE if expected == "live" else grounding_test.RESULTS_MOCK
    assert grounding_test.results_path(advisor.mode()) == want


@pytest.mark.parametrize("flag", MOCK_FLAGS + LIVE_FLAGS + [None])
def test_eval_file_is_mock_without_a_key(monkeypatch, flag):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    if flag is None:
        monkeypatch.delenv("MOCK_LLM", raising=False)
    else:
        monkeypatch.setenv("MOCK_LLM", flag)
    assert grounding_test.results_path(advisor.mode()) == grounding_test.RESULTS_MOCK


class _FakeClient:
    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        text = "I'm not sure. The National Careers Service can help."
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))


@pytest.mark.parametrize("flag", ["false", "0", "No", ""])
def test_live_run_writes_only_the_live_file(tmp_path, monkeypatch, flag):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("MOCK_LLM", flag)
    client = _FakeClient()
    monkeypatch.setattr(advisor, "_get_client", lambda: client)
    live_file, mock_file = tmp_path / "grounding.md", tmp_path / "grounding_mock.md"
    monkeypatch.setattr(grounding_test, "RESULTS_LIVE", live_file)
    monkeypatch.setattr(grounding_test, "RESULTS_MOCK", mock_file)
    monkeypatch.setattr(grounding_test, "HERE", tmp_path)
    advisor.reset()
    try:
        assert grounding_test.main() == 0
    finally:
        advisor.reset()
    assert live_file.exists() and not mock_file.exists()
    assert client.calls == grounding_test.N_QUESTIONS
    assert "MOCK MODE" not in live_file.read_text(encoding="utf-8")
