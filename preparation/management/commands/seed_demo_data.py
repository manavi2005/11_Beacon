"""Seed realistic test data for Beacon.

Run:  python manage.py seed_demo_data
      python manage.py seed_demo_data --flush   (wipe app data first)

Creates 6 candidate profiles, 12 skills, ~24 assessments, 6 plans and ~20 tasks,
which is enough to demonstrate every relationship and constraint in the model.
"""

import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from preparation.models import (
    CandidateProfile,
    PlanTask,
    PreparationPlan,
    Skill,
    SkillAssessment,
)

SKILLS = [
    ("Data structures & algorithms", Skill.Category.TECHNICAL),
    ("SQL & relational modeling", Skill.Category.TECHNICAL),
    ("Python fundamentals", Skill.Category.TECHNICAL),
    ("System design basics", Skill.Category.TECHNICAL),
    ("Version control with Git", Skill.Category.TECHNICAL),
    ("STAR-format storytelling", Skill.Category.BEHAVIORAL),
    ("Handling failure questions", Skill.Category.BEHAVIORAL),
    ("Negotiating an offer", Skill.Category.BEHAVIORAL),
    ("Product sense", Skill.Category.DOMAIN),
    ("Financial markets basics", Skill.Category.DOMAIN),
    ("Whiteboard communication", Skill.Category.COMMUNICATION),
    ("Resume & elevator pitch", Skill.Category.COMMUNICATION),
]

CANDIDATES = [
    # username, first, last, role, company, level, weeks until interview, concern
    ("achen", "Amara", "Chen", "Software Engineer Intern", "Stripe", "STU", 4, "TECH"),
    ("bpatel", "Bharat", "Patel", "Data Analyst", "John Deere", "NEW", 6, "RESUME"),
    ("cmoreno", "Camila", "Moreno", "Product Manager (APM)", "Google", "NEW", 3, "TIME"),
    ("dokafor", "Daniel", "Okafor", "Quantitative Trader", "Jane Street", "STU", 8, "TECH"),
    ("ekim", "Eunji", "Kim", "UX Researcher", "Duolingo", "EARLY", 5, "BEHAV"),
    ("flopez", "Felipe", "Lopez", "Backend Engineer", "Caterpillar", "EARLY", 10, "CONF"),
]

TASK_LIBRARY = [
    ("Solve 10 array & hashing problems", "Data structures & algorithms", 90),
    ("Write 5 JOIN queries against a sample schema", "SQL & relational modeling", 60),
    ("Draft 3 STAR stories from past projects", "STAR-format storytelling", 45),
    ("Record a 2-minute elevator pitch", "Resume & elevator pitch", 30),
    ("Design a URL shortener end to end", "System design basics", 120),
    ("Mock behavioral interview with a peer", "Handling failure questions", 60),
    ("Read one 10-K and summarize the risks", "Financial markets basics", 90),
    ("Rebuild your resume against the job posting", "Resume & elevator pitch", 75),
    ("Explain a past project on a whiteboard", "Whiteboard communication", 45),
    ("Practice an offer-negotiation roleplay", "Negotiating an offer", 30),
]


class Command(BaseCommand):
    help = "Populate the database with realistic Beacon test data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing Beacon data (not superusers) before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(11)  # Group 11 - keeps the demo data reproducible
        today = timezone.localdate()

        if options["flush"]:
            PlanTask.objects.all().delete()
            PreparationPlan.objects.all().delete()
            SkillAssessment.objects.all().delete()
            CandidateProfile.objects.all().delete()
            Skill.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.WARNING("Existing Beacon data cleared."))

        # ---- Skills ------------------------------------------------------
        skills = {}
        for name, category in SKILLS:
            skill, _ = Skill.objects.get_or_create(
                name=name,
                category=category,
                defaults={"description": f"Interview-relevant competency: {name}."},
            )
            skills[name] = skill
        self.stdout.write(f"Skills:            {Skill.objects.count()}")

        # ---- Candidates --------------------------------------------------
        profiles = []
        for username, first, last, role, company, level, weeks, concern in CANDIDATES:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@illinois.edu",
                },
            )
            if created:
                user.set_password("beacon12345")
                user.save()
            profile, _ = CandidateProfile.objects.get_or_create(
                user=user,
                defaults={
                    "target_role": role,
                    "target_company": company,
                    "experience_level": level,
                    "target_interview_date": today + timedelta(weeks=weeks),
                    "preparation_timeline_weeks": weeks,
                    "primary_concern": concern,
                    "resume_summary": (
                        f"{first} {last} - University of Illinois. Targeting a "
                        f"{role} role at {company}."
                    ),
                },
            )
            profiles.append(profile)
        self.stdout.write(f"Candidates:        {CandidateProfile.objects.count()}")

        # ---- Assessments (candidate x skill, unique together) -------------
        for profile in profiles:
            for skill in random.sample(list(skills.values()), 4):
                SkillAssessment.objects.get_or_create(
                    candidate=profile,
                    skill=skill,
                    defaults={
                        "proficiency_score": random.randint(25, 95),
                        "required_level": random.choice([60, 70, 80, 85]),
                        "assessed_on": today - timedelta(days=random.randint(0, 20)),
                        "notes": "Adaptive quiz result (seeded demo data).",
                    },
                )
        self.stdout.write(f"Assessments:       {SkillAssessment.objects.count()}")

        # ---- Plans and tasks ---------------------------------------------
        weeks_for = {p.pk: p.preparation_timeline_weeks for p in profiles}
        for profile in profiles:
            plan, _ = PreparationPlan.objects.get_or_create(
                candidate=profile,
                title=f"{profile.target_role} sprint",
                defaults={
                    "focus_role": profile.target_role,
                    "start_date": today - timedelta(days=random.randint(1, 10)),
                    "target_date": profile.target_interview_date,
                    "status": random.choice(
                        [
                            PreparationPlan.Status.ACTIVE,
                            PreparationPlan.Status.ACTIVE,
                            PreparationPlan.Status.DRAFT,
                        ]
                    ),
                },
            )
            for week, (title, skill_name, minutes) in enumerate(
                random.sample(TASK_LIBRARY, 4), start=1
            ):
                status = random.choice(
                    [
                        PlanTask.Status.TODO,
                        PlanTask.Status.TODO,
                        PlanTask.Status.IN_PROGRESS,
                        PlanTask.Status.DONE,
                    ]
                )
                PlanTask.objects.get_or_create(
                    plan=plan,
                    title=title,
                    defaults={
                        "skill": skills[skill_name],
                        "week_number": min(week, max(1, weeks_for[profile.pk])),
                        "instructions": f"Focus block for: {skill_name}.",
                        "rationale": (
                            f"Your diagnosis flagged {skill_name} as a gap against "
                            f"the {profile.target_role} requirement, and it is the "
                            "highest-weighted skill still below target."
                        ),
                        "due_date": today + timedelta(days=random.randint(2, 25)),
                        "estimated_minutes": minutes,
                        "priority": random.choice(
                            [
                                PlanTask.Priority.LOW,
                                PlanTask.Priority.MEDIUM,
                                PlanTask.Priority.HIGH,
                            ]
                        ),
                        "status": status,
                        "completed_on": today if status == PlanTask.Status.DONE else None,
                    },
                )
        self.stdout.write(f"Plans:             {PreparationPlan.objects.count()}")
        self.stdout.write(f"Tasks:             {PlanTask.objects.count()}")
        self.stdout.write(self.style.SUCCESS("Seed data loaded."))
