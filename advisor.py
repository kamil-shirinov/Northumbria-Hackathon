"""Advisor: explains engine results, never decides anything ("models read, code judges").

Implements advisor.ask() from CONTRACT v1 (see CLAUDE.md).

- Mode (mode()): "mock" if MOCK_LLM is 1, true or yes (any case) or ANTHROPIC_API_KEY is
  missing; otherwise "live" (MOCK_LLM unset, empty, 0, false or no).
- Live: one Claude call with the engine results as the only allowed facts, then validate()
  checks the answer against the context and data/*.csv. Unknown mentions or a closed-door
  phrase trigger one regeneration. Safeguards (closed-door fix, NCS pointer) are applied
  in code, whatever the model wrote.
- Models: ADVISOR_MODEL (default claude-haiku-5-5) writes the answer and ADVISOR_REGEN_MODEL
  (default: the answer model) writes the one regeneration. eval/model_compare.py sets
  MODEL and REGEN_MODEL on this module to compare configurations.
- Budget: identical questions are cached, and live calls are capped per process
  (ADVISOR_MAX_CALLS, default 200). usage() (totals and per model) and last_debug (each
  call's model and latency) report what happened.
- Any API error or timeout falls back to the mock answer, so the demo never crashes.
"""

from __future__ import annotations

import copy
import inspect
import json
import os
import re
import sys
import time

from dotenv import load_dotenv

from groups import BASE_ADVISOR_RULES, GROUPS, NCS_URL, QUALIFICATIONS

load_dotenv()  # reads .env on the demo laptop if present; real environment variables win

DEFAULT_MODEL = "claude-haiku-5-5"


def models_from_env(env=None) -> tuple[str, str]:
    """(answer model, regeneration model) from ADVISOR_MODEL and ADVISOR_REGEN_MODEL.

    Unset or blank ADVISOR_MODEL means DEFAULT_MODEL; unset or blank ADVISOR_REGEN_MODEL
    means the answer model. Surrounding spaces are ignored.
    """
    env = os.environ if env is None else env
    model = (env.get("ADVISOR_MODEL") or "").strip() or DEFAULT_MODEL
    regen = (env.get("ADVISOR_REGEN_MODEL") or "").strip() or model
    return model, regen


MODEL, REGEN_MODEL = models_from_env()
MAX_TOKENS = 400
# Haiku 5.5 thinks adaptively by default and thinking tokens count toward max_tokens, so
# every call disables thinking. If a model rejects that (HTTP 400), or a reply stops at
# max_tokens with no text, the call is retried once with adaptive thinking and this budget.
ADAPTIVE_MAX_TOKENS = 2000
THINKING_OFF = {"type": "disabled"}
THINKING_ADAPTIVE = {"type": "adaptive"}
OUTPUT_CONFIG = {"effort": "low"}
TIMEOUT_SECONDS = 20
HISTORY_TURNS = 6
MAX_CALLS = int(os.environ.get("ADVISOR_MAX_CALLS") or 200)

NCS_NAME = "National Careers Service"
NOT_SURE_APPEND = f"Not sure? The National Careers Service can help: {NCS_URL}"
CLOSED_DOOR_APPEND = (
    "There's always a route: see the longer route above, "
    f"or ask the National Careers Service ({NCS_URL})."
)
CAP_NOTE = "(The live advisor has reached its limit for this session, so this is a template answer.)"
REFUSAL_ANSWER = (
    "I'm not sure I can help with that one. "
    f"The National Careers Service can give you free, impartial advice: {NCS_URL}"
)
EMPTY_CONTEXT_ANSWER = (
    "I'm not sure: I don't have any results to base an answer on yet. "
    "Fill in your profile to see careers and courses, or ask the National Careers Service: "
    f"{NCS_URL}"
)

_MAX_ECHO = 200  # characters of the question the mock repeats back

# Phrases that tell someone a door is closed. Kept specific so "it's never too late" or
# "you can't go wrong" aren't caught.
CLOSED_DOOR_PATTERNS = [
    r"\b(?:is|isn't|is not|it's|it is|that's|that is)?\s*not possible for you\b",
    r"\bisn't possible for you\b",
    r"\bimpossible for you\b",
    r"\byou (?:can't|cannot|can not|won't be able to|will not be able to) (?:become|be an?|get into|work as|do this|train as)\b",
    r"\b(?:isn't|is not|aren't|are not|wouldn't be|would not be) an option for you\b",
    r"\bnot an option for you\b",
    r"\byou (?:are|'re) not (?:eligible|qualified enough|suitable)\b",
    r"\byou don't qualify\b|\byou do not qualify\b",
    r"\bno way for you\b",
    r"\b(?:is|are) closed to you\b",
    r"\bout of reach for you\b",
]
_CLOSED_DOOR_RE = re.compile("|".join(f"(?:{p})" for p in CLOSED_DOOR_PATTERNS), re.IGNORECASE)

