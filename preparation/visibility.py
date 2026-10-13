"""Who may see whose data.

Two kinds of account:

  Student (a regular account)   sees only their own profile, plan, tasks,
                                scores and attempts. Lists show just them;
                                anyone else's page is a 404, not a 403, so
                                the site does not even confirm the record
                                exists.
  Coach (is_staff)              sees the whole cohort, plus the admin.

Anonymous aggregates - averages per skill, counts per category, the public
summary API - are visible to everyone. They describe the cohort without
showing any one person's progress.

Every view that reads per-person data goes through these helpers, so the
rule is written once.
"""

from .models import CandidateProfile, PlanTask, PreparationPlan, SkillAssessment


def is_coach(user):
    return bool(user and user.is_authenticated and user.is_staff)


def candidates_for(user):
    qs = CandidateProfile.objects.all()
    return qs if is_coach(user) else qs.filter(user=user)


def plans_for(user):
    qs = PreparationPlan.objects.all()
    return qs if is_coach(user) else qs.filter(candidate__user=user)


def tasks_for(user):
    qs = PlanTask.objects.all()
    return qs if is_coach(user) else qs.filter(plan__candidate__user=user)


def assessments_for(user):
    qs = SkillAssessment.objects.all()
    return qs if is_coach(user) else qs.filter(candidate__user=user)
