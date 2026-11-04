"""Section 6: the advisor chat.

Display and state only. It never calls the engine; the one advisor call per new question is
made here and the reply is stored, so reruns from any other widget only re-display it.
"""

from __future__ import annotations

import logging

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
QUESTION_KEY = "chat_question"  # the text box

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


def _queue_from_box() -> None:
    _queue(st.session_state.get(QUESTION_KEY, ""))


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
    """Text from the advisor or the user as safe markdown: no formatting, links or images."""
    return components.escape(text).replace("\n", "  \n")


def _assistant_body(message: dict) -> None:
    """The inside of an assistant bubble."""
    if message.get("error"):
        st.warning(message["content"])
        return
    st.markdown(_plain(message["content"]))
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
        link = components.source_link_markdown(source["source_url"])
        st.markdown(f"- **{components.escape(source['title'])}**: {link or 'no source link listed'}")


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
        }
    except Exception as error:  # noqa: BLE001 - the page must never show a traceback
        log.warning("advisor.ask failed: %s", type(error).__name__)
        log.debug("advisor.ask traceback", exc_info=True)
        return {"role": "assistant", "content": _ERROR_TEXT, "error": True}


def _answer(question: str, chat: dict, group: str, profile: dict, context: dict, careers: list, courses: list) -> None:
    """Show a new question and its answer. Calls the advisor once, unless this chat already has the answer."""
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


def render_chat(group: str, profile: dict, context: dict, careers: list[dict], courses: list[dict]) -> None:
    """Section 6. `context` is the CONTRACT v1 advisor context; careers and courses are the ones on the page."""
    label = GROUPS.get(group, {}).get("label", group)
    st.header(f"6. Ask your {components.escape(label)} advisor")
    st.caption(_NOTE)

    chat = _sync_chat(group, profile, context)

    st.markdown("**Try a question**")
    columns = st.columns(len(SUGGESTED_QUESTIONS))
    for index, (column, question) in enumerate(zip(columns, SUGGESTED_QUESTIONS)):
        with column:
            st.button(
                question,
                key=f"chat_suggest_{index}",
                on_click=_queue,
                args=(question,),
                width="stretch",
            )

    st.caption(f"{chat['notice']} {_RESET_HINT}" if chat["notice"] else _RESET_HINT)

    pending = st.session_state.pop(PENDING_KEY, None)
    for message in chat["messages"]:
        _show_message(message)
    if pending:
        _answer(pending, chat, group, profile, context, careers, courses)
    elif not chat["messages"]:
        st.caption("Ask a question below, or pick one of the suggestions.")

    with st.form("chat_form", clear_on_submit=True, border=False):
        st.text_input(
            f"Or ask your own question (up to {MAX_CHARS} characters)",
            max_chars=MAX_CHARS,
            key=QUESTION_KEY,
        )
        st.form_submit_button("Ask", key="chat_ask", on_click=_queue_from_box)