# --------------------------------------------------------------------------- state

_client = None
_adaptive_only: set[str] = set()  # models whose API rejected disabled thinking (HTTP 400)
_cache: dict[tuple, dict] = {}
_usage = {"calls": 0, "cached": 0, "input_tokens": 0, "output_tokens": 0}
_by_model: dict[str, dict] = {}  # model -> {"calls", "input_tokens", "output_tokens"}
# calls: one {"model", "purpose": "answer"|"regeneration", "thinking": "disabled"|"adaptive",
# "max_tokens", "latency_s", "input_tokens", "output_tokens", "stop_reason", "ok", "error"}
# per API request in the last ask, in order.
last_debug: dict = {
    "regenerated": False, "first_unknown": [], "closed_door_fixed": False, "cached": False, "calls": [],
}


def usage() -> dict:
    """Live API calls made, cache hits and tokens used by this process, in total and per model.

    {"calls", "cached", "input_tokens", "output_tokens",
     "by_model": {model: {"calls", "input_tokens", "output_tokens"}}}
    """
    return {**_usage, "by_model": copy.deepcopy(_by_model)}


def reset() -> None:
    """Clear the cache, usage counters, client and last_debug. For tests and evals."""
    global _client
    _client = None
    _adaptive_only.clear()
    _cache.clear()
    for key in _usage:
        _usage[key] = 0
    _by_model.clear()
    _reset_debug()


def _reset_debug() -> None:
    last_debug.clear()
    last_debug.update(
        {"regenerated": False, "first_unknown": [], "closed_door_fixed": False, "cached": False, "calls": []}
    )


MOCK_VALUES = {"1", "true", "yes"}  # MOCK_LLM values that mean mock (any case)
LIVE_VALUES = {"0", "false", "no", ""}  # MOCK_LLM values that mean live when a key is set
_warned_values: set[str] = set()


def mode() -> str:
    """"mock" or "live". Shared by ask() and eval/grounding_test.py.

    Only MOCK_LLM = 1, true or yes (any case, surrounding spaces ignored) means mock.
    Unset, empty, 0, false or no means live when ANTHROPIC_API_KEY is set. Any other value
    is not a mock value either: it is treated like unset, with a warning on stderr.
    Without a key it is always mock.
    """
    flag = os.environ.get("MOCK_LLM", "").strip().lower()
    if flag in MOCK_VALUES:
        return "mock"
    if flag not in LIVE_VALUES and flag not in _warned_values:
        _warned_values.add(flag)
        print(
            f"advisor: MOCK_LLM={flag!r} isn't 1/true/yes or 0/false/no, so it doesn't mean mock",
            file=sys.stderr,
        )
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return "mock"
    return "live"


_mode = mode  # old private name


def _get_client():
    """The Anthropic client, built once. anthropic is imported here so mock mode never needs it."""
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=1)
    return _client


# --------------------------------------------------------------------------- formatting helpers


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _money(amount: float) -> str:
    return f"£{amount:,.0f}" if float(amount).is_integer() else f"£{amount:,.2f}"


def _cost_text(course: dict) -> str:
    if course["cost_gbp"] == 0:
        return "free"
    if course["funded"]:
        return "funded"
    return _money(course["cost_gbp"])


def _context_careers(context: dict) -> list[dict]:
    careers = list(context.get("careers") or [])
    selected = context.get("selected_career")
    if selected and selected.get("career_id") not in {c.get("career_id") for c in careers}:
        careers.append(selected)
    return careers


def _is_empty(context: dict) -> bool:
    return not (context.get("careers") or context.get("selected_career") or context.get("courses"))


# --------------------------------------------------------------------------- mock


