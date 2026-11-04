"""Shared display helpers: badges, pay range, source link, unpaid flag.

Display only. Nothing here ranks, filters or decides anything.
"""

from __future__ import annotations

import re

import streamlit as st

from groups import NCS_URL

NCS_LINK = f"[National Careers Service]({NCS_URL})"

# Characters that would change how Streamlit's markdown draws text taken from the data files.
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]$~<>#|])")

# Text is always part of the badge, so meaning never depends on colour alone.
_DEMAND_BADGES = {
    "high": ("High demand in the North East", "green"),
    "medium": ("Medium demand in the North East", "orange"),
    "low": ("Lower demand in the North East", "gray"),
}


def escape(text: object) -> str:
    """Make text from the data safe to put inside markdown."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", str(text if text is not None else ""))


def badge(text: str, color: str = "blue") -> str:
    """A Streamlit badge as a markdown string. Colours: blue, green, orange, red, violet, gray."""
    return f":{color}-badge[{escape(text)}]"


def demand_badge(ne_demand: str | None) -> str:
    label, color = _DEMAND_BADGES.get(str(ne_demand or "").casefold(), ("North East demand not listed", "gray"))
    return badge(label, color)


def _whole(value: object) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def pay_range(pay_min: object, pay_max: object) -> str:
    """Typical pay as plain text, e.g. "£22,000–£26,000 a year"."""
    low, high = _whole(pay_min), _whole(pay_max)
    if not low and not high:
        return "Pay not listed (see the source link)"
    if low == high or not low or not high:
        return f"£{(high or low):,} a year"
    return f"£{low:,}–£{high:,} a year"


def cost_text(cost_gbp: object) -> str:
    """"Free" when the cost is 0, otherwise pounds."""
    try:
        cost = float(cost_gbp)
    except (TypeError, ValueError):
        return "Cost not listed"
    if cost == 0:
        return "Free"
    return f"£{cost:,.0f}" if cost.is_integer() else f"£{cost:,.2f}"


def weeks_text(length_weeks: object) -> str:
    try:
        weeks = float(length_weeks)
    except (TypeError, ValueError):
        return "Length not listed"
    number = f"{weeks:.0f}" if weeks.is_integer() else f"{weeks:g}"
    return f"{number} {'week' if weeks == 1 else 'weeks'}"


def _link_target(url: str) -> str:
    # Spaces and brackets would end a markdown link early.
    return url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def source_link_markdown(url: object, subject: str | None = None) -> str | None:
    """A markdown "Source" link, or None if the url is missing or isn't http(s)."""
    url = str(url or "").strip()
    if not url.lower().startswith(("https://", "http://")):
        return None
    name = f"Source for {escape(subject)}" if subject else "Source"
    return f"[{name} ↗]({_link_target(url)})"


def source_link(url: object, subject: str | None = None) -> None:
    """A "Source" link. Falls back to the National Careers Service if the link is missing."""
    link = source_link_markdown(url, subject)
    if link:
        st.markdown(link)
    else:
        st.caption(f"We couldn't find a source link for this one. Try the {NCS_LINK} instead.")


def unpaid_flag(what: str = "route") -> None:
    """A visible warning for an unpaid placement."""
    st.warning(f"**Unpaid placement:** this {what} includes an unpaid placement. Check you can manage without pay first.")


def empty_message(text: str) -> None:
    """A friendly message in place of an empty section, always with a way forward."""
    st.info(f"{text} The {NCS_LINK} can help you find a way in.")


def footer() -> None:
    st.divider()
    st.caption(f"If your situation is complicated, talk to the {NCS_LINK}: {NCS_URL}")
