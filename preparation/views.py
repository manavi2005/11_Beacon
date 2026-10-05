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

from functools import wraps

from django.db.models import Avg, Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.template import loader
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_safe
from django.views.generic import CreateView, DetailView, ListView

from . import charts, exports, market, vega
from .models import (
    CandidateProfile,
    PlanTask,
    PreparationPlan,
    Skill,
    SkillAssessment,
)

from .forms import PlanTaskForm

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
# SECTION 1 - Detail pages, addressed by primary key
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
# SECTION 2 - Search form 1: GET
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
    invalid_category = ""

    if query:
        # __icontains: case-insensitive substring match.
        skills = skills.filter(name__icontains=query)
        filters_applied.append(f'name contains "{query}"')

    if category:
        # The code arrives straight from the query string, so it cannot be
        # trusted to be one of the real choices. Look the label up instead of
        # calling Skill.Category(category), which raises ValueError on anything
        # unrecognised and would turn a hand-edited URL into a 500.
        label = dict(Skill.Category.choices).get(category)

        if label is None:
            # Unknown code: match nothing and say so, rather than silently
            # ignoring the filter and showing the whole catalog.
            skills = skills.none()
            invalid_category = category
            filters_applied.append(f'category "{category}" is not a category')
        else:
            # __exact: the category code must match exactly.
            skills = skills.filter(category__exact=category)
            filters_applied.append(f"category is {label}")

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
        "invalid_category": invalid_category,
        "total_in_catalog": Skill.objects.count(),
        "matches": skills.count(),
    }
    return render(request, "preparation/skill_search.html", context)


# ---------------------------------------------------------------------------
# SECTION 2 - Search form 2: POST
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
class CandidateSearchView(View):
    """Look up candidates with request.POST.

    Inheriting View dispatches by method: GET shows the empty form, POST runs
    the search. A blank term returns nothing rather than every candidate, so
    the page never lists personal records that nobody asked for.
    """

    template_name = "preparation/candidate_search.html"

    def get(self, request):
        return render(request, self.template_name, {
            "searched": False,
            "term": "",
            "results": None,
        })

    def post(self, request):
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

        return render(request, self.template_name, {
            "searched": True,
            "term": term,
            "results": results,
        })


# ---------------------------------------------------------------------------
# SECTION 2 - Aggregations
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


# ---------------------------------------------------------------------------
# SECTION 4 - Matplotlib charts served as PNG endpoints
#
# Each endpoint returns image/png rather than HTML, so the URL can be used
# directly as the src of an <img>. The drawing itself lives in charts.py; the
# views below only choose a chart, set the content type, and say how long the
# response may be cached.
#
# Why the charts are not inlined as base64 data URIs instead: a separate URL
# means the browser fetches the image on its own connection, caches it under
# its own key, and can reuse it across pages. A data URI is re-sent inside
# every HTML response and cannot be cached separately.
# ---------------------------------------------------------------------------
def _png(image_bytes, *, max_age=300):
    """Wrap raw PNG bytes in an HttpResponse.

    Content-Length is set so the browser can show real progress and knows the
    response is complete. Cache-Control is deliberately short: the underlying
    rows change whenever someone completes a task, and a stale chart is worse
    than a re-render that costs a few milliseconds.
    """
    response = HttpResponse(image_bytes, content_type="image/png")
    response["Content-Length"] = str(len(image_bytes))
    response["Cache-Control"] = f"max-age={max_age}"
    return response


def chart_skills_by_category(request):
    """/charts/skills-by-category.png"""
    return _png(charts.skills_by_category_png())


def chart_plan_progress(request):
    """/charts/plan-progress.png"""
    return _png(charts.plan_progress_png())


def chart_skill_gap(request):
    """/charts/skill-gap.png"""
    return _png(charts.skill_gap_png())


def chart_task_status(request):
    """/charts/task-status.png"""
    return _png(charts.task_status_png())


