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