def _strip_ids(text: str) -> str:
    """Remove anything in [brackets] and bare CAR/CRS ids, so the mock never echoes an id."""
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\b(?:CAR|CRS)\d+\b", "", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _mock_answer(context: dict, question: str, note: str = "") -> dict:
    career = context.get("selected_career") or next(iter(context.get("careers") or []), None)
    courses = context.get("courses") or []
    course = next((c for c in courses if c.get("free_or_funded")), None) or next(iter(courses), None)

    parts: list[str] = [note] if note else []
    ids: list[str] = []

    question = _strip_ids(question or "")
    if question:
        shown = question if len(question) <= _MAX_ECHO else question[: _MAX_ECHO - 1] + "…"
        parts.append(f'You asked: "{shown}".')

    if career:
        ids.append(career["career_id"])
        parts.append(
            f"A good place to start is {career['title']} [{career['career_id']}]. "
            f"Typical pay is £{career['pay_min']:,} to £{career['pay_max']:,} a year. "
            f"Your route in: {_sentence(career['entry_route'])}"
        )
        if career.get("unpaid_placement"):
            parts.append("Note that this route includes an unpaid placement.")

    if course:
        ids.append(course["course_id"])
        parts.append(
            f"To close the gap, you could start with {course['title']} [{course['course_id']}] "
            f"({_cost_text(course)}, {_number(course['length_weeks'])} weeks)."
        )
        if course.get("unpaid_placement"):
            parts.append("That course includes an unpaid placement.")

    if not career and not course:
        parts.append("I'm not sure: I don't have any results to base an answer on yet.")

    parts.append(f"For more help, the National Careers Service is at {NCS_URL}")

    return {"answer": " ".join(parts), "mentioned_ids": ids, "unknown_mentions": [], "mode": "mock"}


# --------------------------------------------------------------------------- prompt


def _career_fact(c: dict) -> dict:
    return {
        "id": c.get("career_id"),
        "title": c.get("title"),
        "pay": f"£{c.get('pay_min', 0):,} to £{c.get('pay_max', 0):,} a year",
        "demand": c.get("ne_demand"),
        "entry_route": c.get("entry_route"),
        "unpaid_placement": bool(c.get("unpaid_placement")),
        "reasons": c.get("reasons") or [],
        "source_url": c.get("source_url"),
    }


def _course_fact(c: dict) -> dict:
    cost = c.get("cost_gbp") or 0
    return {
        "id": c.get("course_id"),
        "title": c.get("title"),
        "provider": c.get("provider"),
        "cost": "free" if cost == 0 else _money(cost),
        "funded": bool(c.get("funded")),
        "length": f"{_number(c.get('length_weeks') or 0)} weeks",
        "format": c.get("format"),
        "entry_requirements": c.get("entry_requirements"),
        "closes": c.get("closes") or [],
        "unpaid_placement": bool(c.get("unpaid_placement")),
        "source_url": c.get("source_url"),
    }


def _profile_fact(profile: dict) -> dict:
    """Only what the advice needs: no town, name or other personal data."""
    years = profile.get("experience_years") or 0
    return {
        "qualification": QUALIFICATIONS.get(profile.get("qualification"), "not given"),
        "experience": f"{years} years" if profile.get("has_experience") and years else "none given",
        "interests": list(profile.get("interests") or []),
        "skills": list(profile.get("skills") or []),
    }


def build_system(group: str, profile: dict, context: dict) -> str:
    selected = context.get("selected_career")
    facts = {
        "careers": [_career_fact(c) for c in context.get("careers") or []],
        "selected_career": _career_fact(selected) if selected else None,
        "gap": context.get("gap"),
        "courses": [_course_fact(c) for c in context.get("courses") or []],
        "profile": _profile_fact(profile or {}),
    }
    g = GROUPS.get(group) or {}
    parts = [BASE_ADVISOR_RULES]
    if g:
        parts.append(f"This user's group is \"{g['label']}\". {g['advisor_instructions']}")
    parts.append("RESULTS (the only facts you may use):\n" + json.dumps(facts, ensure_ascii=False, separators=(",", ":")))
    return "\n\n".join(parts)


def build_messages(history: list[dict] | None, question: str) -> list[dict]:
    """The last HISTORY_TURNS turns of history, then the question.

    Drops malformed turns, starts on a user turn and merges same-role neighbours, so the
    API always gets a valid alternating conversation.
    """
    turns = [
        {"role": t["role"], "content": t["content"].strip()}
        for t in (history or [])
        if isinstance(t, dict) and t.get("role") in ("user", "assistant")
        and isinstance(t.get("content"), str) and t["content"].strip()
    ][-HISTORY_TURNS:]
    turns.append({"role": "user", "content": (question or "").strip() or "Can you explain my results?"})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    merged: list[dict] = []
    for t in turns:
        if merged and merged[-1]["role"] == t["role"]:
            merged[-1]["content"] += "\n\n" + t["content"]
        else:
            merged.append(dict(t))
    return merged


