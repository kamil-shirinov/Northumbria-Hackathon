"""The grounding eval writes mock runs to grounding_mock.md and only live runs to grounding.md,
so a cloud session (no key) can never overwrite the demo laptop's live results."""

import advisor
from eval import grounding_test


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
