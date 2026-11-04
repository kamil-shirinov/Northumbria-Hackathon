"""Look and feel: one CSS block on top of the colours in .streamlit/config.toml. Display only.

The colours (cream page, pale sage surfaces, dark green primary, brown captions, gold accent) are the ones in the Root
logo and live in config.toml. This adds what a theme can't: the website frame (content capped at 1100px and centred,
a thin top bar, a footer), a slow gradient drifting behind the page, the gradient band behind the title, the pathway
line that draws itself in that band, rounded and softly shadowed cards, and a little more space between sections.
Cards, forms and the expander keep solid surfaces, so only plain page text sits on the moving background (ink text is
over 13:1 on every stop, captions over 6:1). Gold is for borders, the pathway line and the band, never for text.
Nothing here adds horizontal padding or fixed widths that could overflow at 375px; every animation stops under
prefers-reduced-motion (see the last block).

Selectors use data-testid. Streamlit gives a keyed container no test id of its own, so the hero band, the top
bar, the footer and the cards (ui/careers.py, ui/courses.py, ui/guide.py) carry a key, and the one stable hook
Streamlit documents for that is its `st-key-<key>` class: the *_KEY constants and CARD_KEY_PREFIX below.
"""

from __future__ import annotations

import streamlit as st

HERO_KEY = "hero"  # the container around the title, tagline and pathway
TOPBAR_KEY = "topbar"  # the top bar (ui/topbar.py)
BRAND_KEY = "topbar_brand"  # the logo (or the text "Root") inside the top bar
FOOTER_KEY = "site_footer"  # the footer text (ui/components.py)
CARD_KEY_PREFIX = "card_"  # every career, course and guide card has a key that starts with this

# The palette, from the logo. The same values are in .streamlit/config.toml (a TOML file can't import them).
CREAM = "#FAF6EE"  # the page
SAGE = "#EEF3EC"  # surfaces: cards, forms, the expander, inputs
GOLD_TINT = "#F3E9D2"  # soft gold: badges, and the third stop of the drifting gradients
GOLD = "#C29B52"  # the accent: borders, the pathway line and the band. Never text (2.4:1 on the page)
GREEN = "#1E3A2F"  # primary: buttons, links, focus
BROWN = "#6B4F3A"  # secondary text: captions and placeholders (6.2:1 or better on all three backgrounds)
INK = "#1F2421"  # main text

# Widest the page content gets on a big screen.
_PAGE_MAX_WIDTH = "1100px"

_CSS = f"""
/* The style element itself takes no room at the top of the page. */
[data-testid="stElementContainer"]:has([data-testid="stHtml"]) {{ display: none; }}

/* Website frame: wide layout, but the content is capped and centred. */
div[data-testid="stMainBlockContainer"] {{ max-width: {_PAGE_MAX_WIDTH}; }}

/* Background: a slow gradient drifting between cream, pale sage and soft gold. Only plain page text sits straight
   on it: ink text is over 13:1 on every stop, captions over 6:1 and links over 10:1. */
div[data-testid="stApp"] {{
  background-color: {CREAM};
  background-image: linear-gradient(120deg, {CREAM} 0%, {SAGE} 25%, {GOLD_TINT} 50%, {SAGE} 75%, {CREAM} 100%);
  background-size: 300% 300%;
  animation: cp-drift 45s ease-in-out infinite;
}}
@keyframes cp-drift {{
  0% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
  100% {{ background-position: 0% 50%; }}
}}

/* Top bar: the logo first at the far left, then Guide; the demo account on the right. It wraps onto a second row on a phone. */
.st-key-{TOPBAR_KEY} {{
  border-bottom: 1px solid {GOLD};
  padding-bottom: 0.6rem;
  margin-bottom: 0.5rem;
}}
.st-key-{BRAND_KEY} [data-testid="stMarkdownContainer"] p {{ margin: 0; font-size: 1.15rem; white-space: nowrap; }}
.st-key-{BRAND_KEY} [data-testid="stElementToolbar"] {{ display: none; }}  /* a logo needs no enlarge button */

/* Hero: a band drifting between cream, pale sage and soft gold, edged in gold (ink text is over 13:1 on every stop). */
.st-key-{HERO_KEY} {{
  background-color: {CREAM};
  background-image: linear-gradient(120deg, {CREAM} 0%, {SAGE} 25%, {GOLD_TINT} 50%, {SAGE} 75%, {CREAM} 100%);
  background-size: 300% 300%;
  animation: cp-drift 30s ease-in-out infinite;
  border: 1px solid {GOLD};
  border-bottom: 4px solid {GOLD};
  border-radius: 1rem;
  padding: 0.75rem 1.25rem 1rem;
  margin-bottom: 0.5rem;
  box-shadow: 0 2px 8px rgba(31, 36, 33, 0.08);
}}
.st-key-{HERO_KEY} [data-testid="stMarkdownContainer"] p {{ font-size: 1.1rem; margin: 0; }}

/* The pathway in the hero: a dotted line that draws itself once, then three labelled dots (decorative).
   Without the animation the line is simply there: the mask is fully open unless the animation runs. */
.cp-pathway svg {{ display: block; width: 100%; max-width: 420px; height: auto; margin-left: auto; }}
.cp-pathway .cp-draw {{ animation: cp-draw 3.5s ease-in-out 0.4s backwards; }}
@keyframes cp-draw {{
  from {{ stroke-dashoffset: 1; }}
  to {{ stroke-dashoffset: 0; }}
}}

/* Cards, the forms and the expander: pale sage surface, gold edge, rounded corners, a soft shadow. */
[data-testid="stVerticalBlock"][class*="st-key-{CARD_KEY_PREFIX}"],
[data-testid="stLayoutWrapper"][class*="st-key-{CARD_KEY_PREFIX}"],
[data-testid="stForm"],
[data-testid="stExpander"] {{
  background: {SAGE};
  border-color: {GOLD};
  border-radius: 0.75rem;
  box-shadow: 0 2px 8px rgba(31, 36, 33, 0.08);
}}

/* More room between sections. */
[data-testid="stHeading"] h2 {{ padding-top: 1.5rem; }}

/* The guide's three headings are small. */
[data-testid="stPopoverBody"] [data-testid="stHeading"] h3 {{ font-size: 1.05rem; padding-top: 0; }}

/* Captions and placeholders are brown, readable on cream, sage and soft gold. */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {{ color: {BROWN}; }}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stSelectbox"] input::placeholder,
[data-testid="stMultiSelect"] input::placeholder {{ color: {BROWN}; opacity: 1; }}

/* The footer: centred, below a divider. */
.st-key-{FOOTER_KEY} {{ text-align: center; }}

/* Anyone who asks for less motion gets none: the backgrounds stand still and the pathway is fully drawn. */
@media (prefers-reduced-motion: reduce) {{
  div[data-testid="stApp"], .st-key-{HERO_KEY} {{ animation: none !important; }}
  .cp-pathway .cp-draw {{ animation: none !important; stroke-dashoffset: 0 !important; }}
}}
"""


def apply_theme() -> None:
    """Add the CSS block. Call once, at the top of app.py, right after st.set_page_config."""
    st.html(f"<style>{_CSS}</style>")
