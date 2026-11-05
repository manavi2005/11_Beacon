"""The staff support console: see how Beacon is doing, find a person, see
what they see, find out what's wrong and fix it.

    /staff/                      overview: health, usage, open reports, errors
    /staff/users/                search everyone
    /staff/users/<id>/           one person: goal, skills, practice, interviews,
                                 diagnostics with one-click fixes
    /staff/reports/              problem reports from the "Report a problem" form
    /staff/errors/               server errors, newest first
    /staff/audit/                every change staff have made

Staff only. Anyone else gets a plain 404, so the console doesn't even
confirm it exists. Every change goes through support.actions.run(), which
writes the audit trail.
"""

from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from beacon_core import security
from studio import engine
from studio.models import Card, DayLog, InterviewSession, Preferences, RoleBlueprint

from . import actions
from .models import ErrorEvent, StaffAction, SupportTicket

User = get_user_model()


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = request.user
        if not (user.is_authenticated and user.is_active and user.is_staff):
            raise Http404
        return view(request, *args, **kwargs)
    return wrapped


@staff_required
def overview(request):
    now = timezone.now()
    today = timezone.localdate()
    day, week = now - timedelta(days=1), now - timedelta(days=7)
    from studio import views as studio_views
    cards_day = Card.objects.filter(created_at__gte=day)
    cards_total = cards_day.count()
    stats = {
        "users": User.objects.count(),
        "new_day": User.objects.filter(date_joined__gte=day).count(),
        "new_week": User.objects.filter(date_joined__gte=week).count(),
        "active_today": DayLog.objects.filter(date=today).exclude(cards_done=0, interviews_done=0).count(),
        "active_week": DayLog.objects.filter(date__gte=today - timedelta(days=6))
        .exclude(cards_done=0, interviews_done=0).values("candidate").distinct().count(),
        "answers_day": Card.objects.filter(answered_at__gte=day).count(),
        "interviews_day": InterviewSession.objects.filter(started_at__gte=day).count(),
        "offline_share": round(cards_day.exclude(source="ai").count() / cards_total * 100) if cards_total else 0,
        "suspended": User.objects.filter(is_active=False).count(),
        "roles": RoleBlueprint.objects.count(),
    }
    return render(request, "support/overview.html", {
        "stats": stats,
        "ai": actions.ai_status(),
        "ai_site": security.count("ai-site", "all", 3600),
        "ai_site_cap": studio_views.AI_ACTIONS_SITE_PER_HOUR,
        "tickets": SupportTicket.objects.filter(status=SupportTicket.Status.OPEN).select_related("user")[:8],
        "open_tickets": SupportTicket.objects.filter(status=SupportTicket.Status.OPEN).count(),
        "errors": ErrorEvent.objects.select_related("user")[:8],
        "errors_day": ErrorEvent.objects.filter(created_at__gte=day).count(),
        "top_errors": ErrorEvent.objects.filter(created_at__gte=week).values("kind", "path")
        .annotate(n=Count("id")).order_by("-n")[:5],
        "audit": StaffAction.objects.select_related("actor", "target")[:8],
        "recent_users": User.objects.order_by("-date_joined")[:8],
    })


@staff_required
@require_POST
def resume_ai(request):
    actions.resume_ai(request.user)
    messages.success(request, "AI resumed. The next request will try the provider again.")
    return redirect("support:overview")


@staff_required
def users(request):
    q = " ".join(request.GET.get("q", "").split())[:100]
    status = request.GET.get("status", "")
    people = (User.objects.select_related("candidate_profile")
              .annotate(tickets=Count("support_tickets", filter=Q(support_tickets__status="OPEN")))
              .order_by("-date_joined"))
    if q:
        people = people.filter(Q(username__icontains=q) | Q(email__icontains=q)
                               | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                               | Q(candidate_profile__target_role__icontains=q))
    if status == "suspended":
        people = people.filter(is_active=False)
    elif status == "staff":
        people = people.filter(is_staff=True)
    elif status == "no-setup":
        people = people.filter(candidate_profile__isnull=True)
    elif status == "reports":
        people = people.filter(tickets__gt=0)
    page = Paginator(people, 40).get_page(request.GET.get("page"))
    return render(request, "support/users.html", {"page": page, "q": q, "status": status})