# --------------------------------------------------------------------------- validator

_ID_RE = re.compile(r"\[\s*([A-Za-z]{2,5}-?\d{1,4})\s*\]|\b((?:CAR|CRS)\d{1,4})\b")
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"'\])]+", re.IGNORECASE)
_POUND_RE = re.compile(r"£\s?(\d[\d,]*(?:\.\d+)?)(?:\s?([kK]|m|bn)\b)?")
_BARE_NUMBER_RE = re.compile(r"(?<![£\w.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?![\w,]|\.\d)")
_PLACEHOLDER_RE = re.compile(r"^PLACEHOLDER\s*[–—-]\s*", re.IGNORECASE)

_KEYWORDS = {
    "Course", "Courses", "Bootcamp", "Bootcamps", "Apprenticeship", "Apprenticeships",
    "Certificate", "Certificates", "Certification", "Diploma", "Diplomas", "Degree", "Degrees",
    "BTEC", "BTECs", "NVQ", "NVQs", "HNC", "HNCs", "HND", "HNDs", "Academy", "Academies",
    "Programme", "Programmes", "Program", "College", "Colleges", "University", "Universities",
}
# Capitalised words that don't make a phrase a *named* course: sentence starters, generic
# adjectives and qualification levels. "A Level 2 Course" or "Free Courses" stay generic.
_GENERIC = {
    "A", "An", "The", "This", "That", "These", "Those", "Your", "Our", "My", "Their", "Its",
    "Some", "Any", "Each", "Every", "Many", "Most", "Other", "Another", "Both", "Such",
    "Then", "Next", "First", "Second", "After", "Before", "With", "Without", "Through", "Via",
    "Or", "And", "But", "If", "For", "As", "At", "In", "On", "To", "Of", "By", "From", "Also",
    "You", "I", "We", "It", "Is", "Are", "Be", "Can", "Could", "Should", "Would", "Will", "May",
    "Consider", "Try", "Look", "Start", "Starting", "Apply", "Applying", "Take", "Taking", "Join",
    "Do", "Doing", "Check", "Find", "Explore", "See", "Ask", "Choose", "Pick", "Complete",
    "Completing", "Finish", "Get", "Getting", "Gain", "Earn", "Study", "Studying", "Enrol",
    "Enroll", "Search", "Use", "Build", "Note", "Yes", "No", "Not", "Sure", "Here", "There",
    "New", "Short", "Free", "Funded", "Paid", "Unpaid", "Online", "Local", "Part-time",
    "Full-time", "Evening", "Relevant", "Related", "Further", "Higher", "Foundation", "Level",
    "Levels", "Entry", "Advanced", "Intermediate", "Professional", "Accredited", "Recognised",
    "Recognized", "Vocational", "Academic", "Undergraduate", "Postgraduate", "Master's",
    "Masters", "Bachelor's", "Bachelors", "Graduate", "Conversion", "Training", "Trainee",
    "Apprentice", "T", "UK", "English", "Maths", "Math", "GCSE", "GCSEs", "A-level", "A-levels",
}
_CONNECTORS = {"of", "in", "and", "for", "&", "to", "de", "on"}
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*|&|[^\sA-Za-z0-9]")


def _fold(text: str) -> str:
    return " ".join(str(text).replace("’", "'").replace("–", "-").replace("—", "-").casefold().split())


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    return []


def _title_variants(title: str) -> list[str]:
    out = [title.strip()]
    bare = _PLACEHOLDER_RE.sub("", title).strip()
    if bare and bare != out[0]:
        out.append(bare)
    return [t for t in out if len(t) >= 3]


def _norm_url(url: str) -> str:
    url = url.strip().rstrip(".,;:!?").casefold()
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^www\.", "", url)
    return url.rstrip("/")


def _csv_items() -> list[tuple[str, str]]:
    """(id, title) for every career and course in data/*.csv; [] if the data can't load."""
    try:
        import engine

        data = engine._data()
    except Exception as exc:  # never let the validator crash the advisor
        print(f"advisor: couldn't load data/*.csv for the validator: {exc}", file=sys.stderr)
        return []
    return [(c["career_id"], c["title"]) for c in data["careers"]] + [
        (c["course_id"], c["title"]) for c in data["courses"]
    ]


