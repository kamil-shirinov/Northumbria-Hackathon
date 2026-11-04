"""Checks on data/careers.csv and data/courses.csv. These must pass on placeholder AND real data."""

import csv
import os
import warnings
from pathlib import Path

import pytest

DATA_DIR = Path(os.environ.get("CP_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")

CAREERS_HEADER = [
    "career_id", "title", "sector", "ne_demand", "pay_min", "pay_max",
    "entry_route_no_quals", "entry_route_gcse", "entry_route_level3",
    "entry_route_graduate", "entry_route_career_changer", "skills", "source_url",
]
COURSES_HEADER = [
    "course_id", "title", "provider", "cost_gbp", "funded", "length_weeks",
    "format", "entry_requirements", "skills_taught", "source_url",
]
ROUTE_COLUMNS = [c for c in CAREERS_HEADER if c.startswith("entry_route_")]


def _read(name):
    with open(DATA_DIR / name, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


@pytest.fixture(scope="module")
def careers():
    return _read("careers.csv")[1]


@pytest.fixture(scope="module")
def courses():
    return _read("courses.csv")[1]


def _skills(cell):
    return [s.strip() for s in cell.split(";") if s.strip()]


def test_headers_are_exact():
    assert _read("careers.csv")[0] == CAREERS_HEADER
    assert _read("courses.csv")[0] == COURSES_HEADER


def test_there_are_rows(careers, courses):
    assert careers and courses


def test_ids_are_present_and_unique(careers, courses):
    for rows, key in ((careers, "career_id"), (courses, "course_id")):
        ids = [r[key].strip() for r in rows]
        assert all(ids), f"blank {key}"
        assert len(ids) == len(set(ids)), f"duplicate {key}: {sorted({i for i in ids if ids.count(i) > 1})}"


def test_ne_demand_values(careers):
    bad = [(r["career_id"], r["ne_demand"]) for r in careers if r["ne_demand"] not in ("high", "medium", "low")]
    assert not bad, f"ne_demand must be high|medium|low: {bad}"


def test_funded_values(courses):
    bad = [(r["course_id"], r["funded"]) for r in courses if r["funded"] not in ("yes", "no")]
    assert not bad, f"funded must be yes|no: {bad}"


def test_pay_is_whole_pounds_and_ordered(careers):
    for r in careers:
        try:
            low, high = int(r["pay_min"]), int(r["pay_max"])
        except ValueError:
            pytest.fail(f"{r['career_id']}: pay must be whole £ a year (no £ or commas): {r['pay_min']!r}, {r['pay_max']!r}")
        assert 0 < low <= high, f"{r['career_id']}: need 0 < pay_min <= pay_max, got {low}, {high}"


def test_course_cost_and_length(courses):
    for r in courses:
        try:
            cost, weeks = float(r["cost_gbp"]), float(r["length_weeks"])
        except ValueError:
            pytest.fail(f"{r['course_id']}: cost_gbp and length_weeks must be numbers: {r['cost_gbp']!r}, {r['length_weeks']!r}")
        assert cost >= 0, f"{r['course_id']}: cost_gbp must be >= 0"
        assert weeks > 0, f"{r['course_id']}: length_weeks must be > 0"


def test_skills_are_not_empty(careers, courses):
    for r in careers:
        assert _skills(r["skills"]), f"{r['career_id']}: skills is empty"
    for r in courses:
        assert _skills(r["skills_taught"]), f"{r['course_id']}: skills_taught is empty"


def test_every_entry_route_is_filled_and_never_closes_the_door(careers):
    for r in careers:
        for col in ROUTE_COLUMNS:
            cell = r[col].strip()
            assert cell, f"{r['career_id']}: {col} is blank"
            assert "not possible" not in cell.casefold(), f"{r['career_id']}: {col} says 'not possible'"


def test_source_urls_are_links(careers, courses):
    for rows, key in ((careers, "career_id"), (courses, "course_id")):
        for r in rows:
            assert r["source_url"].strip().startswith("http"), f"{r[key]}: source_url must start with http"


# --- warnings only: expected while placeholder rows are in the files -----------------


def test_warn_career_skills_no_course_teaches(careers, courses):
    taught = {s.casefold() for r in courses for s in _skills(r["skills_taught"])}
    for r in careers:
        gaps = [s for s in _skills(r["skills"]) if s.casefold() not in taught]
        if gaps:
            warnings.warn(f"{r['career_id']}: no course teaches {gaps}", stacklevel=1)


def test_warn_placeholder_rows_left(careers, courses):
    left = [r[k] for rows, k in ((careers, "career_id"), (courses, "course_id")) for r in rows if r["title"].startswith("PLACEHOLDER")]
    if left:
        warnings.warn(f"{len(left)} PLACEHOLDER rows left: {', '.join(left)}", stacklevel=1)
