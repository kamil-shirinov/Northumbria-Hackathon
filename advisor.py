"""Advisor: explains engine results, never decides anything.

Implements advisor.ask() from CONTRACT v1 (see CLAUDE.md). For now it only has the
mock mode: a template built from the context it is given, so nothing here can name a
career or course the engine did not return. The live Claude call, the answer cache and
the validator against data/*.csv come in the next session.
"""

from __future__ import annotations

from dotenv import load_dotenv

from groups import NCS_URL

load_dotenv()  # reads .env on the demo laptop if present; real environment variables win

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 400

_MAX_ECHO = 200  # characters of the question to repeat back


def _get_client():
    """Build the Anthropic client. Not called yet: live mode comes next session.

    anthropic is imported here so the app and the tests start without it being used.
    """
    import anthropic

    return anthropic.Anthropic()


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


def _mock_answer(context: dict, question: str) -> dict:
    career = context.get("selected_career") or next(iter(context.get("careers") or []), None)
    courses = context.get("courses") or []
    course = next((c for c in courses if c.get("free_or_funded")), None) or next(iter(courses), None)

    parts: list[str] = []
    ids: list[str] = []

    question = " ".join((question or "").split())
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

    return {
        "answer": " ".join(parts),
        "mentioned_ids": ids,
        "unknown_mentions": [],
        "mode": "mock",
    }


def ask(group: str, profile: dict, context: dict, question: str, history: list[dict] | None = None) -> dict:
    """Answer a question about the engine results in context.

    Returns {"answer", "mentioned_ids", "unknown_mentions", "mode"}. Mock mode only for now,
    whatever MOCK_LLM says; group, profile and history are for live mode.
    """
    return _mock_answer(context or {}, question)
