"""Prove that Beacon's constraints and on_delete rules actually fire.

Run:  python manage.py verify_constraints

Every check runs inside a transaction that is rolled back, so this command
never changes your data. Output is the evidence for the Part-4 requirements
"Uniqueness Constraint Validation" and "on_delete Behavior Validation";
save it to docs/data_model/constraint_validation.txt before submitting.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from preparation.models import (
    CandidateProfile,
    PlanTask,
    PreparationPlan,
    Skill,
    SkillAssessment,
)


class Command(BaseCommand):
    help = "Demonstrate that uniqueness constraints and on_delete rules work."

    def ok(self, message):
        self.stdout.write(self.style.SUCCESS(f"PASS  {message}"))

    def fail(self, message):
        self.stdout.write(self.style.ERROR(f"FAIL  {message}"))

    def header(self, message):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO(message))

    def handle(self, *args, **options):
        today = timezone.localdate()

        # ------------------------------------------------------------------
        # 1. UniqueConstraint: one assessment per (candidate, skill)
        # ------------------------------------------------------------------
        self.header("1) uniq_assessment_per_candidate_skill")
        existing = SkillAssessment.objects.select_related("candidate", "skill").first()
        if existing is None:
            self.fail("No assessments found - run `seed_demo_data` first.")
            return
        try:
            with transaction.atomic():
                SkillAssessment.objects.create(
                    candidate=existing.candidate,
                    skill=existing.skill,
                    proficiency_score=50,
                )
            self.fail("Duplicate assessment was accepted - constraint missing!")
        except IntegrityError as exc:
            self.ok(
                "Duplicate (candidate, skill) rejected by the database.\n"
                f"      candidate={existing.candidate_id} skill='{existing.skill.name}'\n"
                f"      {type(exc).__name__}: {exc}"
            )

        # ------------------------------------------------------------------
        # 2. UniqueConstraint: one plan title per candidate
        # ------------------------------------------------------------------
        self.header("2) uniq_plan_title_per_candidate")
        plan = PreparationPlan.objects.select_related("candidate").first()
        try:
            with transaction.atomic():
                PreparationPlan.objects.create(
                    candidate=plan.candidate,
                    title=plan.title,
                    focus_role=plan.focus_role,
                    target_date=today + timedelta(days=30),
                )
            self.fail("Duplicate plan title was accepted - constraint missing!")
        except IntegrityError as exc:
            self.ok(f"Duplicate plan title rejected: {exc}")

        # ------------------------------------------------------------------
        # 3. CheckConstraint: a plan cannot end before it starts
        # ------------------------------------------------------------------
        self.header("3) plan_ends_after_it_starts (CheckConstraint)")
        try:
            with transaction.atomic():
                PreparationPlan.objects.create(
                    candidate=plan.candidate,
                    title="Impossible backwards plan",
                    focus_role="Test",
                    start_date=today,
                    target_date=today - timedelta(days=5),
                )
            self.fail("Backwards date range was accepted - constraint missing!")
        except IntegrityError as exc:
            self.ok(f"target_date earlier than start_date rejected: {exc}")

        # ------------------------------------------------------------------
        # 4. Field validators: score above 100 rejected by full_clean()
        # ------------------------------------------------------------------
        self.header("4) proficiency_score validators (0-100)")
        try:
            SkillAssessment(
                candidate=existing.candidate,
                skill=existing.skill,
                proficiency_score=140,
            ).full_clean()
            self.fail("Score of 140 passed validation!")
        except ValidationError as exc:
            self.ok(f"Score of 140 rejected: {exc.messages}")

        # ------------------------------------------------------------------
        # 5. on_delete=PROTECT: a scored Skill cannot be deleted
        # ------------------------------------------------------------------
        self.header("5) SkillAssessment.skill -> on_delete=PROTECT")
        try:
            with transaction.atomic():
                existing.skill.delete()
            self.fail("Skill with assessments was deleted - PROTECT not working!")
        except ProtectedError as exc:
            self.ok(
                f"Deleting skill '{existing.skill.name}' blocked because "
                f"{len(exc.protected_objects)} assessment(s) reference it."
            )

        # ------------------------------------------------------------------
        # 6. on_delete=CASCADE: deleting a plan deletes its tasks
        # ------------------------------------------------------------------
        self.header("6) PlanTask.plan -> on_delete=CASCADE")
        task_count = plan.tasks.count()
        with transaction.atomic():
            plan_id = plan.pk
            plan.delete()
            remaining = PlanTask.objects.filter(plan_id=plan_id).count()
            transaction.set_rollback(True)  # undo: this is only a demonstration
        if remaining == 0:
            self.ok(
                f"Deleting plan '{plan.title}' removed all {task_count} of its "
                "tasks (rolled back afterwards)."
            )
        else:
            self.fail(f"{remaining} orphan task(s) survived the delete.")

        # ------------------------------------------------------------------
        # 7. on_delete=SET_NULL: deleting a tagged Skill keeps the task
        # ------------------------------------------------------------------
        self.header("7) PlanTask.skill -> on_delete=SET_NULL")
        tagged = PlanTask.objects.filter(skill__isnull=False).first()
        if tagged is None:
            self.fail("No task with a skill tag found.")
        else:
            with transaction.atomic():
                skill_name = tagged.skill.name
                # Assessments PROTECT the skill, so clear them inside the
                # rolled-back transaction to isolate the SET_NULL behaviour.
                SkillAssessment.objects.filter(skill=tagged.skill).delete()
                tagged.skill.delete()
                survivor = PlanTask.objects.filter(pk=tagged.pk).first()
                still_there = survivor is not None and survivor.skill_id is None
                transaction.set_rollback(True)
            if still_there:
                self.ok(
                    f"Deleting skill '{skill_name}' kept task '{tagged.title}' "
                    "and set its skill to NULL (rolled back afterwards)."
                )
            else:
                self.fail("Task did not survive its skill being deleted.")

        # ------------------------------------------------------------------
        # 8. on_delete=CASCADE on the OneToOneField to User
        # ------------------------------------------------------------------
        self.header("8) CandidateProfile.user -> on_delete=CASCADE")
        profile = CandidateProfile.objects.select_related("user").first()
        with transaction.atomic():
            username = profile.user.username
            profile.user.delete()
            orphan = CandidateProfile.objects.filter(pk=profile.pk).exists()
            transaction.set_rollback(True)
        if not orphan:
            self.ok(
                f"Deleting user '{username}' removed their profile too "
                "(rolled back afterwards)."
            )
        else:
            self.fail("Profile survived its user being deleted.")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("All constraint checks finished. Database unchanged.")
        )
        self.stdout.write(f"Skill rows still present: {Skill.objects.count()}")
        self.stdout.write(f"Plan rows still present:  {PreparationPlan.objects.count()}")
