"""The learning engine: what to practise today, how ready you are, how it is going.

Everything here is computed from the person's own evidence (SkillMemory,
Card, DayLog), never from a fixed list, so it works the same for a chemist,
a nurse or an engineer.
"""

import math
import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from preparation.models import SkillAssessment

from .models import Card, DayLog, Preferences, SkillMemory, clamp, level_name, xp_level

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
            "level": level_name(effective, m.required),
            "due": m.is_due(now),
            "gap": max(m.required - round(effective), 0),
            "percent": round(min(effective / m.required, 1) * 100) if m.required else 100,
        })
    rows.sort(key=lambda r: (-r["gap"], r["skill"].name))
    return rows


# --------------------------------------------------------------------------
# Ranking: what to practise next
# --------------------------------------------------------------------------
# Choosing today's skills is a ranking problem. Every skill gets a score from
# one scoring function, and the session is the top of that list. Each term is
# 0..1 and the weights say how much each one matters, so the ranking can be
# tuned in one place and explained term by term ("why this today").
#
#   urgency      1 - retention: about to be forgotten
#   gap          how far below your own, stage-relative bar
#   demand       current job postings for the role ask for it
#   cohort       how hard people at your stage find it (collaborative signal)
#   explore      little evidence yet, so a rep here teaches Beacon the most
#   recent       practised in the last few hours (a penalty)
#
# Only `cohort` depends on other people's data, and that is the sparse part
# of the user x item matrix: most skills have few answers from people at a
# given stage. It is a Bayesian average, so a skill with three answers sits
# near the prior and only data in volume moves it, and its weight grows with
# the amount of evidence, so it fades in rather than dominating early. The
# explore term (UCB-style) keeps sparse skills from never being shown and so
# never getting any less sparse.
WEIGHTS = {"urgency": 1.0, "gap": 0.9, "demand": 0.35, "cohort": 0.35,
           "explore": 0.25, "recent": 0.8}
COHORT_PRIOR = 65       # the mean score assumed before any answers exist
COHORT_PRIOR_WEIGHT = 10  # how many answers the prior is worth
COHORT_FULL_AT = 50     # answers needed for the cohort term to reach full weight
RECENT_HOURS = 6

REASONS = {
    "urgency": "Fading: review it before it slips",
    "gap": "Widest gap to your bar",
    "demand": "Employers are asking for it now",
    "cohort": "People at your stage find this one hard",
    "explore": "Find your starting level",
}


def cohort_stats(skill_ids, stage):
    """{skill_id: (answers, mean score)} over everyone at this career stage."""
    rows = (Card.objects.filter(skill_id__in=skill_ids, answered_at__isnull=False,
                                candidate__experience_level=stage)
            .values("skill_id").annotate(n=Count("id"), mean=Avg("score")))
    return {r["skill_id"]: (r["n"], r["mean"] or 0) for r in rows}


def shrunk_mean(n, mean, prior=COHORT_PRIOR, weight=COHORT_PRIOR_WEIGHT):
    """Bayesian average: (n * observed + m * prior) / (n + m)."""
    return (n * mean + weight * prior) / (n + weight)


WORD = re.compile(r"[a-z0-9+#]{3,}")


def _demand_words(trending):
    words = set()
    for term in trending or []:
        words |= set(WORD.findall(str(term).lower()))
    return words


def score(memory, *, now, cohort=None, demand=frozenset(), total_reps=0):
    """Score one skill for today; returns (score, {term: contribution})."""
    n, mean = (cohort or {}).get(memory.skill_id, (0, 0))
    gap = max(memory.required - memory.effective(now), 0) / max(memory.required, 1)
    words = set(WORD.findall(memory.skill.name.lower()))
    recent = (memory.last_practiced is not None
              and (now - memory.last_practiced).total_seconds() < RECENT_HOURS * 3600)
    terms = {
        "urgency": (1 - memory.retention(now)) / (1 - 0.5) if memory.reps else 0,
        "gap": min(gap, 1),
        "demand": 1.0 if words & demand else 0.0,
        # Hardness = 1 - shrunk mean score, scaled by how much evidence exists.
        "cohort": (1 - shrunk_mean(n, mean) / 100) * min(n / COHORT_FULL_AT, 1),
        "explore": math.sqrt(math.log(total_reps + 2) / (memory.reps + 1)) / 2,
        "recent": 1.0 if recent else 0.0,
    }
    terms = {k: min(max(v, 0), 1) for k, v in terms.items()}
    parts = {k: WEIGHTS[k] * v * (-1 if k == "recent" else 1) for k, v in terms.items()}
    return sum(parts.values()), parts


def rank(memories, *, now=None, stage="", trending=None):
    """Every skill, best first, each with .rank_score and .why_today."""
    now = now or timezone.now()
    cohort = cohort_stats([m.skill_id for m in memories], stage) if memories else {}
    demand = _demand_words(trending)
    total = sum(m.reps for m in memories)
    ranked = []
    for m in memories:
        m.rank_score, m.rank_parts = score(m, now=now, cohort=cohort, demand=demand,
                                           total_reps=total)
        top = max((k for k in REASONS), key=lambda k: m.rank_parts[k])
        m.why_today = REASONS[top] if m.rank_parts[top] > 0 else "Keep it sharp"
        ranked.append(m)
    ranked.sort(key=lambda m: (-m.rank_score, m.skill.name))
    return ranked


def _context(memories):
    """Stage and trending terms for the person these memories belong to."""
    if not memories:
        return "", []
    profile = memories[0].candidate
    try:
        bp = profile.preferences.blueprint
    except Preferences.DoesNotExist:
        bp = None
    return profile.experience_level, ((bp.market or {}).get("trending") if bp else []) or []


def queue(memories, mood="", now=None):
    """Today's skills: the top of the ranking.

    Due skills always come before ones that are not due, so the spaced
    repetition schedule is kept; within each group the scoring function
    decides. A rough day gets a short, review-only session: keeping what you
    have is a win too, and nobody should be pushed into new material when
    they are struggling.
    """
    now = now or timezone.now()
    size = SESSION_SIZE.get(mood, 4)
    stage, trending = _context(memories)
    ranked = rank(memories, now=now, stage=stage, trending=trending)
    due = [m for m in ranked if m.is_due(now)]
    if mood == "ROUGH":
        return [m for m in due if m.reps][:size] or due[:size]
    rest = [m for m in ranked if not m.is_due(now)]
    return (due + rest)[:size]


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
            "next_review_days": round(memory.stability, 1), "level": level_name(memory.effective(now), memory.required)}


def recent_prompts(profile, skill, limit=12):
    return list(
        Card.objects.filter(candidate=profile, skill=skill)
        .order_by("-created_at").values_list("prompt", flat=True)[:limit]
    )
