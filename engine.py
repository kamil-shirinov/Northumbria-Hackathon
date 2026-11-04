"""Deterministic career engine. No LLM and no network: it makes every decision.

Implements the engine half of CONTRACT v1 (see CLAUDE.md). Every return value is plain
Python (str, int, float, bool, list, dict), never pandas or numpy types.

Status: assign_group and skills_gap are final. rank_careers and recommend_courses are
first passes: the shape and ordering rules are the contract, the scoring is placeholder.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from groups import (
    CAREER_CHANGER_MIN_YEARS,
    GROUPS,
    NCS_URL,
    NE_TOWNS,
    QUALIFICATIONS,
)

_ROOT = Path(__file__).resolve().parent


def _resolve_data_dir() -> Path:
    return Path(os.environ.get("CP_DATA_DIR") or _ROOT / "data")


DATA_DIR: Path = _resolve_data_dir()

_DEMAND_RANK = {"high": 2, "medium": 1, "low": 0}

# Loaded once and cached; reload_data() clears it.
_cache: dict | None = None


# --------------------------------------------------------------------------- data loading


def reload_data(data_dir: str | os.PathLike | None = None) -> None:
    """Forget the cached CSVs so the next call re-reads them. For tests.

    Re-reads CP_DATA_DIR (or ./data) unless data_dir is given.
    """
    global DATA_DIR, _cache
    DATA_DIR = Path(data_dir) if data_dir else _resolve_data_dir()
    _cache = None


def _norm(text: object) -> str:
    """Key used to compare skills and sectors: case and surrounding spaces don't matter."""
    return str(text).strip().casefold()


def _split(cell: str) -> list[str]:
    """Split a semicolon-separated cell; drop blanks and repeats (same key), keep order."""
    seen: set[str] = set()
    out: list[str] = []
    for part in cell.split(";"):
        part = part.strip()
        if part and _norm(part) not in seen:
            seen.add(_norm(part))
            out.append(part)
    return out


def _number(cell: str, where: str) -> float:
    try:
        return float(cell.replace("£", "").replace(",", "").strip())
    except ValueError:
        raise ValueError(f"{where}: expected a number, got {cell!r}") from None


