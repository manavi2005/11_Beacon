"""Pages and JSON endpoints for the v2 experience.

    /                 landing (signed out) or Today (signed in)
    /start/           set up for any role, in any field
    /today/           the daily home: readiness, today's session, streak
    /session/         focus mode: one card at a time, instant feedback
    /interview/       voice or typed mock interview, then a STAR report
    /progress/        every skill, what's fading, readiness over time
    /you/             privacy: what Beacon stores, export, delete
"""

import json
from datetime import date as date_cls
from functools import wraps

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from preparation import onboarding as v1_onboarding
from preparation.models import CandidateProfile, PreparationPlan, SkillAssessment

from . import about, ai, blueprint, cards, chat, engine, interview
from .templatetags.studio_text import coach_html
from .models import Card, DayLog, InterviewSession, Preferences, RoleBlueprint, SkillMemory

SESSION_KEY = "studio_session"


AI_ACTIONS_PER_HOUR = 150


def ai_budget(view):
    """Cap AI-backed actions per person per hour, so one runaway script or
    tab can't run up the provider bill. Generous for real use."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        key = f"studio:ai-budget:{request.user.pk}:{timezone.now():%Y%m%d%H}"
        used = cache.get_or_set(key, 0, 3600)
        if used >= AI_ACTIONS_PER_HOUR:
            return JsonResponse(
                {"error": "You've done a lot this hour. Take a breather and come back in a few minutes."},
                status=429)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 3600)
        return view(request, *args, **kwargs)
    return wrapped


def _profile(request):
    return CandidateProfile.objects.filter(user=request.user).first()


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def _greeting():
    hour = timezone.localtime().hour
    return "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"


def home(request):
    if not request.user.is_authenticated:
        # Real roles people have set up, so the page reflects who uses Beacon.
        # Only roles real people have set up, and only once there are enough
        # to show the range; nothing is invented for the page.
        roles = list(RoleBlueprint.objects.filter(source=RoleBlueprint.Source.AI)
                     .order_by("-created_at").values_list("title", flat=True)[:16])
        return render(request, "studio/landing.html", {"roles": roles if len(roles) >= 6 else []})
    if not _profile(request):
        if request.user.is_staff:
            return redirect("preparation:dashboard")
        return redirect("studio:start")
    return redirect("studio:today")


# --------------------------------------------------------------------------
# Setup for any role
# --------------------------------------------------------------------------
@login_required
def start(request):
    profile = _profile(request)
    if request.method == "POST":
        data = _body(request)
        role = " ".join(str(data.get("role", "")).split())[:140]
        if not role:
            return JsonResponse({"error": "Tell Beacon what you're working toward."}, status=400)
        bp = (RoleBlueprint.objects.filter(slug=str(data.get("blueprint", ""))).first()
              or blueprint.get_blueprint(role, data.get("experience_level", "")))
        ratings = data.get("ratings") or {}
        interview_date = None
        if data.get("date"):
            try:
                interview_date = date_cls.fromisoformat(data["date"])
            except ValueError:
                interview_date = None
        experience = data.get("experience_level") or CandidateProfile.ExperienceLevel.STUDENT
        if experience not in CandidateProfile.ExperienceLevel.values:
            experience = CandidateProfile.ExperienceLevel.STUDENT
        _complete_setup(request.user, bp, ratings, interview_date, experience,
                        str(data.get("company", ""))[:120], str(data.get("background", ""))[:1500])
        return JsonResponse({"next": "/today/?welcome=1"})
    return render(request, "studio/start.html", {
        "profile": profile,
        "experience_levels": CandidateProfile.ExperienceLevel.choices,
        "ai_on": ai.enabled(),
    })


@transaction.atomic
def _complete_setup(user, bp, ratings, interview_date, experience, company, background):
    today = timezone.localdate()
    weeks = 6
    if interview_date:
        weeks = max(1, min(52, -(-max((interview_date - today).days, 7) // 7)))
    profile, _ = CandidateProfile.objects.update_or_create(
        user=user,
        defaults={
            "target_role": bp.title[:120], "target_roles": [bp.title],
            "target_company": company, "experience_level": experience,
            "target_interview_date": interview_date, "preparation_timeline_weeks": weeks,
            "resume_summary": background,
        },
    )
    keep = []
    for skill, row in blueprint.ensure_skills(bp):
        try:
            rating = max(0, min(100, int(ratings.get(row["name"], 40))))
        except (TypeError, ValueError):
            rating = 40
        SkillAssessment.objects.update_or_create(
            candidate=profile, skill=skill,
            defaults={"proficiency_score": rating, "required_level": row["required"],
                      "assessed_on": today, "notes": "Self-rating at setup."},
        )
        keep.append(skill.pk)
    # A new goal replaces the old bar: skills not in this blueprint leave the
    # readiness score (their practice history stays in Cards).
    profile.assessments.exclude(skill_id__in=keep).delete()
    profile.memories.exclude(skill_id__in=keep).delete()
    profile.skills.set(keep)
    engine.sync_memories(profile)
    Preferences.objects.update_or_create(candidate=profile, defaults={"blueprint": bp})
    v1_onboarding.build_plan(profile)
    return profile


@login_required
@require_POST
@ai_budget
def start_about(request):
    """Read a resume (PDF or text, never stored) and/or a self-description."""
    from preparation import resume as resume_reader
    text = request.POST.get("text", "")
    if request.FILES.get("resume"):
        try:
            text = resume_reader.extract_text(upload=request.FILES["resume"]) + "\n" + text
        except resume_reader.ResumeError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
    if not text.strip():
        return JsonResponse({"error": "Upload a resume or write a few sentences about you."}, status=400)
    return JsonResponse(about.read_background(text))


@login_required
@require_POST
@ai_budget
def start_blueprint(request):
    data = _body(request)
    role = " ".join(str(data.get("role", "")).split())[:140]
    if not role:
        return JsonResponse({"error": "Type a role first."}, status=400)
    bp = blueprint.get_blueprint(role, str(data.get("experience_level", "")))
    return JsonResponse({"slug": bp.slug, "title": bp.title, "summary": bp.summary, "skills": bp.skills,
                         "source": bp.source, "interview_style": bp.interview_style,
                         "market": bp.market,
                         "levels": about.estimate_levels(str(data.get("background", ""))[:1500], bp)})


# --------------------------------------------------------------------------
# Today
# --------------------------------------------------------------------------
@login_required
def today(request):
    profile = _profile(request)
    if not profile:
        return redirect("studio:start")
    memories = engine.sync_memories(profile)
    log = engine.today_log(profile)
    rows = engine.skill_rows(memories)
    current = engine.readiness(memories)
    history = engine.snapshot(profile, memories)
    plan = engine.queue(memories, log.mood)
    due_count = sum(1 for r in rows if r["due"] and r["memory"].reps)
    first_time = not profile.cards.filter(answered_at__isnull=False).exists()
    last_interview = profile.interviews.filter(finished_at__isnull=False).first()
    return render(request, "studio/today.html", {
        "profile": profile,
        "greeting": _greeting(),
        "first_name": request.user.first_name or request.user.username,
        "log": log,
        "readiness": current,
        "history": history,
        "history_json": json.dumps([{"d": h["date"].isoformat(), "v": h["value"]} for h in history]),
        "forecast": engine.forecast(profile, current),
        "streak": engine.streak(profile),
        "level": engine.level_info(profile),
        "rows": rows,
        "focus": rows[:3],
        "plan": plan,
        "due_count": due_count,
        "minutes": len(plan) * 3,
        "welcome": request.GET.get("welcome") == "1",
        "first_time": first_time,
        "last_interview": last_interview,
        "ai_on": ai.enabled(),
    })


@login_required
@require_POST
def set_mood(request):
    profile = _profile(request)
    if not profile:
        raise Http404
    mood = _body(request).get("mood", "")
    if mood not in DayLog.Mood.values:
        return JsonResponse({"error": "Unknown mood."}, status=400)
    log = engine.today_log(profile)
    log.mood = mood
    log.save(update_fields=["mood"])
    return JsonResponse({"ok": True, "size": engine.SESSION_SIZE[mood]})


# --------------------------------------------------------------------------
# Focus session
# --------------------------------------------------------------------------
@login_required
def session_page(request):
    profile = _profile(request)
    if not profile:
        return redirect("studio:start")
    memories = engine.sync_memories(profile)
    log = engine.today_log(profile)
    skill_id = request.GET.get("skill")
    if skill_id:
        picked = [m for m in memories if str(m.skill_id) == skill_id][:1]
        plan = picked * 3 if picked else engine.queue(memories, log.mood)
    else:
        plan = engine.queue(memories, log.mood)
    request.session[SESSION_KEY] = {
        "memory_ids": [m.pk for m in plan], "index": 0, "card_ids": [],
        "readiness_before": engine.readiness(memories),
    }
    return render(request, "studio/session.html", {
        "profile": profile, "size": len(plan), "mood": log.mood,
        "skill_names": [m.skill.name for m in plan],
    })


def _card_json(card):
    data = {"id": card.pk, "kind": card.kind, "kind_label": card.get_kind_display(),
            "prompt": card.prompt, "skill": card.skill.name, "is_review": card.is_review,
            "difficulty": card.difficulty}
    if card.kind == Card.Kind.CHOICE:
        data["options"] = card.payload.get("options", [])
    else:
        data["key_points_count"] = len(card.payload.get("key_points", []))
    return data


@login_required
@require_POST
@ai_budget
def session_next(request):
    profile = _profile(request)
    state = request.session.get(SESSION_KEY)
    if not profile or not state:
        return JsonResponse({"error": "Start a session from Today."}, status=400)
    if state["index"] >= len(state["memory_ids"]):
        return JsonResponse({"done": True, "summary": _summary(profile, state)})
    memory = get_object_or_404(SkillMemory, pk=state["memory_ids"][state["index"]], candidate=profile)
    card = cards.new_card(profile, memory, is_review=memory.reps > 0 and memory.is_due())
    state["index"] += 1
    state["card_ids"].append(card.pk)
    request.session[SESSION_KEY] = state
    return JsonResponse({"card": _card_json(card), "position": state["index"],
                         "total": len(state["memory_ids"])})


@login_required
@require_POST
@ai_budget
def card_answer(request, pk):
    profile = _profile(request)
    card = get_object_or_404(Card, pk=pk, candidate=profile)
    if card.answered:
        return JsonResponse({"error": "Already answered."}, status=400)
    data = _body(request)
    if card.kind == Card.Kind.CHOICE:
        score, feedback = cards.grade_choice(card, data.get("pick"))
        response = {"pick": data.get("pick")}
    else:
        score, feedback = cards.grade(card, data.get("answer", ""))
        response = {"answer": str(data.get("answer", ""))[:4000]}
    result = engine.record_card(card, score, feedback, response)
    return JsonResponse({"score": score, "feedback": feedback, **result})


def _summary(profile, state):
    done = list(Card.objects.filter(pk__in=state["card_ids"], answered_at__isnull=False)
                .select_related("skill"))
    memories = list(profile.memories.select_related("skill"))
    after = engine.readiness(memories)
    engine.snapshot(profile, memories)
    streak = engine.streak(profile)
    return {
        "cards": len(done),
        "xp": sum(c.xp for c in done),
        "average": round(sum(c.score for c in done) / len(done)) if done else 0,
        "readiness_before": state.get("readiness_before", after),
        "readiness_after": after,
        "streak": streak["days"],
        "skills": [{"name": c.skill.name, "score": c.score} for c in done],
    }


# --------------------------------------------------------------------------
# Mock interviews
# --------------------------------------------------------------------------
@login_required
def interview_page(request):
    profile = _profile(request)
    if not profile:
        return redirect("studio:start")
    return render(request, "studio/interview.html", {
        "profile": profile,
        "past": profile.interviews.filter(finished_at__isnull=False)[:6],
        "modes": InterviewSession.Mode.choices,
        "ai_on": ai.enabled(),
    })


@login_required
@require_POST
@ai_budget
def interview_start(request):
    profile = _profile(request)
    if not profile:
        raise Http404
    data = _body(request)
    mode = data.get("mode") if data.get("mode") in InterviewSession.Mode.values else InterviewSession.Mode.MIXED
    try:
        questions = int(data.get("questions", 4))
    except (TypeError, ValueError):
        questions = 4
    session = interview.start(profile, mode, questions)
    return JsonResponse({"id": session.pk, "say": session.transcript[0]["text"],
                         "question": 1, "total": session.planned_questions})


@login_required
@require_POST
@ai_budget
def interview_reply(request, pk):
    session = get_object_or_404(InterviewSession, pk=pk, candidate__user=request.user,
                                finished_at__isnull=True)
    line = interview.reply(session, _body(request).get("answer", ""))
    if line is None:
        return JsonResponse({"done": True})
    return JsonResponse({"say": line, "question": session.questions_asked,
                         "total": session.planned_questions})


@login_required
@require_POST
@ai_budget
def interview_finish(request, pk):
    session = get_object_or_404(InterviewSession, pk=pk, candidate__user=request.user)
    already = session.finished_at is not None
    report = interview.finish(session)
    if not already:
        log = engine.today_log(session.candidate)
        log.interviews_done += 1
        log.xp += 40 + report["overall"] // 5
        log.save(update_fields=["interviews_done", "xp"])
    return JsonResponse({"url": f"/interview/{session.pk}/"})


@login_required
def interview_report(request, pk):
    session = get_object_or_404(InterviewSession, pk=pk, candidate__user=request.user)
    if not session.report:
        return redirect("studio:interview")
    return render(request, "studio/interview_report.html", {
        "session": session, "report": session.report, "profile": session.candidate,
        "star_parts": [(k.title(), session.report.get("star", {}).get(k, 0))
                       for k in ("situation", "task", "action", "result")],
    })


@login_required
@require_POST
def transcribe(request):
    """Speech-to-text for browsers without built-in recognition (Firefox).
    Forwards the recording to the configured provider's Whisper-style
    endpoint (Lumen serves granite-speech for free). Never stored."""
    audio = request.FILES.get("audio")
    cfg_key = getattr(settings, "LLM_API_KEY", "")
    if not audio or not cfg_key or not ai.enabled():
        return JsonResponse({"error": "Voice typing isn't available here. Type your answer instead."}, status=503)
    if audio.size > 15 * 1024 * 1024:
        return JsonResponse({"error": "That recording is too long."}, status=400)
    try:
        response = requests.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {cfg_key}"},
            data={"model": settings.LLM_SPEECH_MODEL},
            files={"file": (audio.name or "answer.webm", audio.read(), audio.content_type)},
            timeout=60,
        )
        response.raise_for_status()
        text = response.json().get("text", "")
    except (requests.RequestException, ValueError):
        return JsonResponse({"error": "Couldn't transcribe that. Try again or type it."}, status=502)
    return JsonResponse({"text": text.strip()})


# --------------------------------------------------------------------------
# Coach chat (history in the session only)
# --------------------------------------------------------------------------
CHAT_KEY = "studio_chat"
STARTERS = [
    "What should I focus on this week?",
    "I'm nervous about my interview.",
    "How do I explain a gap or a failure?",
    "Help me answer 'Tell me about yourself'.",
]


@login_required
def coach_page(request):
    profile = _profile(request)
    if not profile:
        return redirect("studio:start")
    return render(request, "studio/coach.html", {
        "profile": profile, "history": request.session.get(CHAT_KEY, []), "starters": STARTERS,
    })


@login_required
@require_POST
@ai_budget
def coach_send(request):
    profile = _profile(request)
    if not profile:
        raise Http404
    message = " ".join(str(_body(request).get("message", "")).split())[:2000]
    if not message:
        return JsonResponse({"error": "Type a message first."}, status=400)
    history = request.session.get(CHAT_KEY, [])
    answer = chat.reply(profile, history, message)
    history = (history + [{"role": "user", "content": message},
                          {"role": "assistant", "content": answer}])[-chat.MAX_TURNS * 2:]
    request.session[CHAT_KEY] = history
    return JsonResponse({"reply": answer, "html": coach_html(answer)})


@login_required
@require_POST
def coach_clear(request):
    request.session.pop(CHAT_KEY, None)
    return redirect("studio:coach")


# --------------------------------------------------------------------------
# Progress and privacy
# --------------------------------------------------------------------------
@login_required
def progress(request):
    profile = _profile(request)
    if not profile:
        return redirect("studio:start")
    memories = engine.sync_memories(profile)
    history = engine.snapshot(profile, memories)
    return render(request, "studio/progress.html", {
        "profile": profile,
        "rows": engine.skill_rows(memories),
        "readiness": engine.readiness(memories),
        "history": history,
        "history_json": json.dumps([{"d": h["date"].isoformat(), "v": h["value"]} for h in history]),
        "level": engine.level_info(profile),
        "streak": engine.streak(profile),
        "recent": profile.cards.filter(answered_at__isnull=False).select_related("skill").order_by("-answered_at")[:12],
        "interviews": profile.interviews.filter(finished_at__isnull=False)[:8],
        "total_cards": profile.cards.filter(answered_at__isnull=False).count(),
    })


@login_required
def you(request):
    profile = _profile(request)
    prefs = Preferences.objects.get_or_create(candidate=profile)[0] if profile else None
    if request.method == "POST" and prefs:
        prefs.email_reminders = request.POST.get("email_reminders") == "on"
        prefs.save(update_fields=["email_reminders"])
        return redirect("studio:you")
    return render(request, "studio/you.html", {
        "prefs": prefs,
        "profile": profile,
        "counts": {
            "cards": profile.cards.count() if profile else 0,
            "interviews": profile.interviews.count() if profile else 0,
            "days": profile.days.count() if profile else 0,
        },
        "provider": ai.label() if ai.enabled() else "Off (offline coaching)",
    })


@login_required
def export_data(request):
    profile = _profile(request)
    data = {"user": request.user.get_username(), "exported_at": timezone.now().isoformat()}
    if profile:
        data.update({
            "goal": {"role": profile.target_role, "company": profile.target_company,
                     "interview_date": str(profile.target_interview_date or "")},
            "skills": [{"skill": m.skill.name, "strength": m.strength, "required": m.required,
                        "reviews": m.reps} for m in profile.memories.select_related("skill")],
            "cards": [{"skill": c.skill.name, "prompt": c.prompt, "response": c.response,
                       "score": c.score, "feedback": c.feedback,
                       "answered_at": c.answered_at.isoformat() if c.answered_at else None}
                      for c in profile.cards.select_related("skill")],
            "interviews": [{"role": i.role, "transcript": i.transcript, "report": i.report,
                            "started_at": i.started_at.isoformat()} for i in profile.interviews.all()],
            "days": [{"date": str(d.date), "mood": d.mood, "cards": d.cards_done, "xp": d.xp}
                     for d in profile.days.all()],
        })
    response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="my-beacon-data.json"'
    return response


@login_required
@require_POST
def reset_progress(request):
    """Delete everything Beacon knows about this person's preparation.
    The login stays, so they can start fresh."""
    profile = _profile(request)
    if profile and request.POST.get("confirm") == "DELETE":
        PreparationPlan.objects.filter(candidate=profile).delete()
        profile.delete()
        request.session.pop(SESSION_KEY, None)
        return redirect("studio:start")
    return redirect("studio:you")



def healthz(request):
    """Deploy check: is the database reachable, and is AI on? No secrets."""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:  # noqa: BLE001 - any failure means "not healthy"
        db_ok = False
    paused = bool(cache.get(ai.DOWN_KEY))
    return JsonResponse(
        {"ok": db_ok, "database": db_ok,
         "ai": "paused" if paused else ("on" if ai.enabled() else "off")},
        status=200 if db_ok else 503,
    )
