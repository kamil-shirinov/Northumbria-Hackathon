"""Smoke test: app.py runs top to bottom in demo mode without an exception.

Skips when app.py isn't present (as on backend before frontend is merged in).
"""

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app.py"


@pytest.mark.skipif(not APP.exists(), reason="app.py is not on this branch")
def test_app_runs_without_an_exception(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "1")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
