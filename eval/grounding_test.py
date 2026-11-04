"""Grounding eval: does the advisor stay inside the engine results?

Run from the repo root against whatever is in data/:

    python3 -m eval.grounding_test

Reads 15 questions from eval/questions.txt, pairs question i with synthetic profile
i % 5 (one per group), builds each context with the engine and calls advisor.ask().
Every answer is re-checked with advisor.validate(), so in mock mode this still catches
validator false positives on the real data. Prints the headline line, writes
eval/results/grounding.md and always exits 0: it reports, it doesn't gate.

Live mode needs ANTHROPIC_API_KEY and MOCK_LLM unset; without a key it runs in mock mode.
"""

from __future__ import annotations

from pathlib import Path

import advisor
import engine

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.txt"
RESULTS = HERE / "results" / "grounding.md"
N_QUESTIONS = 15


def _pick(items: list[str], *indexes: int) -> list[str]:
    """Items at these positions (wrapping), so the profiles work on any data."""
    if not items:
        return []
    out: list[str] = []
    for i in indexes:
        item = items[i % len(items)]
        if item not in out:
            out.append(item)
    return out


def build_profiles() -> list[dict]:
    """Five synthetic profiles, one per group. No names or other personal data."""
    options = engine.form_options()
    interests, skills = options["interests"], options["skills"]
    base = {"has_experience": False, "experience_years": 0, "town": "Other North East"}
    return [
        {**base, "qualification": "no_quals", "interests": _pick(interests, 0), "skills": _pick(skills, 0)},
        {**base, "qualification": "gcse", "interests": _pick(interests, 1), "skills": _pick(skills, 1, 2)},
        {**base, "qualification": "level3", "interests": _pick(interests, 2), "skills": _pick(skills, 3)},
        {**base, "qualification": "graduate", "interests": _pick(interests, 1, 2), "skills": _pick(skills, 4, 5)},
        {
            **base,
            "qualification": "gcse",
            "has_experience": True,
            "experience_years": 10,
            "interests": _pick(interests, 0, 1),
            "skills": _pick(skills, 0, 6, 7),
        },
    ]


def build_context(profile: dict) -> tuple[str, dict]:
    group = engine.assign_group(profile)
    careers = engine.rank_careers(profile, group)
    selected = careers[0]
    gap = engine.skills_gap(profile, selected)
    courses = engine.recommend_courses(gap["missing"], profile)
    return group, {"careers": careers, "selected_career": selected, "gap": gap, "courses": courses}


def read_questions() -> list[str]:
    lines = [line.strip() for line in QUESTIONS.read_text(encoding="utf-8").splitlines()]
    questions = [line for line in lines if line and not line.startswith("#")]
    return questions[:N_QUESTIONS]


def _cell(text: str) -> str:
    return " ".join(str(text).replace("|", "\\|").split("\n")).replace("  ", " ").strip() or "–"


def run() -> dict:
    questions = read_questions()
    profiles = build_profiles()
    rows = []
    for i, question in enumerate(questions):
        profile = profiles[i % len(profiles)]
        group, context = build_context(profile)
        result = advisor.ask(group, profile, context, question, [])
        debug = dict(advisor.last_debug)
        # Re-check the final answer too: in mock mode this tests the validator on real data.
        _, recheck = advisor.validate(result["answer"], context, question)
        flags = list(dict.fromkeys(result["unknown_mentions"] + recheck))
        closed = bool(debug.get("closed_door_fixed")) or bool(advisor.closed_door_phrases(result["answer"]))
        rows.append(
            {
                "question": question,
                "group": group,
                "mode": result["mode"],
                "flags": flags,
                "regenerated": bool(debug.get("regenerated")),
                "first_unknown": debug.get("first_unknown") or [],
                "closed_door": closed,
                "answer": result["answer"],
            }
        )

    used = advisor.usage()
    clean = sum(1 for r in rows if not r["flags"])
    summary = {
        "clean": clean,
        "total": len(rows),
        "regenerations": sum(r["regenerated"] for r in rows),
        "closed_door": sum(r["closed_door"] for r in rows),
        "calls": used["calls"],
        "input_tokens": used["input_tokens"],
        "output_tokens": used["output_tokens"],
        "live": sum(r["mode"] == "live" for r in rows),
    }
    summary["headline"] = (
        f"Grounding: {clean}/{len(rows)} answers with no unknown mentions · "
        f"regenerations: {summary['regenerations']} · closed-door phrases: {summary['closed_door']} · "
        f"calls: {summary['calls']} · tokens in/out: {summary['input_tokens']}/{summary['output_tokens']}"
    )
    return {"summary": summary, "rows": rows}


def write_report(report: dict, path: Path = RESULTS) -> None:
    s, rows = report["summary"], report["rows"]
    lines = ["# Grounding eval", "", f"**{s['headline']}**", ""]
    if s["live"] < s["total"]:
        lines += [
            f"> **MOCK MODE** ({s['total'] - s['live']}/{s['total']} answers are templates, not Claude). "
            "Without ANTHROPIC_API_KEY, or with MOCK_LLM=1, or after an API error, the advisor returns a template "
            "built from the results. This run checks the pipeline and the validator's false positives on the "
            "current data, not the model. Run it with the key for the real grounding score.",
            "",
        ]
    lines += [
        f"Model `{advisor.MODEL}`, max_tokens {advisor.MAX_TOKENS}. Questions from `eval/questions.txt`, "
        "one synthetic profile per group, contexts built by the engine. Flags = unknown mentions in the final answer.",
        "",
        "| # | Question | Group | Mode | Flags | Answer |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        notes = []
        if r["flags"]:
            notes.append("unknown: " + "; ".join(r["flags"]))
        if r["regenerated"]:
            notes.append("regenerated (first: " + ("; ".join(r["first_unknown"]) or "closed-door phrase") + ")")
        if r["closed_door"]:
            notes.append("closed-door phrase fixed")
        lines.append(
            f"| {i} | {_cell(r['question'])} | {r['group']} | {r['mode']} | {_cell(', '.join(notes) or 'none')} "
            f"| {_cell(r['answer'])} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = run()
    print(report["summary"]["headline"])
    write_report(report)
    print(f"Wrote {RESULTS.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
