"""Troubleshooting: what might be wrong for one person, and the fixes.

diagnose(user) runs every check and returns findings, each naming the fix
that resolves it. Every fix goes through run(), which checks it is allowed
and writes it to the audit trail, so the console can never change an
account without leaving a record.
"""

from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from beacon_core import security
from preparation import onboarding
from preparation.models import CandidateProfile
from studio import blueprint as blueprints
from studio import engine
from studio.models import Card, Preferences

from .models import ErrorEvent, StaffAction, SupportTicket

STUCK_AFTER = timedelta(hours=2)


class NotAllowed(Exception):
    pass


def profile_of(user):
    return CandidateProfile.objects.filter(user=user).first()


def ai_used(user):
    return security.count("ai-user", user.pk, 3600)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def diagnose(user):
    """[{level: ok|info|warn|error, title, detail, fix}] for one account."""
    from studio import views as studio_views
    now = timezone.now()
    found = []

    def add(level, title, detail="", fix=None):
        found.append({"level": level, "title": title, "detail": detail, "fix": fix})

    if not user.is_active:
        add("error", "Account is suspended", "They can't sign in until it is reactivated.",
            "reactivate")
    if security.login_locked(user.username, "-"):
        add("warn", "Sign-in is temporarily locked",
            "Too many wrong passwords in the last 15 minutes.", "unlock_login")
    used = ai_used(user)
    if used >= studio_views.AI_ACTIONS_PER_HOUR * 0.8:
        add("warn", "Near the hourly AI limit",
            f"{used} of {studio_views.AI_ACTIONS_PER_HOUR} AI actions this hour.", "reset_ai_budget")

    profile = profile_of(user)
    if not profile:
        add("info", "Hasn't finished setup", "No goal yet, so there is nothing to practise.")
        return found

    prefs = Preferences.objects.filter(candidate=profile).select_related("blueprint").first()
    bp = prefs.blueprint if prefs else None
    if not bp:
        add("warn", "No role blueprint linked", "Skills can't be tailored or refreshed.",
            "refresh_blueprint")
    elif bp.source != bp.Source.AI:
        add("warn", "Using the offline skill set",
            "The AI was unavailable when they set up, so their skills are generic.",
            "refresh_blueprint")

    assessed = set(profile.assessments.values_list("skill_id", flat=True))
    remembered = set(profile.memories.values_list("skill_id", flat=True))
    if assessed != remembered:
        add("error", "Skills out of sync",
            f"{len(assessed)} skills assessed but {len(remembered)} tracked for practice.",
            "resync_skills")

    if not profile.plans.filter(status="ACTIVE").exists():
        add("info", "No active weekly plan", "", "rebuild_plan")

    stuck = profile.interviews.filter(finished_at__isnull=True, started_at__lt=now - STUCK_AFTER)
    if stuck.exists():
        add("warn", f"{stuck.count()} mock interview(s) never finished",
            "Usually a closed tab or a dropped connection.", "close_stuck_interviews")

    week = profile.cards.filter(created_at__gte=now - timedelta(days=7))
    total = week.count()
    offline = week.exclude(source="ai").count()
    if total >= 4 and offline / total > 0.5:
        add("warn", "Mostly offline questions this week",
            f"{offline} of {total} questions came from the offline fallback; check AI status.")

    stale = profile.cards.filter(answered_at__isnull=True, created_at__lt=now - timedelta(days=1))
    if stale.count() > 10:
        add("info", f"{stale.count()} unanswered old questions", "Left over from closed sessions.",
            "discard_stale_cards")

    errors = ErrorEvent.objects.filter(user=user, created_at__gte=now - timedelta(days=7)).count()
    if errors:
        add("error", f"{errors} server error(s) in the last 7 days", "See the errors below.")

    tickets = SupportTicket.objects.filter(user=user, status=SupportTicket.Status.OPEN).count()
    if tickets:
        add("info", f"{tickets} open problem report(s)")

    if profile.target_interview_date and profile.target_interview_date < timezone.localdate():
        add("info", "Interview date has passed", "Worth checking in on how it went.")

    last = profile.days.exclude(cards_done=0, interviews_done=0).first()
    if last and (timezone.localdate() - last.date).days > 14:
        add("info", "Inactive for over two weeks", f"Last practised {last.date:%b %-d}.")

    if not any(f["level"] in ("warn", "error") for f in found):
        add("ok", "No problems found")
    return found


# --------------------------------------------------------------------------
# Fixes
# --------------------------------------------------------------------------
def _reactivate(actor, user, **_):
    user.is_active = True
    user.save(update_fields=["is_active"])
    return "Account reactivated."


def _suspend(actor, user, **_):
    if user == actor:
        raise NotAllowed("You can't suspend your own account.")
    if user.is_superuser and not actor.is_superuser:
        raise NotAllowed("Only a superuser can suspend a superuser.")
    user.is_active = False
    user.save(update_fields=["is_active"])
    return "Account suspended. They are signed out on their next request."


def _unlock_login(actor, user, **_):
    security.unlock_login(user.username)
    return "Sign-in unlocked."


def _reset_ai_budget(actor, user, **_):
    security.clear("ai-user", user.pk, 3600)
    return "Hourly AI allowance reset."


def _need_profile(user):
    profile = profile_of(user)
    if not profile:
        raise NotAllowed("They haven't set up a goal yet.")
    return profile


def _resync_skills(actor, user, **_):
    profile = _need_profile(user)
    assessed = set(profile.assessments.values_list("skill_id", flat=True))
    profile.memories.exclude(skill_id__in=assessed).delete()
    engine.sync_memories(profile)
    return "Practice skills re-synced with their assessments."


