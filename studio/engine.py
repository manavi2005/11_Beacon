"""The learning engine: what to practise today, how ready you are, how it is going.

Everything here is computed from the person's own evidence (SkillMemory,
Card, DayLog), never from a fixed list, so it works the same for a chemist,
a nurse or an engineer.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from preparation.models import SkillAssessment

from .models import Card, DayLog, SkillMemory, clamp, level_name, xp_level

SESSION_SIZE = {"GREAT": 5, "OK": 4, "ROUGH": 2, "": 4}


@transaction.atomic
def sync_memories(profile):
    """One SkillMemory per assessed skill, seeded from the self-rating.
    New skills start due now, so the first session doubles as a diagnostic."""
    existing = {m.skill_id: m for m in profile.memories.all()}
    for a in profile.assessments.select_related("skill"):
        memory = existing.get(a.skill_id)
        if memory is None:
            SkillMemory.objects.create(
                candidate=profile, skill=a.skill, strength=a.proficiency_score,
                required=a.required_level or 65, due_at=timezone.now(),
            )
        elif memory.required != a.required_level and a.required_level:
            memory.required = a.required_level
            memory.save(update_fields=["required"])
    return list(profile.memories.select_related("skill"))


def readiness(memories, now=None):
    if not memories:
        return 0
    return round(sum(m.readiness(now) for m in memories) / len(memories) * 100)


def skill_rows(memories, now=None):
    now = now or timezone.now()
    rows = []
    for m in memories:
        effective = m.effective(now)
        rows.append({
            "memory": m,
            "skill": m.skill,
            "strength": round(m.strength),
            "effective": round(effective),
            "required": m.required,
            "faded": round(m.strength - effective),
            "retention": round(m.retention(now) * 100),
            "level": level_name(effective),
            "due": m.is_due(now),
            "gap": max(m.required - round(effective), 0),
            "percent": round(min(effective / m.required, 1) * 100) if m.required else 100,
        })
    rows.sort(key=lambda r: (-r["gap"], r["skill"].name))
    return rows


def queue(memories, mood="", now=None):
    """Today's skills, in order: what is fading first, then the widest gaps.

    A rough day gets a short, review-only session: keeping what you have is
    a win too, and nobody should be pushed into new material when they are
    struggling.
    """
    now = now or timezone.now()
    size = SESSION_SIZE.get(mood, 4)
    due = sorted((m for m in memories if m.is_due(now)), key=lambda m: m.retention(now))
    picked = due[:size]
    if mood != "ROUGH":
        rest = sorted((m for m in memories if m not in picked),
                      key=lambda m: m.effective(now) - m.required)
        picked += rest[: size - len(picked)]
    return picked


def today_log(profile):
    log, _ = DayLog.objects.get_or_create(candidate=profile, date=timezone.localdate())
    return log


def streak(profile, today=None):
    """Consecutive active days, forgiving by design: one rest day in any
    seven doesn't break a streak, and today not being done yet never does."""
    today = today or timezone.localdate()
    active = set(
        profile.days.filter(date__gte=today - timedelta(days=180))
        .exclude(cards_done=0, interviews_done=0).values_list("date", flat=True)
    )
    day = today if today in active else today - timedelta(days=1)
    count, last_rest = 0, None
    while True:
        if day in active:
            count += 1
        elif (day - timedelta(days=1)) in active and (
            last_rest is None or (last_rest - day).days >= 7
        ):
            last_rest = day
        else:
            break
        day -= timedelta(days=1)
    week = [
        {"date": today - timedelta(days=i), "active": (today - timedelta(days=i)) in active}
        for i in range(6, -1, -1)
    ]
    return {"days": count, "week": week, "done_today": today in active}


def total_xp(profile):
    return profile.days.aggregate(total=Sum("xp"))["total"] or 0


def level_info(profile):
    xp = total_xp(profile)
    level, into, need = xp_level(xp)
    return {"xp": xp, "level": level, "into": into, "need": need,
            "percent": round(into / need * 100) if need else 0}


def snapshot(profile, memories):
    """Record today's readiness and return the recent history for the chart."""
    log = today_log(profile)
    value = readiness(memories)
    if log.readiness != value:
        log.readiness = value
        log.save(update_fields=["readiness"])
    rows = profile.days.filter(readiness__isnull=False).order_by("-date")[:30]
    return [{"date": r.date, "value": r.readiness} for r in reversed(rows)]


def forecast(profile, current):
    """Where readiness lands by the interview date at the pace of the last two weeks."""
    date = profile.target_interview_date
    if not date:
        return None
    gained = list(
        profile.cards.filter(answered_at__gte=timezone.now() - timedelta(days=14))
        .values_list("score", flat=True)
    )
    days_left = (date - timezone.localdate()).days
    if days_left < 0:
        return None
    # Each answered card at or above the bar is worth roughly half a point of
    # readiness; poor answers still teach, at a fifth of that. Spread over
    # the days practised, this gives a daily pace to extend forward.
    if gained:
        pace = sum(0.5 if s >= 60 else 0.1 for s in gained) / 14
    else:
        pace = 0.4
    projected = clamp(round(current + pace * days_left))
    return {"date": date, "days_left": days_left, "value": projected,
            "on_track": projected >= 80}


def record_card(card, score, feedback, response):
    """Store a graded answer, update the skill's memory and today's log."""
    now = timezone.now()
    with transaction.atomic():
        memory = SkillMemory.objects.select_for_update().get(
            candidate=card.candidate, skill=card.skill
        )
        before = memory.effective(now)
        memory.record(score, now, weight=0.6 if card.kind == Card.Kind.CHOICE else 1.0)
        memory.save()
        xp = 10 + score // 10 + (5 if card.is_review and score >= 60 else 0)
        card.score, card.feedback, card.response = score, feedback, response
        card.answered_at, card.xp = now, xp
        card.save()
        log = today_log(card.candidate)
        log.cards_done += 1
        log.xp += xp
        log.save()
        # Keep v1's assessment row in step, so the plan, dashboard and coach
        # all see the same level the practice has shown.
        SkillAssessment.objects.filter(candidate=card.candidate, skill=card.skill).update(
            proficiency_score=clamp(round(memory.strength)), assessed_on=timezone.localdate()
        )
    return {"xp": xp, "before": round(before), "after": round(memory.effective(now)),
            "next_review_days": round(memory.stability, 1), "level": level_name(memory.effective(now))}


def recent_prompts(profile, skill, limit=12):
    return list(
        Card.objects.filter(candidate=profile, skill=skill)
        .order_by("-created_at").values_list("prompt", flat=True)[:limit]
    )
