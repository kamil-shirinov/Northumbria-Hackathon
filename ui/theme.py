"""Look and feel: one small CSS block on top of the colours in .streamlit/config.toml. Display only.

The colours (white page, light-blue surfaces, pink accent) live in config.toml. This adds what a theme
can't: the gradient band behind the title, rounded and softly shadowed cards, and a little more space between
sections. Nothing here changes the layout: no widths, no positions, no horizontal padding that could overflow at 375px.

Selectors use data-testid. Streamlit gives a keyed container no test id of its own, so the hero band and the
cards (ui/careers.py, ui/courses.py, ui/guide.py) carry a key, and the one stable hook Streamlit documents
for that is its `st-key-<key>` class: HERO_KEY and CARD_KEY_PREFIX below.
"""

from __future__ import annotations

import streamlit as st

HERO_KEY = "hero"  # the container around the title and tagline
CARD_KEY_PREFIX = "card_"  # every career, course and guide card has a key that starts with this

# A solid grey-blue for captions and placeholders. Streamlit draws them at 60% of the text colour, which is
# 4.5:1 on the light blue and only just; this is 7:1 and keeps them readable on every surface.
_QUIET_TEXT = "#4B5563"
_SOFT_BORDER = "#C9DDF5"

_CSS = f"""
/* The style element itself takes no room at the top of the page. */
[data-testid="stElementContainer"]:has([data-testid="stHtml"]) {{ display: none; }}

/* Hero: a soft light-blue to pink band behind the title and tagline (dark text on both ends is over 15:1). */
.st-key-{HERO_KEY} {{
  background: linear-gradient(135deg, #EEF6FF 0%, #FCE4EC 100%);
  border-radius: 1rem;
  padding: 0.75rem 1.25rem 1rem;
  margin-bottom: 0.5rem;
}}
.st-key-{HERO_KEY} [data-testid="stMarkdownContainer"] p {{ font-size: 1.1rem; margin: 0; }}

/* Cards, the forms and the expander: light-blue surface, rounded corners, a soft shadow. */
[data-testid="stVerticalBlock"][class*="st-key-{CARD_KEY_PREFIX}"],
[data-testid="stLayoutWrapper"][class*="st-key-{CARD_KEY_PREFIX}"],
[data-testid="stForm"],
[data-testid="stExpander"] {{
  background: #EEF6FF;
  border-color: {_SOFT_BORDER};
  border-radius: 0.75rem;
  box-shadow: 0 2px 8px rgba(17, 24, 39, 0.08);
}}

/* More room between sections. */
[data-testid="stHeading"] h2 {{ padding-top: 1.5rem; }}

/* The guide's three headings are small. */
[data-testid="stPopoverBody"] [data-testid="stHeading"] h3 {{ font-size: 1.05rem; padding-top: 0; }}

/* Captions and placeholders stay readable on the light blue. */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {{ color: {_QUIET_TEXT}; }}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stSelectbox"] input::placeholder,
[data-testid="stMultiSelect"] input::placeholder {{ color: {_QUIET_TEXT}; opacity: 1; }}
"""


def apply_theme() -> None:
    """Add the CSS block. Call once, at the top of app.py, right after st.set_page_config."""
    st.html(f"<style>{_CSS}</style>")
