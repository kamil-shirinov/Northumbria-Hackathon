"""Section 6: the advisor chat.

Display and state only. It never calls the engine; the one advisor call per new question is
made here and the reply is stored, so reruns from any other widget only re-display it.
"""

from __future__ import annotations

import logging
import re

import streamlit as st

import advisor
from groups import GROUPS, NCS_URL
from ui import components

log = logging.getLogger(__name__)

MAX_CHARS = 300
SUGGESTED_QUESTIONS = (
    "What if I can only study part-time?",
    "Which course should I start with?",
    "What if I can't afford a course?",
)

CHAT_KEY = "chat"  # {"sig", "messages", "answers", "notice"}
PENDING_KEY = "chat_pending"  # a question queued by a button; popped (so used once) when answered
QUESTION_KEY = "chat_question"  # the text box; its key ends in the counter below, so a new count is a fresh, empty box
COUNTER_KEY = "chat_question_count"  # raised after each question sent from the box
FROM_BOX_KEY = "chat_pending_from_box"  # the queued question was typed in the box, not picked from the suggestions

_NOTE = (
    "It only uses the careers and courses shown above, and AI can make mistakes. "
    f"For complex situations, talk to the {components.NCS_LINK}: {NCS_URL}"
)
_RESET_HINT = "This chat starts again if you change your profile, group or selected career."
_ERROR_TEXT = (
    "Sorry, the advisor couldn't answer just now. Please try again in a moment, "
    f"or talk to the {components.NCS_LINK}: {NCS_URL}"
)


# --------------------------------------------------------------------------- state


def _new_chat(sig: dict, notice: str | None = None) -> dict:
    return {"sig": sig, "messages": [], "answers": {}, "notice": notice}


def _signature(group: str, profile: dict, context: dict) -> dict:
    career = context.get("selected_career") or {}
    return {"profile": profile, "group": group, "career": career.get("career_id")}


def _sync_chat(group: str, profile: dict, context: dict) -> dict:
    """Return this page's chat, starting a fresh one if the profile, group or career changed."""
    sig = _signature(group, profile, context)
    chat = st.session_state.get(CHAT_KEY)
    if chat is None:
        chat = st.session_state[CHAT_KEY] = _new_chat(sig)
    elif chat["sig"] != sig:
        changed = [
            name
            for name, key in (("profile", "profile"), ("group", "group"), ("selected career", "career"))
            if chat["sig"][key] != sig[key]
        ]
        notice = None
        if chat["messages"]:
            notice = f"Chat cleared because your {' and '.join(changed)} changed."
        chat = st.session_state[CHAT_KEY] = _new_chat(sig, notice)
    return chat


def _clean(text: object) -> str:
    return " ".join(str(text or "").split())[:MAX_CHARS]


def _queue(question: object) -> None:
    """Button callback: remember the question. It runs before the page reruns, so it happens once."""
    question = _clean(question)
    if question:  # empty questions are ignored
        st.session_state[PENDING_KEY] = question


def _question_key() -> str:
    """The text box's key for this send. A new counter value is a new widget, so the box starts empty."""
    return f"{QUESTION_KEY}_{st.session_state.get(COUNTER_KEY, 0)}"


def _queue_from_box() -> None:
    _queue(st.session_state.get(_question_key(), ""))
    if st.session_state.get(PENDING_KEY):  # an empty box queues nothing, so nothing is sent or cleared
        st.session_state[FROM_BOX_KEY] = True


def _history(messages: list[dict]) -> list[dict]:
    """Earlier turns in the contract's format, oldest first. Failed turns are left out."""
    history = []
    for i, message in enumerate(messages):
        if message.get("error"):
            continue
        following = messages[i + 1] if i + 1 < len(messages) else {}
        if message["role"] == "user" and following.get("error"):
            continue
        history.append({"role": message["role"], "content": message["content"]})
    return history