def _read_rows(name: str) -> list[dict[str, str]]:
    # utf-8-sig tolerates a BOM if a CSV was saved through Excel.
    df = pd.read_csv(DATA_DIR / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return [{k: str(v).strip() for k, v in row.items()} for row in df.to_dict("records")]


def _mentions_unpaid(*texts: str) -> bool:
    return any("unpaid" in t.casefold() for t in texts)


def _load() -> dict:
    careers = []
    for row in _read_rows("careers.csv"):
        where = f"careers.csv {row['career_id']}"
        careers.append(
            {
                "career_id": row["career_id"],
                "title": row["title"],
                "sector": row["sector"],
                "ne_demand": row["ne_demand"].casefold(),
                "pay_min": int(round(_number(row["pay_min"], f"{where} pay_min"))),
                "pay_max": int(round(_number(row["pay_max"], f"{where} pay_max"))),
                "routes": {g: row.get(f"entry_route_{g}", "") for g in GROUPS},
                "skills": _split(row["skills"]),
                "source_url": row["source_url"],
            }
        )
    courses = []
    for row in _read_rows("courses.csv"):
        where = f"courses.csv {row['course_id']}"
        courses.append(
            {
                "course_id": row["course_id"],
                "title": row["title"],
                "provider": row["provider"],
                "cost_gbp": float(_number(row["cost_gbp"], f"{where} cost_gbp")),
                "funded": row["funded"].casefold() == "yes",
                "length_weeks": float(_number(row["length_weeks"], f"{where} length_weeks")),
                "format": row["format"],
                "entry_requirements": row["entry_requirements"],
                "skills_taught": _split(row["skills_taught"]),
                "source_url": row["source_url"],
            }
        )
    return {
        "careers": careers,
        "careers_by_id": {c["career_id"]: c for c in careers},
        "courses": courses,
    }


def _data() -> dict:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


# --------------------------------------------------------------------------- profile helpers


def _held_skills(profile: dict) -> set[str]:
    return {_norm(s) for s in (profile.get("skills") or [])}


def _years(profile: dict) -> int:
    try:
        return int(profile.get("experience_years") or 0)
    except (TypeError, ValueError):
        return 0


def _resolve_group(profile: dict, group: str | None) -> str:
    """An unknown or empty group falls back to the profile's own group."""
    return group if group in GROUPS else assign_group(profile)


# --------------------------------------------------------------------------- contract


def form_options() -> dict:
    """Everything the UI needs to build its form."""
    data = _data()
    sectors = {_norm(c["sector"]): c["sector"] for c in data["careers"]}
    skills = {_norm(s): s for c in data["careers"] for s in c["skills"]}
    return {
        "qualifications": [{"id": qid, "label": label} for qid, label in QUALIFICATIONS.items()],
        "groups": [
            {"id": gid, "label": g["label"], "description": g["description"]}
            for gid, g in GROUPS.items()
        ],
        "interests": sorted(sectors.values()),
        "skills": sorted(skills.values()),
        "towns": list(NE_TOWNS),
    }


def assign_group(profile: dict) -> str:
    """FINAL. "career_changer" with enough experience, otherwise the qualification.

    A missing or unrecognised qualification falls back to "no_quals", the most open
    group (no closed doors).
    """
    if bool(profile.get("has_experience")) and _years(profile) >= CAREER_CHANGER_MIN_YEARS:
        return "career_changer"
    qualification = profile.get("qualification")
    return qualification if qualification in QUALIFICATIONS else "no_quals"


def _entry_route(career: dict, group: str) -> str:
    route = career["routes"].get(group, "")
    if route:
        return route
    return (
        "Longer route: there is no set entry route for your situation yet. "
        "Start with a related entry-level role, an apprenticeship or a short course, "
        f"and talk to the National Careers Service ({NCS_URL}) about the best way in."
    )


def _skills_reason(held: int, total: int) -> str | None:
    if total == 0:
        return None
    if held == 0:
        return f"You have none of its {total} skills yet, but you can build them"
    if held == total and total > 1:
        return f"You already have all {total} skills"
    return f"You already have {held} of {total} {'skill' if total == 1 else 'skills'}"


def rank_careers(profile: dict, group: str, n: int = 5) -> list[dict]:
    """FIRST PASS. Best first, never empty (at least one career whenever the data has any).

    Sort order: sector is one of the user's interests, then the share of the career's
    skills already held, then NE demand (high > medium > low), then career_id.
    "score" encodes that same order as one number (higher is better) so it is safe to
    sort on; it is not a percentage and the UI should show "reasons", not the score.
    """
    group = _resolve_group(profile, group)
    interests = {_norm(i) for i in (profile.get("interests") or [])}
    held_skills = _held_skills(profile)

    ranked = []
    for c in _data()["careers"]:
        liked = _norm(c["sector"]) in interests
        total = len(c["skills"])
        held = sum(_norm(s) in held_skills for s in c["skills"])
        share = held / total if total else 0.0
        demand = _DEMAND_RANK.get(c["ne_demand"], 0)

        reasons = []
        if liked:
            reasons.append(f"Matches your interest in {c['sector']}")
        skills_reason = _skills_reason(held, total)
        if skills_reason:
            reasons.append(skills_reason)
        if c["ne_demand"] in _DEMAND_RANK:
            reasons.append(f"{c['ne_demand'].capitalize()} demand in the North East")

        route = _entry_route(c, group)
        career = {
            "career_id": c["career_id"],
            "title": c["title"],
            "sector": c["sector"],
            "ne_demand": c["ne_demand"],
            "pay_min": c["pay_min"],
            "pay_max": c["pay_max"],
            "entry_route": route,
            "unpaid_placement": _mentions_unpaid(route),
            "skills": list(c["skills"]),
            "source_url": c["source_url"],
            "score": round(liked * 100.0 + share * 10.0 + demand * 0.01, 4),
            "reasons": reasons,
        }
        ranked.append(((not liked, -share, -demand, c["career_id"]), career))

    ranked.sort(key=lambda pair: pair[0])
    return [career for _, career in ranked[: max(1, n)]]


def skills_gap(profile: dict, career: dict | str) -> dict:
    """FINAL. Split the career's skills into held and missing, in the career's order.

    career is a career dict from rank_careers or a career_id.
    """
    if isinstance(career, str):
        try:
            career = _data()["careers_by_id"][career]
        except KeyError:
            raise ValueError(f"Unknown career_id: {career!r}") from None
    held = _held_skills(profile)
    have, missing = [], []
    for skill in career.get("skills") or []:
        (have if _norm(skill) in held else missing).append(str(skill))
    return {"have": have, "missing": missing}


def recommend_courses(missing: list[str], profile: dict, n: int = 5) -> list[dict]:
    """FIRST PASS. Courses that close at least one missing skill, best first.

    Order: most missing skills closed, then free or funded first, then cheaper, then
    shorter, then course_id. profile is accepted for the contract but not used: nothing
    about the person changes which courses exist.
    """
    wanted: dict[str, str] = {}
    for skill in missing or []:
        wanted.setdefault(_norm(skill), str(skill))
    if not wanted or n < 1:
        return []

    ranked = []
    for c in _data()["courses"]:
        taught = {_norm(s) for s in c["skills_taught"]}
        closes = [label for key, label in wanted.items() if key in taught]
        if not closes:
            continue
        free_or_funded = c["cost_gbp"] == 0 or c["funded"]
        course = {
            "course_id": c["course_id"],
            "title": c["title"],
            "provider": c["provider"],
            "cost_gbp": c["cost_gbp"],
            "funded": c["funded"],
            "free_or_funded": free_or_funded,
            "length_weeks": c["length_weeks"],
            "format": c["format"],
            "entry_requirements": c["entry_requirements"],
            "skills_taught": list(c["skills_taught"]),
            "closes": closes,
            "unpaid_placement": _mentions_unpaid(c["title"], c["format"], c["entry_requirements"]),
            "source_url": c["source_url"],
        }
        key = (-len(closes), not free_or_funded, c["cost_gbp"], c["length_weeks"], c["course_id"])
        ranked.append((key, course))

    ranked.sort(key=lambda pair: pair[0])
    return [course for _, course in ranked[:n]]
