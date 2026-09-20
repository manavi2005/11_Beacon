"""URL patterns for the preparation feature.

Every route carries a name= so templates and views can reverse them instead of
hard-coding paths. Because app_name is set, the full reference is namespaced:
{% url 'preparation:skill_catalog_render' %}.

Section 2 routes (the four marked for grading):

    /skills/manual/    -> FBV,  HttpResponse
    /skills/           -> FBV,  render()
    /plans/cbv-base/   -> CBV,  base View
    /tasks/            -> CBV,  generic ListView
"""

from django.urls import path

from . import views

app_name = "preparation"

urlpatterns = [
    # Part 4 dashboard
    path("", views.dashboard, name="dashboard"),
    # --- Section 2: function-based views -----------------------------------
    path("skills/manual/", views.skill_catalog_manual, name="skill_catalog_manual"),
    path("skills/", views.skill_catalog_render, name="skill_catalog_render"),
    # --- Section 2: class-based views --------------------------------------
    path("plans/cbv-base/", views.PlanBoardView.as_view(), name="plan_board"),
    path("tasks/", views.PlanTaskListView.as_view(), name="task_list"),
    # Extra generic CBV
    path("tasks/<int:pk>/", views.PlanTaskDetailView.as_view(), name="task_detail"),
]
