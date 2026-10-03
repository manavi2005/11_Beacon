"""Internal chart API and Vega-Lite charts for Beacon.

Assignment 4, Part 1. Three layers, each usable on its own:

1. Row builders (skill_summary_rows, assessment_rows).
   Plain lists of flat dicts straight from the ORM. Flat on purpose: Vega-Lite
   reads an array of records with no unwrapping, and so does pandas, a
   spreadsheet, or a classmate pasting the URL into the online editor.

2. Specs (preparation/vega_lite/*.vl.json).
   Hand-written Vega-Lite JSON, kept as data files rather than Python dicts so
   they can be pasted into the Vega-Lite editor unchanged. Each one loads its
   rows with data: {"url": "/api/..."} and never carries inline values.

3. Renderers (spec_for_editor, render_png).
   spec_for_editor() turns the relative data URL into an absolute one, so the
   spec works outside this site. render_png() draws the chart on the server
   with vl-convert, so every chart also has its own .png URL.

Why render_png() swaps the URL for the rows instead of letting vl-convert
fetch the API itself: that would make the server send an HTTP request to
itself while it is still handling the PNG request. Under the single-worker
setups used for small deployments, the worker would be waiting on itself and
the request would hang until it timed out. The rows come from the same
function the API view calls, so the picture cannot drift from the API.
"""

import copy
import json
from pathlib import Path

import vl_convert as vlc
from django.db.models import Avg, Count, F

from .models import Skill, SkillAssessment

SPEC_DIR = Path(__file__).resolve().parent / "vega_lite"

# The Vega-Lite release the specs are written against. The page loads the same
# version from the CDN, and vl-convert ships it, so browser and server draw
# identical charts.
VEGA_LITE_VERSION = "6.4"

# Public chart number -> spec file and the API route its data comes from.
CHARTS = {
    1: {
        "file": "skill_gap_bar.vl.json",
        "title": "Widest skill gaps",
        "kind": "Bar chart (aggregated summary)",
        "api_name": "preparation:api_skill_summary",
    },
    2: {
        "file": "assessment_scatter.vl.json",
        "title": "Proficiency against requirement",
        "kind": "Scatter plot",
        "api_name": "preparation:api_assessments",
    },
}


# ---------------------------------------------------------------------------
# 1. Row builders - the data behind the internal API
# ---------------------------------------------------------------------------
def skill_summary_rows():
    """One row per skill, aggregated by the database.

    Skills nobody has been assessed on are still listed, with learners = 0 and
    null averages, so the API describes the whole catalog. The bar chart
    filters those rows out itself.
    """
    skills = (
        Skill.objects.annotate(
            learners=Count("assessments", distinct=True),
            avg_proficiency=Avg("assessments__proficiency_score"),
            avg_required=Avg("assessments__required_level"),
            task_count=Count("tasks", distinct=True),
        )
        .order_by("name")
    )
    rows = []
    for skill in skills:
        proficiency = _round(skill.avg_proficiency)
        required = _round(skill.avg_required)
        rows.append({
            "skill": skill.name,
            "category": skill.get_category_display(),
            "learners": skill.learners,
            "avg_proficiency": proficiency,
            "avg_required": required,
            # Negative means the cohort is already above what roles demand.
            "avg_gap": (
                round(required - proficiency, 1)
                if proficiency is not None and required is not None
                else None
            ),
            "tasks": skill.task_count,
        })
    return rows


def assessment_rows():
    """One row per skill assessment.

    Deliberately anonymous: no candidate name, username or email. This
    endpoint is public and meant to be shared with classmates, and the chart
    only needs the scores. Experience level is kept because it is a useful
    grouping and identifies nobody.
    """
    assessments = (
        SkillAssessment.objects.select_related("skill", "candidate")
        .annotate(raw_gap=F("required_level") - F("proficiency_score"))
        .order_by("skill__name", "proficiency_score")
    )
    return [
        {
            "skill": a.skill.name,
            "category": a.skill.get_category_display(),
            "experience": a.candidate.get_experience_level_display(),
            "proficiency": a.proficiency_score,
            "required": a.required_level,
            "gap": a.raw_gap,
            "assessed_on": a.assessed_on.isoformat(),
        }
        for a in assessments
    ]


def _round(value):
    return None if value is None else round(float(value), 1)


# ---------------------------------------------------------------------------
# 2 and 3. Specs and renderers
# ---------------------------------------------------------------------------
def load_spec(number):
    """The spec exactly as written, with its relative data URL."""
    with open(SPEC_DIR / CHARTS[number]["file"], encoding="utf-8") as handle:
        return json.load(handle)


def spec_for_editor(number, build_absolute_uri):
    """The spec with an absolute data URL, ready for the Vega-Lite editor.

    build_absolute_uri is request.build_absolute_uri, so the URL names
    whichever host served it: 127.0.0.1:8000 locally, the real domain once
    deployed. Nothing about the host is hard-coded.
    """
    spec = load_spec(number)
    spec["data"]["url"] = build_absolute_uri(spec["data"]["url"])
    return spec


ROW_BUILDERS = {1: skill_summary_rows, 2: assessment_rows}


def render_png(number, scale=2):
    """Draw chart `number` on the server and return PNG bytes.

    The data URL is replaced by the rows the API would have returned - see the
    module docstring for why the server does not fetch its own API.
    """
    spec = copy.deepcopy(load_spec(number))
    spec["data"] = {"values": ROW_BUILDERS[number]()}
    return vlc.vegalite_to_png(spec, vl_version=VEGA_LITE_VERSION, scale=scale)
