<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/brand/root-logo-dark.svg"><img src="assets/brand/root-logo.svg" alt="Root" width="260"></picture></p>

# Root

Many people leave the North East because they can't see a route into the careers on their doorstep. Root turns a short profile into local careers that fit, the skills still missing and the courses that close the gap, with an AI advisor that can only explain what our code found.

## Demo flow

1. **Profile**: qualification, work experience, interests, skills and town. No names.
2. **Group**: set from the profile (career changer with 3+ years of experience, otherwise by qualification). The user can change it.
3. **Top 5 careers**: match score, reasons, typical pay, the route in for their group, a source link.
4. **Skills gap**: the career's skills you have and the ones you're missing.
5. **Courses**: only courses that close a missing skill.
6. **Advisor**: follow-up questions about those results.

## How it works: "models read, code judges"

**`engine.py`** is deterministic. No LLM makes a decision.
- Score (0–100) = `WEIGHTS`: interest 60 × (1 if the career's sector is one you picked) + skills 25 × (career skills you hold ÷ career skills) + demand 15 × (high 1, medium 0.5, low 0). Interest outweighs skills plus demand.
- Ties: higher score, then higher demand, then `career_id`.
- Skills gap: the career's skills split into have and missing, ignoring case.
- Courses must close at least one missing skill. Order: most missing skills closed, then free or funded, then cheaper, then shorter, then `course_id`.

**`advisor.py`** only explains the engine's results.
- The validator checks every answer against those results and `data/*.csv`: unknown IDs, careers or courses not in the results, invented named courses, colleges and qualifications, links that aren't a source link, and £ figures that aren't a listed pay or cost.
- An unknown mention or a closed-door phrase ("not possible for you") triggers one regeneration. The answer with fewer flags wins, and the UI warns about anything left.
- Enforced in code, whatever the model wrote: a surviving closed-door phrase gets a "There's always a route" line added, and an answer that cites nothing and doesn't mention the National Careers Service (NCS) gets an NCS pointer.
- Any API error or timeout falls back to a template answer, so the demo never crashes.

```text
profile ─▶ engine.py (no LLM) ─▶ group · top 5 careers · skills gap · courses
                                              │ results = the only facts allowed
question ─▶ advisor.py ─▶ Claude ─▶ validator vs data/*.csv ─▶ answer + warnings
                                       └─ unknown mention or closed door: regenerate once
```

## Safeguards and fairness

| Safeguard | Where the code enforces it |
| --- | --- |
| No closed doors | `tests/test_data.py` (every route filled, never "not possible"); `engine.py` falls back to a longer route; the advisor fixes closed-door phrases |
| Pay shown, unpaid flagged | `engine.py` flags any route or course that says "unpaid"; the UI shows pay and a warning |
| Free and funded first | `engine.recommend_courses` ordering |
| Source link on every item | `tests/test_data.py` checks every row; the validator flags other links |
| Says when unsure | the prompt rules; code appends an NCS pointer; no results gives a fixed "not sure" answer |

**Fairness rules**
- Qualification and group change only the entry route shown, never a career's rank or score.
- Name, gender, ethnicity, age, postcode and town never change any output.
- Results don't depend on the order of your interests or skills.

**Bias test** (`python3 -m eval.bias_test`): 20 twin profiles that differ only in name, gender, postcode and town. It compares group, ranking, skills gap and courses, and exits with an error on any difference.

**Grounding test** (`python3 -m eval.grounding_test`): 15 questions across 5 profiles, one per group. Some are traps: a course or college not in the results, London, a job guarantee. Every answer is re-checked by the validator.

**Results:**
- `eval/results/grounding.md` (live run): Grounding: 15/15 answers with no unknown mentions · regenerations: 1 · closed-door phrases: 0 · calls: 16 · tokens in/out: 46026/4210
- `eval/results/bias.md`: Bias test: 20/20 pairs identical
- `eval/results/model_comparison.md` (live run): haiku: grounded 16/16, fairness 3/6, $0.00042/answer · sonnet: grounded 16/16, fairness 5/6, $0.00896/answer · cascade: grounded 16/16, fairness 2/6, $0.00095/answer · Winner: sonnet

## Where it fails

- **Pay** is a typical national range per career, not a North East figure.
- **Demand** is a three-level label (high, medium, low) in `careers.csv`, not computed from vacancies.
- **The validator** spots invented names by title-case words such as "Course" or "College". It can miss a lowercase invention or flag a harmless phrase, and the grounding test uses it too.
- **The data** is a snapshot of CSV files exported from Google Sheets. Costs, funding and pay go out of date.
- **No live job feeds.** We don't know what's open today.
- **The fairness pairs are a small sample (6)** in the model comparison, so 5/6 against 3/6 is a signal, not proof.

## How we used AI

- **Claude Code built it**: one cloud session per module, tests first.
- **`claude-sonnet-5-5` powers the advisor**: We chose Sonnet 5.5 because it was the most consistent when users mentioned personal characteristics in our comparison (5/6 fairness pairs against Haiku's 3/6), at about $0.009 per answer. 400 max tokens, a cache, a call cap (200 by default), and `advisor.usage()` reports calls, cache hits and tokens, so we can work out cost per answer.
- **A planning chat** coordinated the two developers.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # MOCK_LLM=1 needs no key
streamlit run app.py
python3 -m pytest -q
python3 -m eval.bias_test
python3 -m eval.grounding_test
```

For live answers, add `ANTHROPIC_API_KEY` to `.env` and remove `MOCK_LLM=1`.

## Roadmap

An admin panel (v1 is CSV files edited in Google Sheets), live job feeds, notifications, accounts, progress tracking.

## Business model

Free for users. Schools, colleges and employment-support services pay a licence. No pay-to-rank by course providers: it would break the fairness rules.