# --------------------------------------------------------------------------- display


def _plain(text: object) -> str:
    """The user's own words as safe markdown: no formatting, links or images."""
    return components.escape(text).replace("\n", "  \n")


# --- Advisor answers are shown as markdown, after this clean-up. Display only: the stored text is unchanged.

_HTML_BLOCK = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r"<!--.*?-->|</?[A-Za-z][^<>]*>", re.DOTALL)  # also takes <https://...> autolinks
_LINK_TARGET = r"(?:<[^<>\n]*>|(?:[^()\s]|\([^()\s]*\))*)"
_LINK_TITLE = r"""(?:\s+(?:"[^"]*"|'[^']*'|\([^()]*\)))?"""
_INLINE_LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*(" + _LINK_TARGET + r")" + _LINK_TITLE + r"\s*\)")
_REFERENCE_LINK = re.compile(r"(!?)\[([^\]]+)\]\[[^\]]*\]")
_REFERENCE_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]*\S.*(?:\n|\Z)", re.MULTILINE)
_BARE_URL = re.compile(r"(?:\b[A-Za-z][A-Za-z0-9+.\-]*://|\bwww\.)[^\s<>\[\]()\"'`]+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_URL_TAIL = ".,;:!?*_~"  # punctuation or emphasis marks that end a sentence, not the address
# Only the National Careers Service's own address is kept. A pattern (not a URL parser) so that tricks like
# https://nationalcareers.service.gov.uk@other.site or ...\@... can never pass for it.
_NCS_ADDRESS = re.compile(
    r"https?://" + re.escape(NCS_URL.split("://", 1)[-1].rstrip("/")) + r"(?:[/?#][^\s\\]*)?\Z", re.IGNORECASE
)
_ATX_HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)[ \t]*#*[ \t]*$", re.MULTILINE)
_SETEXT_RULE = re.compile(r"^ {0,3}(?:=+|-{2,})[ \t]*$")


def _is_ncs(url: str) -> bool:
    return bool(_NCS_ADDRESS.match(url.strip().strip("<>")))


def _drop_urls(text: str) -> str:
    """Remove bare web addresses, except the National Careers Service's. Email addresses go too (they become links)."""

    def keep_or_drop(match: re.Match) -> str:
        raw = match.group(0)
        url = raw.rstrip(_URL_TAIL)
        return raw if _is_ncs(url) else raw[len(url) :]  # the sentence's own full stop stays

    return _EMAIL.sub("", _BARE_URL.sub(keep_or_drop, text))


def _unlink(text: str) -> str:
    """Markdown links and images become their text. A link to the National Careers Service stays a link."""

    def replace(match: re.Match) -> str:
        bang, label, target = match.groups()
        target = target.strip().strip("<>")
        if not bang and _is_ncs(target):
            return f"[{_drop_urls(label).strip() or 'National Careers Service'}]({target})"
        return label

    text = _INLINE_LINK.sub(replace, text)
    text = _REFERENCE_LINK.sub(lambda match: match.group(2), text)
    return _REFERENCE_DEFINITION.sub("", text)


def _flatten_headings(text: str) -> str:
    """Headings in an answer become bold lines, so the page keeps one h1 and no skipped heading levels."""
    # Blank lines round the bold line, because a bold line (unlike a heading) would merge into its neighbours.
    text = _ATX_HEADING.sub(lambda m: f"\n**{m.group(1).replace('*', '').strip()}**\n" if m.group(1).strip() else "", text)
    lines: list[str] = []
    for line in text.split("\n"):
        if _SETEXT_RULE.match(line) and lines and lines[-1].strip():
            lines.append("")  # a blank line first: "Title" over "---" would be a heading, not a rule
            if line.lstrip().startswith("="):
                continue
        lines.append(line)
    return "\n".join(lines)