def _money_values(context: dict, corpus_strings: list[str]) -> set[float]:
    values: set[float] = set()
    for c in _context_careers(context):
        for key in ("pay_min", "pay_max"):
            if isinstance(c.get(key), (int, float)):
                values.add(float(c[key]))
    for c in context.get("courses") or []:
        if isinstance(c.get("cost_gbp"), (int, float)):
            values.add(float(c["cost_gbp"]))
    for s in corpus_strings:  # a £ figure written in an entry route is grounded too
        for m in _POUND_RE.finditer(s):
            value = _money_value(m.group(1), m.group(2))
            if value is not None:
                values.add(value)
    return values


def _money_value(number: str, suffix: str | None) -> float | None:
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    suffix = (suffix or "").lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    elif suffix == "bn":
        value *= 1_000_000_000
    return value


def _money_ok(value: float, k_form: bool, allowed: set[float]) -> bool:
    for a in allowed:
        if abs(a - value) < 0.5:
            return True
        if k_form and abs(round(a / 1000, 1) * 1000 - value) < 0.5:  # £21.5k, £22k
            return True
        if k_form and float(value / 1000).is_integer() and round(a / 1000) * 1000 == value:
            return True
    return False


def _mask(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " " if chars[i].isspace() else "|"
    return "".join(chars)


def _is_keyword(word: str) -> bool:
    return word in _KEYWORDS or re.sub(r"['’]s$", "", word) in _KEYWORDS


def _named_phrases(text: str) -> list[str]:
    """Title-case phrases that name a course, qualification, college or university."""
    tokens = [(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(text)]
    runs: list[list[tuple[str, int, int]]] = []
    run: list[tuple[str, int, int]] = []
    for tok in tokens:
        word = tok[0]
        joinable = word[0].isupper() or word[0].isdigit() or word in _CONNECTORS
        if joinable and (not run or text[run[-1][2]:tok[1]].strip() == ""):
            run.append(tok)
        else:
            if run:
                runs.append(run)
            run = [tok] if (word[0].isupper() or word[0].isdigit()) else []
    if run:
        runs.append(run)

    found = []
    for run in runs:
        while run and (run[0][0] in _CONNECTORS or run[0][0] in _GENERIC - {"T"}):
            run = run[1:]
        while run and run[-1][0] in _CONNECTORS:
            run = run[:-1]
        if not run:
            continue
        words = [w for w, _, _ in run]
        has_keyword = any(_is_keyword(w) for w in words) or any(
            a == "T" and b.startswith("Level") for a, b in zip(words, words[1:])
        )
        if not has_keyword:
            continue
        distinctive = [
            w for w in words
            if not _is_keyword(w) and w not in _GENERIC and w not in _CONNECTORS and not w[0].isdigit()
        ]
        if not distinctive:
            continue
        phrase = text[run[0][1]:run[-1][2]]
        phrase = re.sub(r"['’]s$", "", phrase)
        found.append(phrase)
    return found


def validate(answer: str, context: dict, user_text: str = "") -> tuple[list[str], list[str]]:
    """Check an answer against the context it was given.

    Returns (mentioned_ids, unknown_mentions), each in order of first appearance.
    mentioned_ids: context careers and courses named by [ID] or by title.
    unknown_mentions: ids not in the context; data/*.csv careers or courses not in the
    context; named courses, qualifications, colleges or universities that match nothing in
    the context; URLs that aren't a context source_url or NCS_URL; £ figures that aren't a
    context pay or cost value.

    The user's own words (user_text: the question and their earlier turns) are allowed
    too, so "Newcastle College isn't in your results" isn't flagged when they asked about
    it. [IDs] are always checked.
    """
    context = context or {}
    text = (answer or "").replace("’", "'")
    user_text = (user_text or "").replace("’", "'")
    user_folded = _fold(user_text)
    careers = _context_careers(context)
    courses = list(context.get("courses") or [])
    ids = {c["career_id"]: c["title"] for c in careers if c.get("career_id")}
    ids.update({c["course_id"]: c["title"] for c in courses if c.get("course_id")})
    ids_folded = {k.casefold(): k for k in ids}

    corpus_strings = _strings(context) + [NCS_NAME, NCS_URL] + [g["label"] for g in GROUPS.values()] + list(
        QUALIFICATIONS.values()
    )
    corpus = _fold(" | ".join(corpus_strings))
    grounded = corpus + " | " + user_folded

    mentioned: list[tuple[int, str]] = []
    unknown: list[tuple[int, str]] = []
    spans: list[tuple[int, int]] = []

    # 1. URLs (masked first so ids or figures inside them aren't read twice).
    allowed_urls = {_norm_url(u) for u in [NCS_URL] + [c.get("source_url") or "" for c in careers + courses] if u}
    allowed_urls |= {_norm_url(m.group(0)) for m in _URL_RE.finditer(user_text)}
    for m in _URL_RE.finditer(text):
        url = m.group(0).rstrip(".,;:!?")
        if _norm_url(url) not in allowed_urls:
            unknown.append((m.start(), url))
        spans.append((m.start(), m.start() + len(url)))
    text_m = _mask(text, spans)

    # 2. [IDs] and bare CAR/CRS ids.
    for m in _ID_RE.finditer(text_m):
        raw = m.group(1) or m.group(2)
        real = ids_folded.get(raw.casefold())
        if real:
            mentioned.append((m.start(), real))
        else:
            unknown.append((m.start(), f"[{raw}]"))
        spans.append(m.span())

    # 3. Context titles, with or without an id; longest first so nested titles don't double count.
    title_index = sorted(
        ((variant, item_id) for item_id, title in ids.items() for variant in _title_variants(title)),
        key=lambda pair: -len(pair[0]),
    )
    for variant, item_id in title_index:
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(variant.replace("’", "'")) + r"(?![A-Za-z0-9])", re.IGNORECASE)
        for m in pattern.finditer(_mask(text, spans)):
            mentioned.append((m.start(), item_id))
            after = re.match(r"\s*\[\s*([A-Za-z]{2,5}-?\d{1,4})\s*\]", text[m.end():])
            if after and after.group(1).casefold() != item_id.casefold() and after.group(1).casefold() in ids_folded:
                unknown.append((m.start(), f"{m.group(0)} [{after.group(1)}] (wrong ID)"))
            spans.append(m.span())
    text_m = _mask(text, spans)

    # 4. Careers and courses from data/*.csv that aren't in the results.
    for item_id, title in _csv_items():
        if item_id in ids:
            continue
        for variant in _title_variants(title):
            if _fold(variant) in grounded:
                continue  # e.g. an entry route, or the user's question, names the same job
            pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(variant) + r"(?![A-Za-z0-9])", re.IGNORECASE)
            m = pattern.search(text_m)
            if m and re.match(r"\s*\[", text[m.end():]):
                break  # "Electrician [CAR05]": the unknown id is already flagged
            if m:
                unknown.append((m.start(), f"{m.group(0)} (not in your results)"))
                spans.append(m.span())
                text_m = _mask(text, spans)
                break

    # 5. Named courses, qualifications, colleges and universities.
    for phrase in _named_phrases(text_m):
        if _fold(phrase) not in grounded:
            unknown.append((text_m.find(phrase), phrase))

    # 6. £ figures (£22,000, £22k, £22000) and bare grouped numbers (22,000).
    allowed_money = _money_values(context, corpus_strings + [user_text])
    for m in _POUND_RE.finditer(text_m):
        value = _money_value(m.group(1), m.group(2))
        if value is not None and not _money_ok(value, bool(m.group(2)), allowed_money):
            unknown.append((m.start(), m.group(0).strip()))
    text_m = _mask(text_m, [m.span() for m in _POUND_RE.finditer(text_m)])
    for m in _BARE_NUMBER_RE.finditer(text_m):
        value = _money_value(m.group(1), None)
        if value is not None and not _money_ok(value, False, allowed_money):
            unknown.append((m.start(), m.group(1)))

    def ordered(pairs: list[tuple[int, str]]) -> list[str]:
        out: list[str] = []
        for _, item in sorted(pairs, key=lambda p: p[0]):
            if item not in out:
                out.append(item)
        return out

    return ordered(mentioned), ordered(unknown)