def _rebuild_plan(actor, user, **_):
    onboarding.build_plan(_need_profile(user))
    return "Built a fresh weekly plan."


def _refresh_blueprint(actor, user, **_):
    """Regenerate the role blueprint and re-apply it, keeping their levels."""
    from studio.views import _complete_setup
    profile = _need_profile(user)
    bp = blueprints.get_blueprint(profile.target_role, profile.experience_level)
    if bp.source != bp.Source.AI:
        raise NotAllowed("The AI is still unavailable, so the blueprint couldn't be refreshed. "
                         "Try again when AI status is on.")
    levels = {a.skill.name.lower(): a.proficiency_score
              for a in profile.assessments.select_related("skill")}
    ratings = {row["name"]: levels.get(row["name"].lower(), 40) for row in bp.skills}
    _complete_setup(user, bp, ratings, profile.target_interview_date, profile.experience_level,
                    profile.target_company, profile.resume_summary)
    return f"Refreshed their blueprint for {bp.title} and kept their levels."


def _close_stuck_interviews(actor, user, **_):
    profile = _need_profile(user)
    n = profile.interviews.filter(finished_at__isnull=True,
                                  started_at__lt=timezone.now() - STUCK_AFTER
                                  ).update(finished_at=timezone.now())
    return f"Closed {n} unfinished interview(s)."


def _discard_stale_cards(actor, user, **_):
    profile = _need_profile(user)
    n, _ = profile.cards.filter(answered_at__isnull=True,
                                created_at__lt=timezone.now() - timedelta(days=1)).delete()
    return f"Removed {n} unanswered question(s)."


def _make_due(actor, user, **_):
    profile = _need_profile(user)
    n = profile.memories.update(due_at=timezone.now())
    return f"All {n} skills are due for review now."


def _adjust_skill(actor, user, memory_id=None, strength=None, required=None, **_):
    profile = _need_profile(user)
    memory = profile.memories.select_related("skill").filter(pk=memory_id).first()
    if not memory:
        raise NotAllowed("That skill isn't on this account.")
    try:
        strength, required = float(strength), int(required)
    except (TypeError, ValueError):
        raise NotAllowed("Levels must be numbers.")
    if not (0 <= strength <= 100 and 1 <= required <= 100):
        raise NotAllowed("Level must be 0-100 and the bar 1-100.")
    memory.strength, memory.required = round(strength, 1), required
    memory.save(update_fields=["strength", "required"])
    profile.assessments.filter(skill=memory.skill).update(
        proficiency_score=round(strength), required_level=required)
    return f"{memory.skill.name}: level {memory.strength:g}, bar {required}."


def _grant_staff(actor, user, **_):
    if not actor.is_superuser:
        raise NotAllowed("Only a superuser can grant staff access.")
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return "Staff access granted."


def _revoke_staff(actor, user, **_):
    if not actor.is_superuser:
        raise NotAllowed("Only a superuser can revoke staff access.")
    if user == actor:
        raise NotAllowed("You can't remove your own staff access here.")
    user.is_staff = False
    user.save(update_fields=["is_staff"])
    return "Staff access removed."


ACTIONS = {
    "reactivate": ("Reactivate account", _reactivate),
    "suspend": ("Suspend account", _suspend),
    "unlock_login": ("Unlock sign-in", _unlock_login),
    "reset_ai_budget": ("Reset AI allowance", _reset_ai_budget),
    "resync_skills": ("Re-sync skills", _resync_skills),
    "rebuild_plan": ("Rebuild weekly plan", _rebuild_plan),
    "refresh_blueprint": ("Refresh role blueprint", _refresh_blueprint),
    "close_stuck_interviews": ("Close stuck interviews", _close_stuck_interviews),
    "discard_stale_cards": ("Discard stale questions", _discard_stale_cards),
    "make_due": ("Make every skill due now", _make_due),
    "adjust_skill": ("Adjust a skill", _adjust_skill),
    "grant_staff": ("Grant staff access", _grant_staff),
    "revoke_staff": ("Revoke staff access", _revoke_staff),
}


def label(name):
    return ACTIONS.get(name, (name, None))[0]


def run(actor, user, name, **params):
    """Apply one fix and record it. Raises NotAllowed with a reason."""
    if name not in ACTIONS:
        raise NotAllowed("Unknown action.")
    with transaction.atomic():
        message = ACTIONS[name][1](actor, user, **params)
        StaffAction.objects.create(
            actor=actor, target=user, action=name,
            detail={k: str(v)[:100] for k, v in params.items()} | {"result": message[:200]},
        )
    return message


def ai_status():
    from studio import ai
    from preparation import coach
    reason = cache.get(ai.DOWN_KEY)
    if reason:
        return {"state": "paused", "detail": str(reason)[:200]}
    if not coach.llm_enabled():
        return {"state": "off", "detail": "No AI provider configured."}
    if ai.slow():
        return {"state": "slow", "detail": f"{ai.label()}. Slow or rate-limited in the last "
                f"{ai.SLOW_SECONDS // 60} minutes, so practice uses instant offline questions: "
                f"{str(cache.get(ai.SLOW_KEY))[:120]}"}
    return {"state": "on", "detail": ai.label()}


def resume_ai(actor):
    """Clear the circuit breaker so the next request tries the provider."""
    from studio import ai
    cache.delete(ai.DOWN_KEY)
    cache.delete(ai.SLOW_KEY)
    StaffAction.objects.create(actor=actor, action="resume_ai", detail={})
