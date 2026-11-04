# Career Pathways — CLAUDE.md

Hackathon app (Python + Streamlit). It shows a user North East careers for their profile, their skills gap and the courses that close it, plus a per-group AI advisor. Read this file first in every session and follow it.

## Golden rule: "models read, code judges"

- `engine.py` is deterministic (no LLM) and makes every decision: the group, the career ranking, the skills gap and the course recommendations.
- `advisor.py` only explains engine results passed in as context. A validator checks every career and course it names against `data/*.csv`.
- `app.py` and `ui/` only collect input and display results. No business logic.

## Ownership

| Owner | Branch | Files |
| --- | --- | --- |
| Kamil | `backend` | `CLAUDE.md`, `README.md`, `requirements.txt`, `.gitignore`, `.env.example`, `pytest.ini`, `data/`, `groups.py`, `engine.py`, `advisor.py`, `tests/`, `eval/` |
| Dev 2 | `frontend` | `app.py`, `ui/`, `.streamlit/` |

- Never edit a file you don't own.
- Interface changes are agreed out loud, then Kamil records them here.

## Git

- Commit and push only to your own branch (Kamil's cloud sessions: `git push origin HEAD:backend`).
- After this scaffold nobody pushes to `main`. Kamil merges PRs at 16:15, 17:00 and 17:25.
- Never force-push.

## Commands

```bash
pip install -q -r requirements.txt   # first, in every new session
python3 -m pytest -q   # not bare pytest: it picks the wrong Python in cloud sessions
python3 -m eval.bias_test
MOCK_LLM=1 streamlit run app.py
```

## Budget and secrets

- Advisor model: `claude-haiku-5-5`, `max_tokens` 400.
- Cache identical questions.
- `MOCK_LLM=1` for all development and tests.
- The API key lives only in `.env` on the demo laptop, never in code, commits or cloud sessions.

## Safeguards visible in the demo

- No closed doors: always a route, even a longer one.
- Typical pay is shown and unpaid placements are flagged.
- Free and funded courses come first.
- A source link on every career and course.
- The advisor says when it's unsure and points to the National Careers Service.

## Fairness rules

- Qualification and group change only the entry route shown, never a career's rank or score.
- Name, gender, ethnicity, age, postcode and town never change any output.
- Results don't depend on the order of the user's interests or skills.
- Checked by `tests/test_engine.py` and `python3 -m eval.bias_test` (20 twin profiles that differ only in personal details).

## CONTRACT v1 (UI ⇄ engine/advisor; change only by agreement, recorded here by Kamil)

```text
CONTRACT v1 (UI ⇄ engine/advisor; change only by agreement, recorded here by Kamil)
profile, built by the UI, with no names or other personal data:
  {"qualification": "no_quals"|"gcse"|"level3"|"graduate", "has_experience": bool,
   "experience_years": int (0 when no experience), "interests": [str], "skills": [str], "town": str}
  The engine ignores any other key. Ranking never uses name, gender, ethnicity, age, postcode or town.
engine.form_options() -> {"qualifications": [{"id", "label"}], "groups": [{"id", "label", "description"}],
  "interests": [str] (unique careers.csv sectors, sorted), "skills": [str] (unique career skills, sorted), "towns": [str]}
engine.assign_group(profile) -> group id: "career_changer" if has_experience and experience_years >= CAREER_CHANGER_MIN_YEARS (3), else the qualification. The UI lets the user change it.
engine.rank_careers(profile, group, n=5) -> [career], best first, never empty.
  career = {career_id, title, sector, ne_demand: "high"|"medium"|"low", pay_min: int, pay_max: int (£ a year),
            entry_route: str (for this group, never empty), unpaid_placement: bool, skills: [str], source_url,
            score: float (0–100 match score, 1 dp, safe to display), reasons: [str] (plain English, explain the score, shown to the user)}
engine.skills_gap(profile, career) -> {"have": [str], "missing": [str]}, in the career's skill order.
engine.recommend_courses(missing, profile, n=5) -> [course]: only courses that close at least one missing skill; [] if none (the UI then shows the entry route and the NCS link).
  Order: most missing skills closed, then free or funded first, then cheaper, then shorter, then course_id.
  course = {course_id, title, provider, cost_gbp: float (0 = free), funded: bool, free_or_funded: bool,
            length_weeks: float, format, entry_requirements, skills_taught: [str], closes: [str] (the missing skills it teaches),
            unpaid_placement: bool, source_url}
advisor.ask(group, profile, context, question, history) -> {"answer": str, "mentioned_ids": [str], "unknown_mentions": [str], "mode": "mock"|"live"}
  context = {"careers": [career], "selected_career": career or None, "gap": dict or None, "courses": [course]}
  history = [{"role": "user"|"assistant", "content": str}], oldest first, kept by the UI.
  Answers cite items as "Title [ID]". Non-empty unknown_mentions → the UI shows a visible warning; mode "mock" → the UI shows a small "demo mode" label.
The UI may import groups.GROUPS and groups.NCS_URL. Every return value is plain Python (str, int, float, bool, list, dict), never pandas or numpy types.
```

## DATA (data/*.csv, exported from Google Sheets; the data teammate's real rows replace the placeholders at about 15:45)

```text
DATA (data/*.csv, exported from Google Sheets; the data teammate's real rows replace the placeholders at about 15:45)
careers.csv: career_id,title,sector,ne_demand,pay_min,pay_max,entry_route_no_quals,entry_route_gcse,entry_route_level3,entry_route_graduate,entry_route_career_changer,skills,source_url
courses.csv: course_id,title,provider,cost_gbp,funded,length_weeks,format,entry_requirements,skills_taught,source_url
IDs: CAR01… and CRS01…. skills and skills_taught are semicolon-separated and spelled the same in both files. ne_demand: high|medium|low. funded: yes|no. Pay in whole £ a year; cost_gbp is what an eligible learner pays (0 if funding covers it); funded is yes when public or employer funding covers some or all of the cost; length in weeks. Every entry_route_* is filled and never says "not possible". Any route or course with an unpaid placement says "unpaid". Every row has a real source_url. Placeholder titles start with "PLACEHOLDER".
```
