"""CSV and JSON exports, and the aggregates behind the reports page.

Assignment 4, Part 3.

The exported model is CandidateProfile: it is the row a user of Beacon would
actually want out of the system, and it is the closest thing this project has
to the assignment's "Students" example.

One rule shapes this module: the CSV and the JSON are built from the same
function. candidate_rows() returns a list of flat dicts, EXPORT_COLUMNS fixes
their order, and both views read from those two names. If they each built
their own rows, the two downloads could drift apart without anything failing,
and nobody would notice until a user compared them. There is a test asserting
the two files describe the same records.

Rows are ordered explicitly rather than relying on Meta.ordering, which is
"-updated_at" on this model: a file whose row order changes every time
somebody edits a profile is a file you cannot diff between two downloads.
"""

import csv
from datetime import datetime

from django.db.models import Avg, Count, F, FloatField, Q
from django.utils import timezone

from .models import CandidateProfile, PlanTask, PreparationPlan, SkillAssessment

# Column order for the CSV, and the key order inside each JSON record.
# Headers are human-readable because the file is opened in a spreadsheet far
# more often than it is parsed.
EXPORT_COLUMNS = [
    ("id", "ID"),
    ("username", "Username"),
    ("full_name", "Full name"),
    ("email", "Email"),
    ("target_role", "Target role"),
    ("target_company", "Target company"),
    ("experience_level", "Experience level"),
    ("primary_concern", "Main concern"),
    ("interview_date", "Interview date"),
    ("days_until_interview", "Days until interview"),
    ("timeline_weeks", "Preparation weeks"),
    ("skills_assessed", "Skills assessed"),
    ("average_proficiency", "Average proficiency"),
    ("readiness_percent", "Readiness %"),
    ("plans", "Plans"),
    ("tasks_total", "Tasks"),
    ("tasks_done", "Tasks done"),
    ("joined", "Joined"),
]


def export_queryset():
    """Candidates with their counts, ordered, in one query.

    select_related pulls the User in the same query instead of one per row.
    The annotations mean the per-row numbers come from the database rather
    than from a property called inside a loop, which on 6 candidates is
    invisible and on 6000 is the whole response time.

    distinct=True matters: counting across two different related tables in
    one query multiplies the rows, and the inflated numbers look plausible.
    """
    return (
        CandidateProfile.objects.select_related("user")
        .annotate(
            skills_assessed=Count("assessments", distinct=True),
            average_proficiency=Avg("assessments__proficiency_score"),
            plan_count=Count("plans", distinct=True),
            tasks_total=Count("plans__tasks", distinct=True),
            tasks_done=Count(
                "plans__tasks",
                filter=Q(plans__tasks__status=PlanTask.Status.DONE),
                distinct=True,
            ),
        )
        .order_by("user__username")
    )


def candidate_rows():
    """One flat dict per candidate, in EXPORT_COLUMNS order.

    Flat on purpose: a CSV cell cannot hold a nested object, so building the
    rows flat here is what lets the same structure serve both formats.

    Dates are ISO strings and None stays None. JSON renders None as null;
    csv.DictWriter writes it as an empty cell, which is what a spreadsheet
    expects for "no value" and is not the same as the string "None".
    """
    rows = []
    for candidate in export_queryset():
        user = candidate.user
        average = candidate.average_proficiency
        rows.append(
            {
                "id": candidate.pk,
                "username": user.username,
                "full_name": user.get_full_name(),
                "email": user.email,
                "target_role": candidate.target_role,
                "target_company": candidate.target_company,
                "experience_level": candidate.get_experience_level_display(),
                "primary_concern": candidate.get_primary_concern_display()
                if candidate.primary_concern
                else "",
                "interview_date": candidate.target_interview_date.isoformat()
                if candidate.target_interview_date
                else None,
                "days_until_interview": candidate.days_until_interview,
                "timeline_weeks": candidate.preparation_timeline_weeks,
                "skills_assessed": candidate.skills_assessed,
                "average_proficiency": round(float(average), 1)
                if average is not None
                else None,
                "readiness_percent": candidate.readiness_percent,
                "plans": candidate.plan_count,
                "tasks_total": candidate.tasks_total,
                "tasks_done": candidate.tasks_done,
                "joined": candidate.created_at.date().isoformat(),
            }
        )
    return rows


def export_filename(extension, *, stem="candidates", now=None):
    """candidates_2026-10-04_19-30.csv

    The timestamp is the point: a user downloading the same report twice gets
    two files instead of "candidates (1).csv", and the name says when the
    numbers were true. localtime() so the stamp matches the user's clock
    rather than UTC.
    """
    moment = now or timezone.localtime()
    return f"{stem}_{moment:%Y-%m-%d_%H-%M}.{extension}"


