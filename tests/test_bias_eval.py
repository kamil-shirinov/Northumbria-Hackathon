"""The bias eval (python3 -m eval.bias_test) passes on data/ and catches a planted bias."""

import engine
from eval import bias_test


def test_twins_differ_only_in_personal_details():
    pairs = bias_test.build_pairs()
    assert len(pairs) == bias_test.PAIRS == 20
    assert pairs == bias_test.build_pairs()  # seeded, so repeatable
    for base, twin in pairs:
        for key in ("name", "gender", "postcode", "town"):
            assert base[key] != twin[key]
        rest = lambda p: {k: v for k, v in p.items() if k not in ("name", "gender", "postcode", "town")}
        assert rest(base) == rest(twin)


def test_bias_eval_passes_on_the_data():
    identical, differences = bias_test.run()
    assert differences == []
    assert identical == 20


def test_bias_eval_catches_a_planted_bias(monkeypatch, capsys):
    real = engine.rank_careers

    def biased(profile, group, n=5):
        careers = real(profile, group, n)
        return careers[::-1] if profile.get("gender") == "female" else careers

    monkeypatch.setattr(engine, "rank_careers", biased)
    assert bias_test.main() == 1
    out = capsys.readouterr().out
    assert "Bias test: " in out and "/20 pairs identical" in out
    assert "rank_careers differs" in out
