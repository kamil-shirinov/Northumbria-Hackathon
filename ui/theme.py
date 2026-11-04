"""Look and feel: one CSS block on top of the colours in .streamlit/config.toml. Display only.

The colours (white page, light-blue surfaces, pink accent) live in config.toml. This adds what a theme
can't: the website frame (content capped at 1100px and centred, a thin top bar, a footer), a slow gradient
drifting behind the page, the gradient band behind the title, the pathway line that draws itself in that band,
rounded and softly shadowed cards, and a little more space between sections. Cards, forms and the expander keep
solid surfaces, so only plain page text sits on the moving background (dark text is over 14:1, captions over 6:1).
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

# A solid grey-blue for captions and placeholders. Streamlit draws them at 60% of the text colour, which is
# 4.5:1 on the light blue and only just; this is 7:1 and keeps them readable on every surface.
_QUIET_TEXT = "#4B5563"
_SOFT_BORDER = "#C9DDF5"

# Widest the page content gets on a big screen.
_PAGE_MAX_WIDTH = "1100px"

_CSS = f"""
/* The style element itself takes no room at the top of the page. */
[data-testid="stElementContainer"]:has([data-testid="stHtml"]) {{ display: none; }}

/* Website frame: wide layout, but the content is capped and centred. */
div[data-testid="stMainBlockContainer"] {{ max-width: {_PAGE_MAX_WIDTH}; }}

/* Background: a slow gradient drifting between white, light blue and pink. Only plain page text sits straight
   on it: dark text is over 14:1 on every stop, captions over 6:1 and links 4.8:1 on the pink. */
div[data-testid="stApp"] {{
  background-color: #FFFFFF;
  background-image: linear-gradient(120deg, #FFFFFF 0%, #EEF6FF 25%, #FCE4EC 50%, #EEF6FF 75%, #FFFFFF 100%);
  background-size: 300% 300%;
  animation: cp-drift 45s ease-in-out infinite;
}}
@keyframes cp-drift {{
  0% {{ background-position: 0% 50%; }}
  50% {{ background-position: 100% 50%; }}
  100% {{ background-position: 0% 50%; }}
}}

/* Top bar: Guide and the brand on the left, the demo account on the right. It wraps onto a second row on a phone. */
.st-key-{TOPBAR_KEY} {{
  border-bottom: 1px solid {_SOFT_BORDER};
  padding-bottom: 0.6rem;
  margin-bottom: 0.5rem;
}}
.st-key-{BRAND_KEY} [data-testid="stMarkdownContainer"] p {{ margin: 0; font-size: 1.15rem; white-space: nowrap; }}
.st-key-{BRAND_KEY} [data-testid="stElementToolbar"] {{ display: none; }}  /* a logo needs no enlarge button */

/* Hero: a soft light-blue to pink band behind the title and tagline (dark text on both ends is over 14:1). */
.st-key-{HERO_KEY} {{
  background: linear-gradient(135deg, #EEF6FF 0%, #FCE4EC 100%);
  border-radius: 1rem;
  padding: 0.75rem 1.25rem 1rem;
  margin-bottom: 0.5rem;
  box-shadow: 0 2px 8px rgba(17, 24, 39, 0.08);
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

/* Captions and placeholders stay readable on the light blue and on the pink. */
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {{ color: {_QUIET_TEXT}; }}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stSelectbox"] input::placeholder,
[data-testid="stMultiSelect"] input::placeholder {{ color: {_QUIET_TEXT}; opacity: 1; }}

/* The footer: centred, below a divider. */
.st-key-{FOOTER_KEY} {{ text-align: center; }}

/* Anyone who asks for less motion gets none: the background stands still and the pathway is fully drawn. */
@media (prefers-reduced-motion: reduce) {{
  div[data-testid="stApp"] {{ animation: none !important; }}
  .cp-pathway .cp-draw {{ animation: none !important; stroke-dashoffset: 0 !important; }}
}}
"""


def apply_theme() -> None:
    """Add the CSS block. Call once, at the top of app.py, right after st.set_page_config."""
    st.html(f"<style>{_CSS}</style>")