@staff_required
def user_detail(request, pk):
    person = get_object_or_404(User, pk=pk)
    profile = actions.profile_of(person)
    context = {"person": person, "profile": profile,
               "findings": actions.diagnose(person),
               "labels": {k: v[0] for k, v in actions.ACTIONS.items()},
               "ai_used": actions.ai_used(person),
               "tickets": SupportTicket.objects.filter(user=person)[:10],
               "errors": ErrorEvent.objects.filter(user=person)[:10],
               "audit": StaffAction.objects.filter(target=person).select_related("actor")[:15],
               "social": list(person.socialaccount_set.values_list("provider", flat=True))
               if hasattr(person, "socialaccount_set") else []}
    if profile:
        memories = engine.sync_memories(profile)
        prefs = Preferences.objects.filter(candidate=profile).select_related("blueprint").first()
        context.update({
            "rows": engine.skill_rows(memories),
            "ranked": engine.rank(memories, stage=profile.experience_level,
                                  trending=(prefs.blueprint.market or {}).get("trending")
                                  if prefs and prefs.blueprint else None),
            "readiness": engine.readiness(memories),
            "streak": engine.streak(profile),
            "level": engine.level_info(profile),
            "blueprint": prefs.blueprint if prefs else None,
            "prefs": prefs,
            "cards": profile.cards.select_related("skill").order_by("-created_at")[:25],
            "interviews": profile.interviews.all()[:10],
            "days": profile.days.all()[:14],
            "plans": profile.plans.annotate(n=Count("tasks"))[:5],
        })
    return render(request, "support/user_detail.html", context)


ACTION_FIELDS = ("memory_id", "strength", "required")


@staff_required
@require_POST
def user_action(request, pk):
    person = get_object_or_404(User, pk=pk)
    name = request.POST.get("action", "")
    params = {k: request.POST[k] for k in ACTION_FIELDS if k in request.POST}
    try:
        message = actions.run(request.user, person, name, **params)
    except actions.NotAllowed as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, message)
    return redirect("support:user", pk=person.pk)


@staff_required
def reports(request):
    status = request.GET.get("status", "OPEN")
    tickets = SupportTicket.objects.select_related("user", "resolved_by")
    if status in SupportTicket.Status.values:
        tickets = tickets.filter(status=status)
    page = Paginator(tickets, 30).get_page(request.GET.get("page"))
    return render(request, "support/reports.html", {"page": page, "status": status})


@staff_required
@require_POST
def resolve_report(request, pk):
    ticket = get_object_or_404(SupportTicket, pk=pk)
    reopen = request.POST.get("reopen") == "1"
    ticket.status = SupportTicket.Status.OPEN if reopen else SupportTicket.Status.RESOLVED
    ticket.staff_note = request.POST.get("note", ticket.staff_note)[:2000]
    ticket.resolved_at = None if reopen else timezone.now()
    ticket.resolved_by = None if reopen else request.user
    ticket.save()
    StaffAction.objects.create(actor=request.user, target=ticket.user,
                               action="reopen_report" if reopen else "resolve_report",
                               detail={"ticket": ticket.pk})
    messages.success(request, "Report reopened." if reopen else "Report resolved.")
    if request.POST.get("back") == "user":
        return redirect("support:user", pk=ticket.user_id)
    return redirect("support:reports")


@staff_required
def errors(request):
    page = Paginator(ErrorEvent.objects.select_related("user"), 50).get_page(request.GET.get("page"))
    return render(request, "support/errors.html", {"page": page})


@staff_required
def audit(request):
    page = Paginator(StaffAction.objects.select_related("actor", "target"), 50).get_page(
        request.GET.get("page"))
    return render(request, "support/audit.html", {"page": page, "labels":
                  {k: v[0] for k, v in actions.ACTIONS.items()}})


# --------------------------------------------------------------------------
# For everyone: "Something not right?" on the You page
# --------------------------------------------------------------------------
REPORTS_PER_DAY = 10


@login_required
@require_POST
def report_problem(request):
    message = request.POST.get("message", "").strip()[:3000]
    category = request.POST.get("category", "")
    if category not in SupportTicket.Category.values:
        category = SupportTicket.Category.OTHER
    if not message:
        messages.error(request, "Tell us a little about what happened first.")
    elif not security.allow("report", request.user.pk, REPORTS_PER_DAY, 86400):
        messages.error(request, "You've sent a lot of reports today. We'll get to them soon.")
    else:
        SupportTicket.objects.create(
            user=request.user, category=category, message=message,
            page=request.POST.get("page", "")[:200],
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        messages.success(request, "Thanks. Your report is in, and the reply will show up here.")
    return redirect("/you/#help")