# --------------------------------------------------------------------------- safeguards


def closed_door_phrases(answer: str) -> list[str]:
    return [m.group(0).strip() for m in _CLOSED_DOOR_RE.finditer((answer or "").replace("’", "'"))]


def _has_ncs_pointer(answer: str) -> bool:
    folded = _fold(answer)
    return _fold(NCS_NAME) in folded or _norm_url(NCS_URL) in folded


def _correction(unknown: list[str], closed: list[str]) -> str:
    lines = ["Please rewrite your answer."]
    if unknown:
        lines.append(
            "These were not in the results, so leave them out: " + "; ".join(unknown) + ". "
            "Use only the careers, courses, £ figures and links in the results, and cite each as Title [ID]."
        )
    if closed:
        lines.append(
            "Don't tell the user a route is closed to them (you wrote: " + "; ".join(f'"{c}"' for c in closed) + "). "
            "Give the longer route from the results instead."
        )
    lines.append(f"If the results don't answer the question, say you're not sure and point to {NCS_URL}.")
    return " ".join(lines)


# --------------------------------------------------------------------------- live call


class Refusal(Exception):
    """The API returned stop_reason "refusal"."""


def _accepts(client, name: str) -> bool:
    """Does client.messages.create take this keyword? (Older SDKs lack thinking/output_config.)"""
    try:
        params = inspect.signature(client.messages.create).parameters
    except (TypeError, ValueError):
        return True
    return name in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _call_kwargs(client, model: str, system: str, messages: list[dict], adaptive: bool) -> dict:
    """messages.create arguments. Never sends temperature (Haiku 5.5 rejects non-default values)."""
    kwargs = {
        "model": model,
        "max_tokens": ADAPTIVE_MAX_TOKENS if adaptive else MAX_TOKENS,
        "system": system,
        "messages": messages,
    }
    extra = {}
    for name, value in (("thinking", THINKING_ADAPTIVE if adaptive else THINKING_OFF), ("output_config", OUTPUT_CONFIG)):
        if _accepts(client, name):
            kwargs[name] = dict(value)
        else:
            extra[name] = dict(value)
    if extra:
        kwargs["extra_body"] = extra
    return kwargs


