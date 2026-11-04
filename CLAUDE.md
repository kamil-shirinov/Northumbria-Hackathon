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

## Git workflow

Everyone:

- Every developer commits and pushes each working change to their own branch.
- Never push to `main` directly. Never force-push or delete branches.

Kamil's cloud sessions:

- First, every session (the branch the session started on doesn't matter):
  `git fetch origin`, then `git checkout backend` (or `git checkout -b backend origin/backend` if it isn't local), then `git pull --rebase origin backend`.
- Commit every change as soon as the tests pass, with a clear message, and push it straight away:
  `git pull --rebase origin backend`, then `git push origin backend`.
- After merging `main` into `backend`, always pull with `git pull --rebase=merges origin backend` before pushing, so a rebase never flattens the merge.
- Never end a reply with uncommitted or unpushed work. End every reply with the commit hash.
- At the checkpoints (16:15, 17:00, 17:25) the session merges `backend` and `frontend` into `main` through pull requests it opens and merges itself with `gh api` (REST endpoints; `gh pr` is blocked here). It merges only after the tests pass on the merged result.

## Commands

```bash
pip install -q -r requirements.txt   # first, in every new session
python3 -m pytest -q   # not bare pytest: it picks the wrong Python in cloud sessions
python3 -m eval.bias_test
python3 -m eval.grounding_test   # live (key) → eval/results/grounding.md; mock → grounding_mock.md (gitignored)
MOCK_LLM=1 streamlit run app.py   # MOCK_LLM: only 1/true/yes (any case) = mock; unset, empty, 0/false/no = live if ANTHROPIC_API_KEY is set; no key = always mock
```

## Budget and secrets

- Advisor model: `claude-haiku-5-5`, `max_tokens` 400.
- Cache identical questions.
- `MOCK_LLM=1` for all development and tests.
- The API key lives only in `.env` on the demo laptop, never in code, commits or cloud sessions.

## Advisor (advisor.py; the ask() contract is unchanged)

- Mode (`advisor.mode()`, also used by the eval to choose its results file): "mock" if `MOCK_LLM` is 1, true or yes (any case) or `ANTHROPIC_API_KEY` is missing. "live" if the key is set and `MOCK_LLM` is unset, empty, 0, false or no. Any other value is not mock and prints a warning. An empty context gets a fixed "not sure" answer with `NCS_URL` and no API call.
- Live call: `anthropic.Anthropic(timeout=20, max_retries=1).messages.create(model=MODEL, max_tokens=400, thinking={"type": "disabled"}, output_config={"effort": "low"}, ...)` (in `extra_body` if the installed SDK lacks those arguments). Never send temperature: Haiku 5.5 returns a 400 for a non-default value. Haiku 5.5 thinks adaptively by default and thinking tokens count toward max_tokens, so thinking is disabled. Retried once with `thinking={"type": "adaptive"}`, effort low and max_tokens 2000 (`ADAPTIVE_MAX_TOKENS`) if the API rejects disabled thinking with a 400 (remembered per model) or stops at `max_tokens` with no text. The answer is all blocks of type "text" joined, never `content[0]`. stop_reason "refusal" returns `REFUSAL_ANSWER` ("not sure", NCS_URL) with mode "live" and logs to stderr. Any empty answer logs its stop_reason and block types to stderr, then falls back to the mock. The system prompt is `BASE_ADVISOR_RULES` + the group's `advisor_instructions` + the results as compact JSON (careers, selected_career, gap, courses, and the profile's qualification, experience, interests and skills; never the town). The messages are the last 6 history turns + the question.
- `advisor.validate(answer, context, user_text="") -> (mentioned_ids, unknown_mentions)`. It flags [IDs] not in the context, data/*.csv careers and courses outside the results, invented named courses, qualifications, colleges and universities (title-case phrases with Course, Bootcamp, Apprenticeship, Certificate, Diploma, Degree, BTEC, NVQ, HNC, HND, T Level, Academy, Programme, College or University that match nothing in the context), URLs other than a context `source_url` or `NCS_URL`, and £ figures (£22,000, £22k or 22,000) other than a context pay or cost. Context titles without an ID count as mentions. It never flags the National Careers Service, group labels, generic phrases ("a Level 2 course") or the user's own words (named things, figures or links from the question or their earlier turns; [IDs] are always checked).
- Regeneration: unknown mentions or a closed-door phrase ("not possible for you", "you can't become", "isn't an option for you"…) trigger at most one regeneration, which tells the model what to drop. The less-flagged answer wins. Anything still unknown is returned in `unknown_mentions`, and the UI shows the warning.
- Safeguards enforced in code: a closed-door phrase that survives regeneration gets "There's always a route: … ask the National Careers Service (NCS_URL)." appended. An answer that cites no result and has no NCS pointer gets "Not sure? The National Careers Service can help: NCS_URL" appended. The mock never echoes [IDs] typed in the question.
- Failures: any API error or timeout is printed to stderr and the mock answer is returned (mode "mock"), so the demo never crashes. If the regeneration call fails, the first answer is kept with its flags.
- Budget: an in-memory cache keyed on group + normalised question + context IDs (and gap) + the last 6 turns (only live answers are cached). A cap of `ADVISOR_MAX_CALLS` (default 200) API calls per process; after that, the mock with a note.
- Observability: `advisor.usage()` returns `{"calls", "cached", "input_tokens", "output_tokens"}`. `advisor.last_debug` holds the last ask's `{"regenerated", "first_unknown", "closed_door_fixed", "cached"}`. `advisor.reset()` clears the cache, counters and client (for tests and evals).
- Tests: `tests/test_advisor.py` uses a fake client and tests/fixtures (no network, no key). Eval: `python3 -m eval.grounding_test` (15 questions in `eval/questions.txt` × 5 profiles) prints "Grounding: X/15 …" A live run (key set, `MOCK_LLM` unset) writes `eval/results/grounding.md`, which only the demo laptop commits. A mock run writes `eval/results/grounding_mock.md` (gitignored, with a MOCK banner), so cloud sessions never overwrite the live results.

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
  history holds only earlier turns, oldest first, each {"role", "content"}; the new question goes only in question, never in history.
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