def charts_page(request):
    """The page that displays all four charts.

    The numbers beside each chart come from the same ORM aggregates the charts
    are drawn from, so a reader who cannot see the images still gets the
    figures, and the alt text on each <img> describes what the chart shows
    rather than repeating its title.
    """
    status_counts = (
        PlanTask.objects.values("status").annotate(total=Count("id")).order_by("-total")
    )

    context = {
        "category_rows": [
            {
                "label": Skill.Category(row["category"]).label,
                "total": row["total"],
            }
            for row in Skill.objects.values("category")
            .annotate(total=Count("id"))
            .order_by("-total")
        ],
        "status_rows": [
            {
                "label": PlanTask.Status(row["status"]).label,
                "total": row["total"],
            }
            for row in status_counts
        ],
        "task_total": PlanTask.objects.count(),
        "plan_total": PreparationPlan.objects.count(),
        "assessed_skill_count": Skill.objects.annotate(
            learners=Count("assessments", distinct=True)
        ).filter(learners__gt=0).count(),
    }
    return render(request, "preparation/charts.html", context)

class PlanTaskCreateView(CreateView):
    """Create a new preparation task using a POST form.

    GET displays the form.
    POST validates the submitted data and creates a PlanTask.
    A successful submission redirects to the new task's detail page using
    PlanTask.get_absolute_url().
    """

    model = PlanTask
    form_class = PlanTaskForm
    template_name = "preparation/task_form.html"
def skill_api(request):

    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()

    skills = Skill.objects.all().order_by("name")
    if query:
        skills = skills.filter(name__icontains=query)

    if category:
        skills = skills.filter(category=category)

    data = {
        "count": skills.count(),
        "results": [
            {
                "id": skill.pk,
                "name": skill.name,
                "category": skill.category,
                "category_label": skill.get_category_display(),
            }
            for skill in skills
        ],
    }

    return JsonResponse(data)


# ===========================================================================
# ASSIGNMENT 4
# ===========================================================================
# ---------------------------------------------------------------------------
# Part 1.1 - Internal JSON API for charts
#
# GET only, JSON only, rows straight from the models. Each response is a bare
# array of flat records, which is what Vega-Lite's data: {url: ...} reads
# without any format hints.
#
# Access-Control-Allow-Origin: * lets a page on another origin - the online
# Vega-Lite editor, or a classmate's site - fetch these URLs from the
# browser. That is safe here because the endpoints are read-only and return
# no personal data: assessment rows carry scores, never names or emails.
# ---------------------------------------------------------------------------
def _api_response(data, status=200):
    response = JsonResponse(data, safe=False, status=status)
    response["Access-Control-Allow-Origin"] = "*"
    return response


