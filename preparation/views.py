"""Views for the preparation app.

Assignment 2, Section 2 requires four *kinds* of view. The four marked for
grading are labelled below so the mapping is obvious to a reader:

    1. FBV  - HttpResponse   -> skill_catalog_manual   (/skills/manual/)
    2. FBV  - render()       -> skill_catalog_render   (/skills/)
    3. CBV  - base View      -> PlanBoardView          (/plans/cbv-base/)
    4. CBV  - generic CBV    -> PlanTaskListView       (/tasks/)

Everything else in this file is either the Part 4 dashboard (kept so the
existing URL still works) or an extra generic CBV that was cheap to add.

The two FBVs deliberately render the *same* template, so the only difference
between them is how the response is plumbed - that is the whole point of the
exercise, and it is also what Section 3 means by "template reuse".
"""

from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views import View
from django.views.generic import DetailView, ListView

from .models import (
    CandidateProfile,
    PlanTask,
    PreparationPlan,
    Skill,
    SkillAssessment,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _skill_context(request, view_label, explainer):
    """Build the context both skill views need.

    Supports an optional ?q= filter. That filter is not decoration: passing a
    nonsense value (e.g. /skills/?q=zzzz) empties the queryset, which is how we
    capture the empty-state screenshot Section 3 asks for without deleting any
    rows from the database.
    """
    query = request.GET.get("q", "").strip()
    skills = Skill.objects.all()
    if query:
        skills = skills.filter(name__icontains=query)

    return {
        "skills": skills,
        "query": query,
        "view_label": view_label,
        "explainer": explainer,
    }


# ---------------------------------------------------------------------------
# 1. Function-based view - HttpResponse (manual)
# ---------------------------------------------------------------------------
def skill_catalog_manual(request):
    """Load the template by hand, render it to a string, wrap it in HttpResponse.

    This is what render() does internally. Writing it out once makes the
    shortcut in the next view meaningful: find the template, hand it a context,
    get a string back, and put that string inside an HTTP response with the
    right content type.
    """
    context = _skill_context(
        request,
        view_label="View 1 - FBV, HttpResponse + loader.get_template()",
        explainer=(
            "This page was produced manually: loader.get_template() fetched the "
            "template, .render() turned it into a string, and HttpResponse "
            "wrapped that string in a response."
        ),
    )

    template = loader.get_template("preparation/skill_list.html")
    html = template.render(context, request)
    return HttpResponse(html)


# ---------------------------------------------------------------------------
# 2. Function-based view - render() shortcut
# ---------------------------------------------------------------------------
def skill_catalog_render(request):
    """The same page, using the render() shortcut.

    Identical output to skill_catalog_manual - one line instead of three.
    """
    context = _skill_context(
        request,
        view_label="View 2 - FBV, render() shortcut",
        explainer=(
            "Same template and same data as the manual view. render() collapses "
            "the fetch/render/wrap steps into a single call."
        ),
    )
    return render(request, "preparation/skill_list.html", context)


# ---------------------------------------------------------------------------
# 3. Class-based view - base View
# ---------------------------------------------------------------------------
class PlanBoardView(View):
    """Every preparation plan, queried and rendered by hand inside get().

    Inheriting from the bare View gives us URL-to-method dispatch (GET lands in
    get(), POST would land in post()) and nothing else. The queryset, the
    context and the template are all still our job - which is exactly the
    difference from the generic CBV below.
    """

    template_name = "preparation/plan_list.html"

    def get(self, request):
        plans = PreparationPlan.objects.select_related("candidate__user")

        context = {
            "plans": plans,
            "view_label": "View 3 - CBV, base django.views.View",
            "explainer": (
                "A bare View subclass. get() does the querying and calls "
                "render() itself; nothing about the model is inferred."
            ),
        }
        return render(request, self.template_name, context)


# ---------------------------------------------------------------------------
# 4. Class-based view - generic ListView
# ---------------------------------------------------------------------------
class PlanTaskListView(ListView):
    """Every task across every plan, via Django's generic ListView.

    Compared with PlanBoardView: no get(), no manual queryset, no render()
    call. Setting `model` is enough for Django to fetch the rows, build the
    context and pick a template. We override template_name and
    context_object_name anyway so the template reads clearly rather than
    relying on the default `object_list`.
    """

    model = PlanTask
    template_name = "preparation/task_list.html"
    context_object_name = "tasks"
    paginate_by = 25

    def get_queryset(self):
        # select_related avoids one extra query per row when the template
        # prints task.plan.title and task.skill.name.
        return PlanTask.objects.select_related("plan", "skill")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["view_label"] = "View 4 - CBV, generic ListView"
        context["explainer"] = (
            "model = PlanTask is the whole configuration. ListView supplies the "
            "queryset, the context and the pagination."
        )
        return context


# ---------------------------------------------------------------------------
# Extra (not required): generic DetailView
# ---------------------------------------------------------------------------
class PlanTaskDetailView(DetailView):
    """One task in full. Included to show a second generic CBV in use."""

    model = PlanTask
    template_name = "preparation/task_detail.html"
    context_object_name = "task"


# ---------------------------------------------------------------------------
# Part 4 dashboard (kept so the existing route keeps working)
# ---------------------------------------------------------------------------
def dashboard(request):
    """Read-only summary of what is currently in the database."""
    context = {
        "skill_count": Skill.objects.count(),
        "candidate_count": CandidateProfile.objects.count(),
        "assessment_count": SkillAssessment.objects.count(),
        "plan_count": PreparationPlan.objects.count(),
        "task_count": PlanTask.objects.count(),
        "plans": PreparationPlan.objects.select_related("candidate__user")[:10],
    }
    return render(request, "preparation/dashboard.html", context)


# ---------------------------------------------------------------------------
# SECTION 1 — Detail pages, addressed by primary key
#
# Each list page links every row to its own detail page. The links are written
# as {{ object.get_absolute_url }} rather than {% url %}, so the model decides
# where its own page lives.
# ---------------------------------------------------------------------------
class SkillDetailView(DetailView):
    """One skill: who has been assessed on it, and which tasks target it.

    URL: /skills/<pk>/
    """

    model = Skill
    template_name = "preparation/skill_detail.html"
    context_object_name = "skill"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        skill = self.object

        # Relationship spanning: reach through SkillAssessment to the
        # candidate and the User behind them, in one query.
        context["assessments"] = skill.assessments.select_related(
            "candidate__user"
        )
        context["tasks"] = skill.tasks.select_related("plan__candidate__user")

        # Aggregation on a single object: how strong is this skill across
        # everyone who has been measured on it?
        context["average_proficiency"] = skill.assessments.aggregate(
            average=Avg("proficiency_score")
        )["average"]
        return context


class PlanDetailView(DetailView):
    """One preparation plan and the tasks inside it.

    URL: /plans/<pk>/
    """

    model = PreparationPlan
    template_name = "preparation/plan_detail.html"
    context_object_name = "plan"

    def get_queryset(self):
        return PreparationPlan.objects.select_related("candidate__user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tasks"] = self.object.tasks.select_related("skill")
        return context


class CandidateDetailView(DetailView):
    """One candidate: their goal, their scores and their plans.

    URL: /candidates/<pk>/
    """

    model = CandidateProfile
    template_name = "preparation/candidate_detail.html"
    context_object_name = "candidate"

    def get_queryset(self):
        return CandidateProfile.objects.select_related("user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate = self.object
        context["assessments"] = candidate.assessments.select_related("skill")
        context["plans"] = candidate.plans.all()

        # The gap that most needs work: lowest proficiency relative to what
        # the target role requires.
        gaps = sorted(candidate.assessments.select_related("skill"),
                      key=lambda a: -a.gap)
        context["biggest_gaps"] = gaps[:3]
        return context


class CandidateListView(ListView):
    """Every candidate, each annotated with summary numbers.

    URL: /candidates/

    This is the grouped-summary aggregation: one row per candidate, with
    counts and an average computed by the database rather than in Python.
    """

    model = CandidateProfile
    template_name = "preparation/candidate_list.html"
    context_object_name = "candidates"

    def get_queryset(self):
        return (
            CandidateProfile.objects.select_related("user")
            .annotate(
                # distinct=True matters: joining two different related tables
                # in one query would otherwise multiply the row counts.
                assessment_count=Count("assessments", distinct=True),
                plan_count=Count("plans", distinct=True),
                average_proficiency=Avg("assessments__proficiency_score"),
            )
            .order_by("user__username")
        )


# ---------------------------------------------------------------------------
# SECTION 2 — Search form 1: GET
#
# The skill catalog is public reference data. A filtered view of it is worth
# sharing, bookmarking and reloading, so the filter belongs in the URL:
#
#     /search/skills/?q=sql&category=TECH
#
# That link can be pasted into a team chat and it reproduces exactly what the
# sender saw. GET is the right method precisely because the query is visible.
# ---------------------------------------------------------------------------
def skill_search(request):
    """Filter the skill catalog with request.GET."""
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    role = request.GET.get("role", "").strip()

    skills = Skill.objects.all()
    filters_applied = []

    if query:
        # __icontains: case-insensitive substring match.
        skills = skills.filter(name__icontains=query)
        filters_applied.append(f'name contains "{query}"')

    if category:
        # __exact: the category code must match exactly.
        skills = skills.filter(category__exact=category)
        filters_applied.append(
            f"category is {Skill.Category(category).label}"
        )

    if role:
        # RELATIONSHIP SPANNING: skill -> assessments -> candidate -> role.
        # Three tables, one queryset, expressed entirely with __.
        skills = skills.filter(
            assessments__candidate__target_role__icontains=role
        ).distinct()
        filters_applied.append(f'assessed by someone targeting "{role}"')

    # Grouped summary over whatever survived the filters.
    skills = skills.annotate(
        learner_count=Count("assessments", distinct=True),
        task_count=Count("tasks", distinct=True),
        average_proficiency=Avg("assessments__proficiency_score"),
    )

    context = {
        "skills": skills,
        "query": query,
        "category": category,
        "role": role,
        "categories": Skill.Category.choices,
        "filters_applied": filters_applied,
        "total_in_catalog": Skill.objects.count(),
        "matches": skills.count(),
    }
    return render(request, "preparation/skill_search.html", context)


# ---------------------------------------------------------------------------
# SECTION 2 — Search form 2: POST
#
# Candidate records are personal: real names, email addresses, the role
# somebody is quietly job-hunting for. A GET search would write that straight
# into the URL bar, the browser history, the server access log, and any link
# the user later shares or screen-shares.
#
# POST keeps the search term in the request body instead. It is not
# encryption - it is about not leaving personal data lying around in places
# that outlive the request.
#
# The visible cost is the trade-off worth naming: a POST result cannot be
# bookmarked, shared, or reloaded without the browser re-submitting. That is
# exactly the behaviour we want here and exactly the behaviour we do not want
# on the skill catalog above.
# ---------------------------------------------------------------------------
def candidate_search(request):
    """Look up candidates with request.POST."""
    term = ""
    results = None

    if request.method == "POST":
        term = request.POST.get("term", "").strip()

        if term:
            # RELATIONSHIP SPANNING: CandidateProfile -> User, via user__.
            # One Q object per field, OR-ed together, so a single box
            # searches name, username, email and target role at once.
            results = (
                CandidateProfile.objects.select_related("user")
                .filter(
                    Q(user__first_name__icontains=term)
                    | Q(user__last_name__icontains=term)
                    | Q(user__username__icontains=term)
                    | Q(user__email__icontains=term)
                    | Q(target_role__icontains=term)
                    | Q(target_company__icontains=term)
                )
                .annotate(
                    assessment_count=Count("assessments", distinct=True),
                    average_proficiency=Avg("assessments__proficiency_score"),
                )
                .distinct()
            )
        else:
            results = CandidateProfile.objects.none()

    context = {
        "term": term,
        "results": results,
        "searched": request.method == "POST",
    }
    return render(request, "preparation/candidate_search.html", context)


# ---------------------------------------------------------------------------
# SECTION 2 — Aggregations
# ---------------------------------------------------------------------------
def insights(request):
    """Totals and grouped summaries across the whole database.

    URL: /insights/

    Everything on this page is computed by the database. None of it is a
    Python loop over a queryset, which is the difference between one query
    and one query per row.
    """
    # --- TOTALS (count) ---------------------------------------------------
    totals = {
        "skills": Skill.objects.count(),
        "candidates": CandidateProfile.objects.count(),
        "assessments": SkillAssessment.objects.count(),
        "plans": PreparationPlan.objects.count(),
        "tasks": PlanTask.objects.count(),
        "tasks_done": PlanTask.objects.filter(
            status=PlanTask.Status.DONE
        ).count(),
    }

    # --- GROUPED SUMMARY 1: skills by category (values + annotate) --------
    # values() sets the GROUP BY column; annotate() is the aggregate over
    # each group. The result is one dict per category, not one per skill.
    by_category_raw = (
        Skill.objects.values("category")
        .annotate(skill_count=Count("id"))
        .order_by("-skill_count")
    )
    by_category = [
        {
            "label": Skill.Category(row["category"]).label,
            "skill_count": row["skill_count"],
        }
        for row in by_category_raw
    ]

    # --- GROUPED SUMMARY 2: tasks per plan, with completion ---------------
    plans = (
        PreparationPlan.objects.select_related("candidate__user")
        .annotate(
            task_total=Count("tasks", distinct=True),
            # A filtered Count: only the tasks whose status is DONE.
            task_done=Count(
                "tasks",
                filter=Q(tasks__status=PlanTask.Status.DONE),
                distinct=True,
            ),
        )
        .order_by("target_date")
    )

    # --- GROUPED SUMMARY 3: how each skill is doing across all candidates -
    skills = (
        Skill.objects.annotate(
            learner_count=Count("assessments", distinct=True),
            average_proficiency=Avg("assessments__proficiency_score"),
            task_count=Count("tasks", distinct=True),
        )
        .filter(learner_count__gt=0)
        .order_by("average_proficiency")
    )

    # --- RELATIONSHIP SPANNING, optional filter ---------------------------
    # /insights/?role=Data%20Analyst narrows every task to the ones belonging
    # to candidates chasing that role: task -> plan -> candidate -> role.
    role = request.GET.get("role", "").strip()
    tasks = PlanTask.objects.select_related("plan__candidate__user", "skill")
    if role:
        tasks = tasks.filter(plan__candidate__target_role__icontains=role)

    context = {
        "totals": totals,
        "by_category": by_category,
        "plans": plans,
        "skills": skills,
        "role": role,
        "tasks": tasks[:20],
        "task_match_count": tasks.count(),
    }
    return render(request, "preparation/insights.html", context)