def write_csv(stream, rows):
    """Write the header row and `rows` into an open text stream.

    Takes a stream rather than returning a string so the caller can hand it
    an HttpResponse directly; HttpResponse has a write() method, so csv
    writes straight into the response instead of building the whole file in
    memory first.

    extrasaction="ignore" keeps a stray key in a row from raising, and
    restval="" fills a missing one, so a column list change cannot 500 the
    download.
    """
    writer = csv.DictWriter(
        stream,
        fieldnames=[key for key, _ in EXPORT_COLUMNS],
        extrasaction="ignore",
        restval="",
    )
    # Not writer.writeheader(): that would emit the machine keys. The file is
    # read by people, so it gets the readable labels.
    writer.writerow({key: label for key, label in EXPORT_COLUMNS})
    for row in rows:
        writer.writerow(row)


# ---------------------------------------------------------------------------
# Aggregates for the reports page
# ---------------------------------------------------------------------------
def candidates_by_experience():
    """Grouped summary 1: how many candidates sit at each experience level."""
    labels = dict(CandidateProfile.ExperienceLevel.choices)
    return [
        {
            "label": labels.get(row["experience_level"], row["experience_level"]),
            "candidates": row["candidates"],
            "average_readiness": round(float(row["average_proficiency"]), 1)
            if row["average_proficiency"] is not None
            else None,
        }
        for row in CandidateProfile.objects.values("experience_level")
        .annotate(
            candidates=Count("id", distinct=True),
            average_proficiency=Avg("assessments__proficiency_score"),
        )
        .order_by("-candidates")
    ]


def candidates_by_role():
    """Grouped summary 2: candidates per target role, with their gap.

    The second column is the reason this grouping is worth having: it says
    which roles the cohort is furthest from being ready for.
    """
    return [
        {
            "label": row["target_role"],
            "candidates": row["candidates"],
            "assessments": row["assessment_count"],
            "average_gap": round(float(row["average_gap"]), 1)
            if row["average_gap"] is not None
            else None,
        }
        for row in CandidateProfile.objects.values("target_role")
        .annotate(
            candidates=Count("id", distinct=True),
            # Deliberately NOT called "assessments": an annotation alias that
            # matches a relation name shadows it, and the next line's
            # "assessments__required_level" would then resolve against this
            # Count (an integer) instead of the related table. Django reports
            # that as "Unsupported lookup 'required_level' for IntegerField",
            # which does not obviously point at the alias.
            assessment_count=Count("assessments", distinct=True),
            # The mean of each row's gap rather than the difference of two
            # means. Equivalent when every assessment has both scores, and
            # unambiguous when one is missing.
            average_gap=Avg(
                F("assessments__required_level")
                - F("assessments__proficiency_score"),
                output_field=FloatField(),
            ),
        )
        .order_by("-candidates", "target_role")
    ]


def tasks_by_plan():
    """Grouped summary 3: tasks per plan, done against all.

    This is the assignment's "enrollments per section, active vs all" shape:
    a count and a filtered count of the same relation, side by side.
    """
    rows = []
    for plan in (
        PreparationPlan.objects.select_related("candidate__user")
        .annotate(
            tasks_total=Count("tasks", distinct=True),
            tasks_done=Count(
                "tasks",
                filter=Q(tasks__status=PlanTask.Status.DONE),
                distinct=True,
            ),
        )
        .order_by("target_date")
    ):
        total = plan.tasks_total
        rows.append(
            {
                "plan": plan.title,
                "candidate": plan.candidate.user.get_full_name()
                or plan.candidate.user.username,
                "candidate_url": plan.candidate.get_absolute_url(),
                "plan_url": plan.get_absolute_url(),
                "target_date": plan.target_date,
                "tasks_total": total,
                "tasks_done": plan.tasks_done,
                "percent_done": round(plan.tasks_done / total * 100) if total else 0,
            }
        )
    return rows


def report_totals():
    """The totals line.

    Counted here rather than summed from the groupings above: a grouping can
    silently drop rows whose grouping key is null, and a total that disagrees
    with its own table is worse than no total.
    """
    tasks = PlanTask.objects.count()
    done = PlanTask.objects.filter(status=PlanTask.Status.DONE).count()
    return {
        "candidates": CandidateProfile.objects.count(),
        "assessments": SkillAssessment.objects.count(),
        "plans": PreparationPlan.objects.count(),
        "tasks": tasks,
        "tasks_done": done,
        "percent_done": round(done / tasks * 100) if tasks else 0,
    }
