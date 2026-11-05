from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("ai/resume/", views.resume_ai, name="resume_ai"),
    path("users/", views.users, name="users"),
    path("users/<int:pk>/", views.user_detail, name="user"),
    path("users/<int:pk>/action/", views.user_action, name="user_action"),
    path("reports/", views.reports, name="reports"),
    path("reports/<int:pk>/resolve/", views.resolve_report, name="resolve_report"),
    path("errors/", views.errors, name="errors"),
    path("audit/", views.audit, name="audit"),
]