def _request(client, purpose: str, kwargs: dict):
    """One API request, counted in usage() and recorded (model, latency) in last_debug["calls"]."""
    model = kwargs["model"]
    thinking = kwargs.get("thinking") or (kwargs.get("extra_body") or {}).get("thinking") or {}
    _usage["calls"] += 1
    stats = _by_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
    stats["calls"] += 1
    record = {"model": model, "purpose": purpose, "thinking": thinking.get("type", ""),
              "max_tokens": kwargs["max_tokens"], "latency_s": 0.0, "input_tokens": 0, "output_tokens": 0,
              "stop_reason": "", "ok": False, "error": ""}
    last_debug.setdefault("calls", []).append(record)
    start = time.perf_counter()
    try:
        response = client.messages.create(**kwargs)
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"[:200]
        raise
    finally:
        record["latency_s"] = round(time.perf_counter() - start, 3)
    used = getattr(response, "usage", None)
    tokens_in = int(getattr(used, "input_tokens", 0) or 0)
    tokens_out = int(getattr(used, "output_tokens", 0) or 0)
    _usage["input_tokens"] += tokens_in
    _usage["output_tokens"] += tokens_out
    stats["input_tokens"] += tokens_in
    stats["output_tokens"] += tokens_out
    record.update(input_tokens=tokens_in, output_tokens=tokens_out,
                  stop_reason=str(getattr(response, "stop_reason", "") or ""), ok=True)
    return response


def _blocks(response) -> list:
    return list(getattr(response, "content", None) or [])


def _text(response) -> str:
    """All text blocks joined (thinking and other blocks are skipped; never just content[0])."""
    return "".join(getattr(b, "text", "") or "" for b in _blocks(response) if getattr(b, "type", None) == "text").strip()


def _describe(response) -> str:
    types = [getattr(b, "type", "?") for b in _blocks(response)]
    return f"stop_reason={getattr(response, 'stop_reason', None)!r}, blocks={types}"


