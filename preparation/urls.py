"""URL patterns for the preparation feature.

Every route carries a name= so templates and views can reverse them instead of
hard-coding paths. Because app_name is set, the full reference is namespaced:
{% url 'preparation:skill_catalog_render' %}.

The four core catalog and plan routes, one per kind of Django view:

    /skills/manual/    -> FBV,  HttpResponse
    /skills/           -> FBV,  render()
    /plans/cbv-base/   -> CBV,  base View
    /tasks/            -> CBV,  generic ListView
"""

from django.urls import path

from . import views

app_name = "preparation"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
    # --- Function-based views ----------------------------------------------
    path("skills/manual/", views.skill_catalog_manual, name="skill_catalog_manual"),
    path("skills/", views.skill_catalog_render, name="skill_catalog_render"),
    # --- Class-based views -------------------------------------------------
    path("plans/cbv-base/", views.PlanBoardView.as_view(), name="plan_board"),
    path("tasks/create/", views.PlanTaskCreateView.as_view(), name="task_create"),
    path("tasks/", views.PlanTaskListView.as_view(), name="task_list"),
    # Extra generic CBV
    path("tasks/<int:pk>/", views.PlanTaskDetailView.as_view(), name="task_detail"),
    # =====================================================================
    # Detail pages, search, insights and charts
    # =====================================================================
    # Detail pages addressed by primary key
    path("skills/<int:pk>/", views.SkillDetailView.as_view(), name="skill_detail"),
    path("plans/<int:pk>/", views.PlanDetailView.as_view(), name="plan_detail"),
    path("candidates/", views.CandidateListView.as_view(), name="candidate_list"),
    path("candidates/<int:pk>/", views.CandidateDetailView.as_view(), name="candidate_detail"),
    # The two search forms
    path("search/skills/", views.skill_search, name="skill_search"),
    path("search/candidates/", views.CandidateSearchView.as_view(), name="candidate_search"),
    # Aggregations
    path("insights/", views.insights, name="insights"),
    # -- Matplotlib charts --------------------------------------------------
    # The page that displays them, then one PNG endpoint per chart. Each .png
    # URL returns image/png directly, so it works as an <img src> and can be
    # opened on its own.
    path("charts/", views.charts_page, name="charts"),
    path(
        "charts/skills-by-category.png",
        views.chart_skills_by_category,
        name="chart_skills_by_category",
    ),
    path(
        "charts/plan-progress.png",
        views.chart_plan_progress,
        name="chart_plan_progress",
    ),
    path("charts/skill-gap.png", views.chart_skill_gap, name="chart_skill_gap"),
    path("charts/task-status.png", views.chart_task_status, name="chart_task_status"),

    path("api/skills/", views.skill_api, name="skill_api"),
    # =====================================================================
    # Chart APIs, Vega-Lite, market data and reports
    # =====================================================================
    # Internal JSON API, chart-ready
    path("api/skills/summary/", views.api_skill_summary, name="api_skill_summary"),
    path("api/assessments/", views.api_assessments, name="api_assessments"),
    # Vega-Lite: the page, each spec, and each chart as a PNG
    path("vega-lite/", views.vega_lite_page, name="vega_lite"),
    path("vega-lite/chart<int:number>.json", views.vega_lite_spec, name="vega_lite_spec"),
    path("vega-lite/chart<int:number>.png", views.vega_lite_png, name="vega_lite_png"),
    # External API (Jobicy) joined with internal skill gaps
    path("api/market-demand/", views.api_market_demand, name="api_market_demand"),
    path("market/", views.market_page, name="market"),
    # Reports page, and the two downloads it links to. The URLs end
    # in .csv and .json so the path itself says what comes back, and so the
    # file keeps a sensible name if someone saves it with right-click.
    path("reports/", views.reports_page, name="reports"),
    path(
        "reports/candidates.csv",
        views.export_candidates_csv,
        name="export_candidates_csv",
    ),
    path(
        "reports/candidates.json",
        views.export_candidates_json,
        name="export_candidates_json",
    ),

    # =====================================================================
    # Authentication
    # =====================================================================
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/signup/", views.signup_view, name="signup"),
    path("accounts/logout/", views.logout_view, name="logout"),
    # A protected JSON endpoint. Unlike the browser-facing views above it
    # answers 401 with a JSON body rather than redirecting to the HTML login
    # page, because a JSON client cannot do anything useful with a redirect
    # to markup.
    path("api/whoami/", views.api_whoami, name="api_whoami"),
    path("api/local-model/", views.local_model_status, name="local_model_status"),
    # Command palette entries (Ctrl/Cmd+K). Protected: it lists candidates.
    path("api/palette/", views.api_palette, name="api_palette"),
    # Start-from-scratch journey: onboarding, your plan, doing tasks.
    path("welcome/", views.onboarding_view, name="onboarding"),
    path("welcome/resume/", views.resume_parse, name="resume_parse"),
    path("me/", views.my_plan, name="my_plan"),
    # AI coach: recommendations (GET) and a question box (POST). Protected JSON.
    path("me/coach/", views.coach_advice, name="coach_advice"),
    path("me/coach/ask/", views.coach_ask, name="coach_ask"),
    path("me/tasks/<int:pk>/", views.task_workspace, name="task_workspace"),
    path("me/tasks/<int:pk>/screen/", views.task_screen, name="task_screen"),
]
