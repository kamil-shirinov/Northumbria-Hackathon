"""Bias test: personal details must never change the engine's output.

Run from the repo root against whatever is in data/:

    python3 -m eval.bias_test

Builds 20 base profiles with random.Random(42) from engine.form_options(), gives each a
twin that differs only in a made-up name, gender, postcode and town, then compares
assign_group, rank_careers, skills_gap for the top career and recommend_courses for that
gap. Prints "Bias test: X/20 pairs identical", lists any differences, and exits 1 if any.
"""

from __future__ import annotations

import random
import sys

import engine

SEED = 42
PAIRS = 20

# Made-up details only: no real people.
NAMES = ["Test Person A", "Test Person B", "Sample User C", "Example Learner D", "Demo Profile E", "Fictional F"]
GENDERS = ["female", "male", "non-binary", "prefer not to say"]
POSTCODES = ["NE1 1AA", "SR1 1ZZ", "DH1 9XX", "TS1 2YY", "DL1 3QQ", "NE46 4ZZ"]


def _other(rng: random.Random, choices: list[str], current: str) -> str:
    return rng.choice([c for c in choices if c != current])


def build_pairs(seed: int = SEED, pairs: int = PAIRS) -> list[tuple[dict, dict]]:
    rng = random.Random(seed)
    options = engine.form_options()
    qualifications = [q["id"] for q in options["qualifications"]]
    out = []
    for _ in range(pairs):
        has_experience = rng.random() < 0.5
        base = {
            "qualification": rng.choice(qualifications),
            "has_experience": has_experience,
            "experience_years": rng.randint(1, 10) if has_experience else 0,
            "interests": rng.sample(options["interests"], rng.randint(0, min(3, len(options["interests"])))),
            "skills": rng.sample(options["skills"], rng.randint(0, min(5, len(options["skills"])))),
            "town": rng.choice(options["towns"]),
            "name": rng.choice(NAMES),
            "gender": rng.choice(GENDERS),
            "postcode": rng.choice(POSTCODES),
        }
        twin = {
            **base,
            "interests": list(base["interests"]),
            "skills": list(base["skills"]),
            "name": _other(rng, NAMES, base["name"]),
            "gender": _other(rng, GENDERS, base["gender"]),
            "postcode": _other(rng, POSTCODES, base["postcode"]),
            "town": _other(rng, options["towns"], base["town"]),
        }
        out.append((base, twin))
    return out


def outputs(profile: dict) -> dict:
    group = engine.assign_group(profile)
    careers = engine.rank_careers(profile, group)
    gap = engine.skills_gap(profile, careers[0])
    return {
        "assign_group": group,
        "rank_careers": careers,
        "skills_gap": gap,
        "recommend_courses": engine.recommend_courses(gap["missing"], profile),
    }


def run(seed: int = SEED, pairs: int = PAIRS) -> tuple[int, list[str]]:
    """Return (identical pair count, one line per difference)."""
    identical = 0
    differences = []
    for i, (base, twin) in enumerate(build_pairs(seed, pairs), start=1):
        a, b = outputs(base), outputs(twin)
        changed = [key for key in a if a[key] != b[key]]
        if not changed:
            identical += 1
        for key in changed:
            differences.append(
                f"Pair {i}: {key} differs ({base['name']}, {base['gender']}, {base['postcode']}, {base['town']} "
                f"vs {twin['name']}, {twin['gender']}, {twin['postcode']}, {twin['town']}): {a[key]!r} != {b[key]!r}"
            )
    return identical, differences


def main() -> int:
    identical, differences = run()
    print(f"Bias test: {identical}/{PAIRS} pairs identical")
    for line in differences:
        print(f"  - {line}")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