def _rejects_disabled_thinking(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    return status == 400 and "thinking" in str(exc).lower()


def _call(system: str, messages: list[dict], model: str | None = None, purpose: str = "answer") -> str:
    """One answer from the API: thinking disabled, effort low, max_tokens MAX_TOKENS.

    Retries once with adaptive thinking (max_tokens ADAPTIVE_MAX_TOKENS) if the API rejects
    disabled thinking with a 400 (remembered per model) or stops at max_tokens with no text.
    Raises Refusal on stop_reason "refusal" and RuntimeError on any other empty answer.
    """
    model = model or MODEL
    client = _get_client()
    adaptive = model in _adaptive_only
    try:
        response = _request(client, purpose, _call_kwargs(client, model, system, messages, adaptive))
    except Exception as exc:
        if adaptive or not _rejects_disabled_thinking(exc):
            raise
        print(f"advisor: {model} rejected disabled thinking ({exc}); retrying with adaptive thinking", file=sys.stderr)
        _adaptive_only.add(model)
        adaptive = True
        response = _request(client, purpose, _call_kwargs(client, model, system, messages, adaptive))

    if not adaptive and getattr(response, "stop_reason", None) == "max_tokens" and not _text(response):
        print(f"advisor: {model} hit max_tokens with no text ({_describe(response)}); "
              f"retrying with adaptive thinking and max_tokens {ADAPTIVE_MAX_TOKENS}", file=sys.stderr)
        response = _request(client, purpose, _call_kwargs(client, model, system, messages, True))

    if getattr(response, "stop_reason", None) == "refusal":
        print(f"advisor: {model} refused ({_describe(response)})", file=sys.stderr)
        raise Refusal(_describe(response))
    text = _text(response)
    if not text:
        print(f"advisor: empty answer from {model} ({_describe(response)})", file=sys.stderr)
        raise RuntimeError(f"empty answer from the API ({_describe(response)})")
    return text


def _live_answer(group: str, profile: dict, context: dict, question: str, history: list[dict] | None) -> dict:
    system = build_system(group, profile, context)
    messages = build_messages(history, question)

    user_text = "\n".join(m["content"] for m in messages if m["role"] == "user")

    try:
        answer = _call(system, messages, MODEL, "answer")
    except Refusal:
        return {"answer": REFUSAL_ANSWER, "mentioned_ids": [], "unknown_mentions": [], "mode": "live"}
    mentioned, unknown = validate(answer, context, user_text)
    closed = closed_door_phrases(answer)
    last_debug["first_unknown"] = list(unknown)

    if (unknown or closed) and _usage["calls"] < MAX_CALLS:
        last_debug["regenerated"] = True
        retry = messages + [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": _correction(unknown, closed)},
        ]
        try:
            second = _call(system, retry, REGEN_MODEL or MODEL, "regeneration")
        except Exception as exc:  # keep the first answer (and its warnings) if the retry fails
            print(f"advisor: regeneration failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        else:
            second_mentioned, second_unknown = validate(second, context, user_text)
            if len(second_unknown) <= len(unknown):
                answer, mentioned, unknown = second, second_mentioned, second_unknown

    if closed:
        last_debug["closed_door_fixed"] = True
        if closed_door_phrases(answer):
            answer = answer.rstrip() + "\n\n" + CLOSED_DOOR_APPEND

    if not mentioned and not _has_ncs_pointer(answer):
        answer = answer.rstrip() + "\n\n" + NOT_SURE_APPEND

    return {"answer": answer, "mentioned_ids": mentioned, "unknown_mentions": unknown, "mode": "live"}


def _cache_key(group: str, context: dict, question: str, history: list[dict] | None) -> tuple:
    q = re.sub(r"[\s?!.]+$", "", " ".join((question or "").casefold().split()))
    selected = context.get("selected_career") or {}
    gap = context.get("gap") or {}
    turns = tuple(
        (t.get("role"), " ".join(str(t.get("content", "")).split()))
        for t in (history or [])[-HISTORY_TURNS:]
        if isinstance(t, dict)
    )
    return (
        MODEL,
        REGEN_MODEL,
        group,
        q,
        tuple(c.get("career_id") for c in context.get("careers") or []),
        selected.get("career_id"),
        tuple(gap.get("missing") or []),
        tuple(c.get("course_id") for c in context.get("courses") or []),
        turns,
    )


# --------------------------------------------------------------------------- contract


def ask(group: str, profile: dict, context: dict, question: str, history: list[dict] | None = None) -> dict:
    """Answer a question about the engine results in context.

    Returns {"answer", "mentioned_ids", "unknown_mentions", "mode"} (CONTRACT v1).
    """
    _reset_debug()
    context = context or {}
    profile = profile or {}
    current = mode()

    if _is_empty(context):
        return {"answer": EMPTY_CONTEXT_ANSWER, "mentioned_ids": [], "unknown_mentions": [], "mode": current}

    if current == "mock":
        return _mock_answer(context, question)

    key = _cache_key(group, context, question, history)
    if key in _cache:
        _usage["cached"] += 1
        last_debug["cached"] = True
        return copy.deepcopy(_cache[key])

    if _usage["calls"] >= MAX_CALLS:
        return _mock_answer(context, question, note=CAP_NOTE)

    try:
        result = _live_answer(group, profile, context, question, history)
    except Exception as exc:  # the demo never crashes: fall back to the template
        print(f"advisor: live call failed ({type(exc).__name__}: {exc}); using the mock answer", file=sys.stderr)
        return _mock_answer(context, question)

    _cache[key] = copy.deepcopy(result)
    return result
