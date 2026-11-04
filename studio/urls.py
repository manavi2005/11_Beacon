from django.urls import path

from . import views

app_name = "studio"

urlpatterns = [
    path("", views.home, name="home"),
    path("start/", views.start, name="start"),
    path("start/about/", views.start_about, name="start_about"),
    path("start/blueprint/", views.start_blueprint, name="start_blueprint"),
    path("today/", views.today, name="today"),
    path("today/mood/", views.set_mood, name="set_mood"),
    path("session/", views.session_page, name="session"),
    path("session/next/", views.session_next, name="session_next"),
    path("cards/<int:pk>/answer/", views.card_answer, name="card_answer"),
    path("interview/", views.interview_page, name="interview"),
    path("interview/start/", views.interview_start, name="interview_start"),
    path("interview/transcribe/", views.transcribe, name="transcribe"),
    path("interview/<int:pk>/", views.interview_report, name="interview_report"),
    path("interview/<int:pk>/reply/", views.interview_reply, name="interview_reply"),
    path("interview/<int:pk>/finish/", views.interview_finish, name="interview_finish"),
    path("coach/", views.coach_page, name="coach"),
    path("coach/send/", views.coach_send, name="coach_send"),
    path("coach/clear/", views.coach_clear, name="coach_clear"),
    path("progress/", views.progress, name="progress"),
    path("you/", views.you, name="you"),
    path("you/export/", views.export_data, name="export_data"),
    path("you/reset/", views.reset_progress, name="reset_progress"),
]