def public_api(view):
    """Read-only, cross-origin JSON endpoint.

    GET and HEAD run the view. OPTIONS answers the browser's CORS preflight
    without running it: Chrome sends one before a page on a public site
    (vega.github.io/editor) may read from a private address such as
    127.0.0.1, and only proceeds if Access-Control-Allow-Private-Network
    comes back. Anything else is 405, so the endpoint can never write.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type"
            response["Access-Control-Allow-Private-Network"] = "true"
            response["Access-Control-Max-Age"] = "86400"
            return response
        return require_safe(view)(request, *args, **kwargs)

    return wrapper


@public_api
def api_skill_summary(request):
    """/api/skills/summary/ - one aggregated row per skill."""
    return _api_response(vega.skill_summary_rows())


@public_api
def api_assessments(request):
    """/api/assessments/ - one anonymous row per skill assessment."""
    return _api_response(vega.assessment_rows())


# ---------------------------------------------------------------------------
# Part 1.2 - Vega-Lite charts
#
# Every chart is reachable three ways:
#   /vega-lite/                 both charts embedded in a page (vega-embed)
#   /vega-lite/chart<N>.json    the spec, with an absolute data URL, ready to
#                               paste into the Vega-Lite editor
#   /vega-lite/chart<N>.png     the same chart drawn on the server
# ---------------------------------------------------------------------------
def _chart_or_404(number):
    if number not in vega.CHARTS:
        raise Http404("No such chart.")
    return vega.CHARTS[number]


def vega_lite_page(request):
    """The page that embeds both Vega-Lite charts."""
    charts_info = [
        {"number": number, **info, "api_url": reverse(info["api_name"])}
        for number, info in vega.CHARTS.items()
    ]
    return render(request, "preparation/vega_lite.html", {"charts": charts_info})


@public_api
def vega_lite_spec(request, number):
    """/vega-lite/chart<N>.json"""
    _chart_or_404(number)
    return _api_response(vega.spec_for_editor(number, request.build_absolute_uri))


@require_safe
def vega_lite_png(request, number):
    """/vega-lite/chart<N>.png"""
    _chart_or_404(number)
    return _png(vega.render_png(number))


# ---------------------------------------------------------------------------
# Part 2 - External API (Jobicy), triangulated with internal skill gaps
#
# Two views over the same market.market_report():
#   /api/market-demand/?q=<role>   the processed result as JSON
#   /market/?q=<role>              the same result as a page
# The external call, the error handling and the analysis live in market.py,
# so neither view knows anything about Jobicy.
# ---------------------------------------------------------------------------
@public_api
def api_market_demand(request):
    """/api/market-demand/?q=data analyst"""
    query = request.GET.get("q", "").strip()
    if not query:
        return _api_response(
            {"error": "Add a role to search for, e.g. ?q=data analyst"}, status=400
        )
    try:
        report = market.market_report(query)
    except market.MarketDataError as exc:
        return _api_response({"error": exc.message, "query": query}, status=exc.status)
    return _api_response(report)


@require_safe
def market_page(request):
    """/market/?q=data analyst"""
    query = request.GET.get("q", "").strip()
    context = {
        "query": query,
        "report": None,
        "error": None,
        "suggestions": sorted(
            set(CandidateProfile.objects.values_list("target_role", flat=True))
        ),
    }
    if query:
        try:
            context["report"] = market.market_report(query)
        except market.MarketDataError as exc:
            context["error"] = exc.message
    return render(request, "preparation/market.html", context)


# ---------------------------------------------------------------------------
# ASSIGNMENT 4, PART 3 - CSV and JSON exports, and the reports page
#
# Both exports describe the same model (CandidateProfile) and are built from
# the same rows, in preparation/exports.py. The only thing that differs here
# is how those rows are serialised and what filename they are offered under.
#
# The Content-Disposition header is what turns a response into a download:
# "attachment" tells the browser to save rather than display, and filename=
# is what it saves as. Without it, the CSV would render as text in the tab
# and the JSON would open in the browser's JSON viewer.
# ---------------------------------------------------------------------------
def export_candidates_csv(request):
    """Every candidate as a CSV download.

    URL: /reports/candidates.csv

    charset=utf-8 is on the content type because the data contains real
    names: without it a spreadsheet may fall back to a local 8-bit encoding
    and turn any non-ASCII character into mojibake.
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{exports.export_filename("csv")}"'
    )
    # HttpResponse is a file-like object, so csv writes straight into the
    # response rather than building the whole file in memory first.
    exports.write_csv(response, exports.candidate_rows())
    return response


def export_candidates_json(request):
    """The same candidates as a JSON download, with metadata.

    URL: /reports/candidates.json

    generated_at and record_count are what make a downloaded file readable
    six weeks later: without them it is a bare array with no way to tell when
    it was taken or whether it is complete.
    """
    rows = exports.candidate_rows()
    payload = {
        "generated_at": timezone.localtime().isoformat(),
        "record_count": len(rows),
        "candidates": rows,
    }
    response = JsonResponse(
        payload,
        # indent=2 so the file a user opens is readable rather than one long
        # line. It costs a little size and is worth it for a download.
        json_dumps_params={"indent": 2},
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{exports.export_filename("json")}"'
    )
    return response


def reports_page(request):
    """Grouped summaries, totals, and the two download buttons.

    URL: /reports/

    Every number on this page is a database aggregate, and the same
    candidate rows that back the exports are listed underneath, so what you
    see is what you download.
    """
    rows = exports.candidate_rows()
    context = {
        "totals": exports.report_totals(),
        "by_experience": exports.candidates_by_experience(),
        "by_role": exports.candidates_by_role(),
        "by_plan": exports.tasks_by_plan(),
        "headers": [label for _, label in exports.EXPORT_COLUMNS],
        # Cells are aligned to EXPORT_COLUMNS here rather than looked up by
        # key in the template: Django has no dict-lookup-by-variable filter,
        # and flattening in the view keeps the column order defined in exactly
        # one place for the page and both downloads.
        "rows": [
            [row[key] for key, _ in exports.EXPORT_COLUMNS] for row in rows
        ],
        "csv_name": exports.export_filename("csv"),
        "json_name": exports.export_filename("json"),
    }
    return render(request, "preparation/reports.html", context)
