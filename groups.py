"""Groups, form lists and advisor rules shared by the engine, the advisor and the UI.

The UI may import GROUPS and NCS_URL from here (see CONTRACT v1 in CLAUDE.md).
"""

from __future__ import annotations

# A user with at least this many years of work experience is a "career changer".
CAREER_CHANGER_MIN_YEARS = 3

NCS_URL = "https://nationalcareers.service.gov.uk"

# Qualification ids a profile may carry (the "qualification" key), in display order.
QUALIFICATIONS = {
    "no_quals": "No formal qualifications",
    "gcse": "GCSEs or equivalent",
    "level3": "A-levels, T Level, BTEC or other Level 3",
    "graduate": "Degree or other higher education",
}

_UNDER_YEARS = f"less than {CAREER_CHANGER_MIN_YEARS} years of work experience"

# Ordered. advisor_instructions set tone and emphasis only; facts come from the engine results.
GROUPS = {
    "no_quals": {
        "label": "No formal qualifications",
        "description": (
            f"You have no formal qualifications and {_UNDER_YEARS}."
        ),
        "advisor_instructions": (
            "Be warm and encouraging. Use short, plain sentences and no jargon. "
            "Lead with the entry route for their situation, then the free and funded courses. "
            "Make clear that no qualifications is a starting point, not a closed door."
        ),
    },
    "gcse": {
        "label": "GCSE level",
        "description": (
            f"Your highest qualification is GCSEs or equivalent and you have {_UNDER_YEARS}."
        ),
        "advisor_instructions": (
            "Be friendly and practical. Emphasise the next step up from where they are "
            "and any route in the results that lets them earn while they learn."
        ),
    },
    "level3": {
        "label": "A-level / Level 3",
        "description": (
            "Your highest qualification is A-levels, a T Level, a BTEC or another "
            f"Level 3 qualification and you have {_UNDER_YEARS}."
        ),
        "advisor_instructions": (
            "Be clear and respectful. Emphasise how their Level 3 qualification connects "
            "to the routes in the results and which short courses fill the remaining gaps."
        ),
    },
    "graduate": {
        "label": "Graduate",
        "description": (
            "You have a degree or other higher education qualification and "
            f"{_UNDER_YEARS}."
        ),
        "advisor_instructions": (
            "Be professional and concise. Emphasise skills that transfer from a degree and "
            "the quickest way to close the gaps. Don't assume the degree is in a related subject."
        ),
    },
    "career_changer": {
        "label": "Career changer",
        "description": (
            f"You have {CAREER_CHANGER_MIN_YEARS} or more years of work experience, "
            "whatever your qualifications."
        ),
        "advisor_instructions": (
            "Be respectful of their experience and acknowledge the skills they already hold. "
            "Emphasise transferable skills and the fastest way to close what is missing."
        ),
    },
}

# Dropdown options for the "town" question. Never used for ranking.
NE_TOWNS = [
    "Newcastle upon Tyne",
    "Gateshead",
    "Sunderland",
    "South Shields",
    "North Shields",
    "Durham",
    "Darlington",
    "Hartlepool",
    "Middlesbrough",
    "Stockton-on-Tees",
    "Redcar",
    "Blyth",
    "Ashington",
    "Hexham",
    "Bishop Auckland",
    "Other North East",
]

# Shared by every group. The advisor builds its system prompt from this plus the
# group's advisor_instructions.
BASE_ADVISOR_RULES = f"""You are a careers adviser for people in the North East of England. Follow these rules:
- Use only the RESULTS below. Never add careers, courses, colleges, qualifications, pay, costs, links or other facts from anywhere else.
- Cite every career and course as "Title [ID]", written exactly as in the results, e.g. "Data analyst [CAR04]".
- Only use £ figures and links that appear in the results.
- Mention typical pay, flag any unpaid placement and put free and funded courses first.
- Never call a route impossible or closed. If the usual route doesn't fit, give the longer route from the results.
- Never promise a job, a place on a course or a paid placement.
- If the results don't answer the question, say you're not sure and end with: "The National Careers Service can help: {NCS_URL}".
- Keep the answer under 120 words, in plain English. Never ask for personal details."""
