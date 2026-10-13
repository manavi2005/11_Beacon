"""New-user onboarding: from a blank account to a personal preparation plan.

A user who has just signed up has no CandidateProfile, so nothing in Beacon
is about them yet. Onboarding asks for a target role, an interview date and
a self-rating per skill, then builds everything the rest of the site already
knows how to show:

    CandidateProfile    the goal
    SkillAssessment     one per skill: self-rating vs what the role requires
    PreparationPlan     dated from today to the interview
    PlanTask            the widest gaps first, spread across the weeks

The plan builder is deliberately rule-based. This is the Phase 1 (non-AI)
prototype: build_plan() is the exact seam the AI coach will replace later,
taking the same profile and assessments and returning the same plan shape.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    CandidateProfile,
    PlanTask,
    PreparationPlan,
    Skill,
    SkillAssessment,
)

DEFAULT_REQUIRED = 65

# What each target role demands, per skill (0-100). Any skill not listed for
# a role uses DEFAULT_REQUIRED, so a skill added to the catalog later is
# still measured.
ROLE_REQUIREMENTS = {
    "Software Engineer": {
        "Data structures & algorithms": 85, "System design basics": 70,
        "Python fundamentals": 80, "Version control with Git": 75,
        "SQL & relational modeling": 60, "Whiteboard communication": 75,
        "STAR-format storytelling": 65, "Handling failure questions": 65,
    },
    "Data Analyst": {
        "SQL & relational modeling": 85, "Python fundamentals": 75,
        "Product sense": 65, "Whiteboard communication": 70,
        "STAR-format storytelling": 70, "Data structures & algorithms": 50,
        "System design basics": 40,
    },
    "Product Manager": {
        "Product sense": 85, "STAR-format storytelling": 80,
        "Whiteboard communication": 80, "Resume & elevator pitch": 75,
        "SQL & relational modeling": 55, "Data structures & algorithms": 40,
        "System design basics": 55,
    },
    "Quantitative Trader": {
        "Financial markets basics": 85, "Data structures & algorithms": 80,
        "Python fundamentals": 80, "Negotiating an offer": 65,
        "Whiteboard communication": 75, "System design basics": 45,
    },
    "UX Researcher": {
        "Product sense": 80, "STAR-format storytelling": 80,
        "Whiteboard communication": 80, "Resume & elevator pitch": 75,
        "Data structures & algorithms": 30, "System design basics": 35,
        "SQL & relational modeling": 45, "Python fundamentals": 40,
    },
    "Backend Engineer": {
        "System design basics": 85, "Data structures & algorithms": 80,
        "SQL & relational modeling": 80, "Python fundamentals": 80,
        "Version control with Git": 80,
    },
}
# For someone with no specific role in mind, or a mix of roles: a balanced
# bar where the skills every interview tests (telling stories, explaining
# your thinking, presenting yourself) matter most.
GENERAL_ROLE = "General interview readiness"
ROLE_REQUIREMENTS[GENERAL_ROLE] = {
    "STAR-format storytelling": 75, "Handling failure questions": 75,
    "Whiteboard communication": 70, "Resume & elevator pitch": 75,
    "Negotiating an offer": 60, "Data structures & algorithms": 50,
    "Python fundamentals": 50, "SQL & relational modeling": 50,
    "System design basics": 45, "Version control with Git": 50,
    "Product sense": 55, "Financial markets basics": 45,
}
ROLE_CHOICES = list(ROLE_REQUIREMENTS)
MAX_ROLES = 3

# What kind of work someone enjoys -> the roles that fit it. Onboarding asks
# this first, so a user who does not know which role to aim for gets
# suggestions instead of a blank dropdown.
INTERESTS = {
    "build": ("Building software", "Writing code, shipping features",
              ["Software Engineer", "Backend Engineer"]),
    "data": ("Working with data", "Finding answers in numbers",
             ["Data Analyst", "Quantitative Trader"]),
    "product": ("Shaping products", "Deciding what to build and why",
                ["Product Manager", "UX Researcher"]),
    "people": ("Understanding people", "Research, interviews, design",
               ["UX Researcher", "Product Manager"]),
    "markets": ("Finance and markets", "Trading, risk, the economy",
                ["Quantitative Trader", "Data Analyst"]),
    "unsure": ("Not sure yet", "Keep my options open",
               [GENERAL_ROLE]),
}
INTEREST_CHOICES = [(key, label) for key, (label, _desc, _roles) in INTERESTS.items()]


def suggested_roles(interest_keys):
    """Roles that fit the chosen interests, most-matched first."""
    counts = {}
    for key in interest_keys:
        for rank, role in enumerate(INTERESTS.get(key, ("", "", []))[2]):
            counts[role] = counts.get(role, 0) + (2 - rank)
    return sorted(counts, key=lambda r: (-counts[r], ROLE_CHOICES.index(r)))


def roles_label(roles):
    return " + ".join(roles) if roles else GENERAL_ROLE

# Concrete practice per skill, hardest-hitting first. Minutes are estimates.
TASKS_BY_SKILL = {
    "Data structures & algorithms": [
        ("Solve 10 array & hashing problems", 90),
        ("Solve 6 tree and graph traversal problems", 120),
        ("Timed mock: 2 medium problems in 45 minutes", 60),
    ],
    "SQL & relational modeling": [
        ("Write 5 JOIN queries against a sample schema", 60),
        ("Solve 5 window-function questions", 75),
        ("Model a schema for a product you use", 60),
    ],
    "Python fundamentals": [
        ("Rebuild 3 small scripts without looking anything up", 60),
        ("Practise list, dict and generator idioms", 45),
    ],
    "System design basics": [
        ("Design a URL shortener end to end", 120),
        ("Explain caching, queues and sharding out loud", 60),
    ],
    "Version control with Git": [
        ("Resolve a merge conflict in a practice repo", 30),
        ("Walk through your team's branching strategy", 30),
    ],
    "STAR-format storytelling": [
        ("Draft 3 STAR stories from past projects", 45),
        ("Tell each story in under 2 minutes, recorded", 40),
    ],
    "Handling failure questions": [
        ("Write your strongest 'tell me about a failure' answer", 40),
        ("Mock behavioral interview with a peer", 60),
    ],
    "Negotiating an offer": [
        ("Research the salary band for your target role", 30),
        ("Practice an offer-negotiation roleplay", 30),
    ],
    "Product sense": [
        ("Critique one product you use daily: users, metrics, fixes", 60),
        ("Answer 3 'how would you improve X' prompts", 75),
    ],
    "Financial markets basics": [
        ("Read one 10-K and summarise the risks", 90),
        ("Explain 5 market terms without notes", 30),
    ],
    "Whiteboard communication": [
        ("Explain a past project on a whiteboard", 45),
        ("Talk through a problem while solving it, recorded", 45),
    ],
    "Resume & elevator pitch": [
        ("Rebuild your resume against the job posting", 75),
        ("Record a 2-minute elevator pitch", 30),
    ],
}

MAX_TASKS = 12


def required_level(roles, skill_name):
    """The bar for one skill. With several roles it is the highest of them:
    to be ready for all of them you have to clear the toughest one."""
    if isinstance(roles, str):
        roles = [roles]
    levels = [
        ROLE_REQUIREMENTS.get(role, {}).get(skill_name, DEFAULT_REQUIRED)
        for role in roles or [GENERAL_ROLE]
    ]
    return max(levels)


def _priority(gap):
    if gap >= 25:
        return PlanTask.Priority.HIGH
    if gap >= 10:
        return PlanTask.Priority.MEDIUM
    return PlanTask.Priority.LOW


def build_plan(profile):
    """Turn a profile's assessments into a dated plan of tasks.

    Rules, in order:
      1. Only skills below the required level get tasks.
      2. The widest gap gets the most tasks (up to 3), the next widest up
         to 2, the rest 1, capped at MAX_TASKS so the plan stays doable.
      3. Tasks are spread across the weeks in gap order, so week 1 starts
         on the skill that is furthest behind.
    """
    today = timezone.localdate()
    weeks = profile.preparation_timeline_weeks
    target = profile.target_interview_date or today + timedelta(weeks=weeks)

    # Keep earlier plans as history, but only one is active.
    profile.plans.filter(status=PreparationPlan.Status.ACTIVE).update(
        status=PreparationPlan.Status.ARCHIVED
    )
    base_title = f"{weeks}-week {profile.target_role} plan"[:140]
    title, n = base_title, 2
    while profile.plans.filter(title=title).exists():
        title, n = f"{base_title} ({n})", n + 1

    plan = PreparationPlan.objects.create(
        candidate=profile,
        title=title,
        focus_role=profile.target_role,
        start_date=today,
        target_date=max(target, today),
        status=PreparationPlan.Status.ACTIVE,
        generated_by_ai=False,
    )

    gaps = sorted(
        (
            (a.required_level - a.proficiency_score, a)
            for a in profile.assessments.select_related("skill")
            if a.required_level > a.proficiency_score
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )

    chosen = []
    for rank, (gap, assessment) in enumerate(gaps):
        allowance = 3 if rank == 0 else 2 if rank == 1 else 1
        for title_, minutes in TASKS_BY_SKILL.get(assessment.skill.name, [])[:allowance]:
            chosen.append((gap, assessment, title_, minutes))
    chosen = chosen[:MAX_TASKS]

    for i, (gap, assessment, task_title, minutes) in enumerate(chosen):
        week = min(1 + i * weeks // max(len(chosen), 1), weeks)
        PlanTask.objects.create(
            plan=plan,
            skill=assessment.skill,
            title=task_title,
            week_number=week,
            due_date=min(today + timedelta(weeks=week), plan.target_date),
            estimated_minutes=minutes,
            priority=_priority(gap),
            rationale=(
                f"You rated {assessment.skill.name} at {assessment.proficiency_score}; "
                f"{_who_expects(profile)} about {assessment.required_level}. "
                f"Closing that {gap}-point gap is "
                f"{'your top priority' if gap == gaps[0][0] else 'on the critical path'}."
            ),
        )
    return plan


def _who_expects(profile):
    roles = profile.target_roles or [profile.target_role]
    if roles == [GENERAL_ROLE]:
        return "most interviews expect"
    if len(roles) > 1:
        return "the toughest of your target roles expects"
    return f"{roles[0]} roles expect"


@transaction.atomic
def complete_onboarding(user, *, target_roles, target_company, experience_level,
                        target_interview_date, prep_weeks, primary_concern,
                        ratings, interests=(), about=""):
    """Create or update the profile, record self-ratings, build the plan.

    target_roles is one or more role names; each skill's bar is the highest
    among them. With no interview date, prep_weeks sets an open-ended plan
    length instead and the date stays blank. ratings maps Skill pk ->
    self-rating 0-100. Running it again (a retake) updates the same rows and
    builds a fresh plan; the old one is archived.
    """
    today = timezone.localdate()
    if target_interview_date:
        days = max((target_interview_date - today).days, 7)
        weeks = max(1, min(52, -(-days // 7)))
    else:
        weeks = max(1, min(52, int(prep_weeks or 6)))
    roles = list(target_roles) or [GENERAL_ROLE]

    profile, _ = CandidateProfile.objects.update_or_create(
        user=user,
        defaults={
            "target_role": roles_label(roles)[:120],
            "target_roles": roles,
            "interests": list(interests),
            "target_company": target_company,
            "experience_level": experience_level,
            "target_interview_date": target_interview_date,
            "preparation_timeline_weeks": weeks,
            "primary_concern": primary_concern,
            "resume_summary": about,
        },
    )
    for skill in Skill.objects.filter(pk__in=ratings):
        SkillAssessment.objects.update_or_create(
            candidate=profile,
            skill=skill,
            defaults={
                "proficiency_score": ratings[skill.pk],
                "required_level": required_level(roles, skill.name),
                "assessed_on": today,
                "notes": "Self-assessment during onboarding.",
            },
        )
    return profile, build_plan(profile)