def _hide_ids(text: str, ids: set[str]) -> str:
    """Remove "[CAR04]"-style ids (and the space before them). Ids that aren't in `ids` stay, so the warning makes sense."""
    if not ids:
        return text
    one = r"\[\s*(?:" + "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True)) + r")\s*\](?:\([^()\s]*\))?"
    text = re.sub(r"(?<=\S)[ \t]*" + one, "", text, flags=re.IGNORECASE)
    return re.sub(one + r"[ \t]*", "", text, flags=re.IGNORECASE)  # at the start of a line


def _tidy(text: str) -> str:
    text = re.sub(r"\(\s*\)", "", text)  # "()" left by a removed link or id
    text = re.sub(r"(?<=\S) {2,}(?=\S)", " ", text)  # double spaces inside a line (a hard line break is kept)
    return re.sub(r"(?<=\S) +(?=[.,;:!?](?:\s|\Z))", "", text).strip()  # "analyst ." -> "analyst."


def safe_answer(text: object, known_ids: object = ()) -> str:
    """An advisor answer as markdown that is safe to show.

    Keeps bold, lists and the like. Removes markdown links and images (keeping their text), raw HTML and
    web addresses, except the National Careers Service's. Removes [ids] in `known_ids`. Escapes "$" so
    Streamlit doesn't read it as maths. Headings become bold lines.
    """
    text = str(text or "").replace("\r\n", "\n")
    text = _hide_ids(text, {str(i) for i in known_ids or ()})
    text = _HTML_TAG.sub("", _HTML_BLOCK.sub("", text))
    text = _drop_urls(_unlink(text))
    text = _tidy(_flatten_headings(text))
    return re.sub(r"(?<!\\)\$", r"\\$", text)


def _known_ids(context: dict, mentioned_ids: list) -> list[str]:
    """Career and course ids that are real (in the results or reported as mentioned): safe to hide from view."""
    ids = {str(i) for i in mentioned_ids or []}
    for career in [*(context.get("careers") or []), context.get("selected_career") or {}]:
        if career.get("career_id"):
            ids.add(career["career_id"])
    for course in context.get("courses") or []:
        if course.get("course_id"):
            ids.add(course["course_id"])
    return sorted(ids)


def _assistant_body(message: dict) -> None:
    """The inside of an assistant bubble."""
    if message.get("error"):
        st.warning(message["content"])
        return
    st.markdown(safe_answer(message["content"], message.get("known_ids")))
    if message.get("mode") == "mock":
        st.caption("Demo mode: this answer is a template, not live AI.")
    if message.get("repeat"):
        st.caption("You asked this before, so this is the same answer. No new request was made.")

    unknown = message.get("unknown_mentions") or []
    if unknown:
        st.warning(
            "**Please check this answer.** It names something we couldn't find in our data: "
            f"{components.escape(', '.join(str(u) for u in unknown))}. "
            f"Don't rely on it. The {components.NCS_LINK} can help: {NCS_URL}"
        )
    else:
        st.caption("Checked: everything named is in our data")
    for source in message.get("sources") or []:
        link = components.source_link_markdown(source["source_url"], source["title"])
        st.markdown(f"- {link or components.escape(source['title']) + ': no source link listed'}")


def _show_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(_plain(message["content"]))
        else:
            _assistant_body(message)


def _sources(mentioned_ids: list, careers: list[dict], courses: list[dict], context: dict) -> list[dict]:
    """Title and source link for each mentioned id found on the page. Unknown ids are skipped."""
    found = {}
    for career in [*(careers or []), context.get("selected_career") or {}]:
        if career.get("career_id"):
            found.setdefault(career["career_id"], career)
    for course in courses or []:
        if course.get("course_id"):
            found.setdefault(course["course_id"], course)

    sources, seen = [], set()
    for item_id in mentioned_ids or []:
        item = found.get(item_id)
        if item is None or item_id in seen:
            continue
        seen.add(item_id)
        sources.append({"id": item_id, "title": item.get("title", item_id), "source_url": item.get("source_url")})
    return sources


# --------------------------------------------------------------------------- asking


def _ask_advisor(question: str, history: list[dict], group: str, profile: dict, context: dict, careers: list, courses: list) -> dict:
    """The one advisor call for a new question. Returns the reply to store, or a friendly error reply."""
    try:
        raw = advisor.ask(group, profile, context, question, history)
        answer = raw.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("advisor returned no answer")
        return {
            "role": "assistant",
            "content": answer,
            "mode": raw.get("mode"),
            "unknown_mentions": [str(u) for u in raw.get("unknown_mentions") or []],
            "sources": _sources(raw.get("mentioned_ids") or [], careers, courses, context),
            "known_ids": _known_ids(context, raw.get("mentioned_ids") or []),
        }
    except Exception as error:  # noqa: BLE001 - the page must never show a traceback
        log.warning("advisor.ask failed: %s", type(error).__name__)
        log.debug("advisor.ask traceback", exc_info=True)
        return {"role": "assistant", "content": _ERROR_TEXT, "error": True}


def _answer(question: str, chat: dict, group: str, profile: dict, context: dict, careers: list, courses: list) -> dict:
    """Show a new question and its answer, and return the reply. Calls the advisor once, unless this chat already has the answer."""
    history = _history(chat["messages"])  # earlier turns only; the question is passed separately
    user = {"role": "user", "content": question}
    chat["notice"] = None
    _show_message(user)

    cached = chat["answers"].get(question.casefold())
    if cached is not None:
        reply = {**cached, "repeat": True}
        _show_message(reply)
    else:
        with st.chat_message("assistant"):
            with st.spinner("Asking your advisor…"):
                reply = _ask_advisor(question, history, group, profile, context, careers, courses)
            _assistant_body(reply)
        if not reply.get("error"):  # a failed question can be asked again
            chat["answers"][question.casefold()] = reply
    chat["messages"].extend([user, reply])
    return reply


def render_chat(group: str, profile: dict, context: dict, careers: list[dict], courses: list[dict]) -> None:
    """Section 6. `context` is the CONTRACT v1 advisor context; careers and courses are the ones on the page."""
    label = GROUPS.get(group, {}).get("label", group)
    st.header(f"6. Ask your {components.escape(label)} advisor", anchor=False)
    st.caption(_NOTE)

    chat = _sync_chat(group, profile, context)

    st.markdown("**Try a question**")
    for index, question in enumerate(SUGGESTED_QUESTIONS):  # one full-width button per row, so it reads well on a phone
        st.button(
            question,
            key=f"chat_suggest_{index}",
            on_click=_queue,
            args=(question,),
            width="stretch",
        )

    st.caption(f"{chat['notice']} {_RESET_HINT}" if chat["notice"] else _RESET_HINT)

    pending = st.session_state.pop(PENDING_KEY, None)
    from_box = st.session_state.pop(FROM_BOX_KEY, False)
    for message in chat["messages"]:
        _show_message(message)
    if pending:
        reply = _answer(pending, chat, group, profile, context, careers, courses)
        if from_box and not reply.get("error"):
            # Sent: the next box has a new key, so it starts empty. (After a failure the text stays, to send again.)
            st.session_state[COUNTER_KEY] = st.session_state.get(COUNTER_KEY, 0) + 1
    elif not chat["messages"]:
        st.caption("Ask a question below, or pick one of the suggestions.")

    # Enter sends the question as well as the button. The box is cleared by its new key, not by clear_on_submit.
    with st.form("chat_form"):  # bordered like the profile form, so both get the same light-blue surface
        st.text_input(
            f"Or ask your own question (up to {MAX_CHARS} characters)",
            max_chars=MAX_CHARS,
            key=_question_key(),
        )
        st.form_submit_button("Ask the advisor", key="chat_ask", on_click=_queue_from_box)
