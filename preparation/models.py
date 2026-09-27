"""
Data model for Beacon - AI Personal Career Coach (Team: Career Coaches).

The five models below mirror the four features in our Project Idea Description:

    Resume & goal identification -> CandidateProfile
    Skills diagnosis             -> Skill, SkillAssessment
    Plan generator               -> PreparationPlan
    Progress tracker             -> PlanTask

Reading order: Skill -> CandidateProfile -> SkillAssessment -> PreparationPlan
-> PlanTask.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Skill(models.Model):
    """A single competency Beacon can diagnose and coach, e.g. "SQL joins".

    Exists as its own table (rather than as free text on an assessment) so every
    candidate is scored against the *same* catalog. That is what lets Beacon
    compare a candidate's proficiency with the requirements of a target role and
    generate a plan for the gap.
    """

    class Category(models.TextChoices):
        TECHNICAL = "TECH", "Technical"
        BEHAVIORAL = "BEHAV", "Behavioral"
        DOMAIN = "DOMAIN", "Domain knowledge"
        COMMUNICATION = "COMM", "Communication"

    name = models.CharField(max_length=100)
    category = models.CharField(
        max_length=6, choices=Category.choices, default=Category.TECHNICAL
    )
    description = models.TextField(
        blank=True, help_text="What mastery of this skill looks like in an interview."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Default ordering: group the catalog by category, then alphabetically -
        # the order the skills-diagnosis quiz presents them in.
        ordering = ["category", "name"]
        constraints = [
            # Multi-field uniqueness: the same name may not appear twice inside
            # one category, but "Storytelling" can exist as both a behavioral and
            # a communication skill.
            models.UniqueConstraint(
                fields=["name", "category"], name="uniq_skill_name_per_category"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def get_absolute_url(self):
        """Canonical page for this skill.

        The model owns its own URL, so templates write
        {{ skill.get_absolute_url }} instead of rebuilding the path by hand.
        """
        return reverse("preparation:skill_detail", args=[self.pk])


class CandidateProfile(models.Model):
    """One Beacon user's career goal: who they are and what job they are chasing.

    Kept separate from django.contrib.auth.User because User answers "who is
    logged in" while this model answers "what is this person preparing for".
    Splitting them means our product questions can change without ever touching
    Django's auth table.
    """

    class ExperienceLevel(models.TextChoices):
        STUDENT = "STU", "Current student"
        NEW_GRAD = "NEW", "New graduate"
        EARLY_CAREER = "EARLY", "Early career (1-3 yrs)"

    class PrimaryConcern(models.TextChoices):
        """The optional "what worries you most?" answer on the setup screen."""

        TECHNICAL = "TECH", "Technical rounds"
        BEHAVIORAL = "BEHAV", "Behavioral questions"
        RESUME = "RESUME", "Resume and elevator pitch"
        CONFIDENCE = "CONF", "Confidence under pressure"
        TIME = "TIME", "Not enough time to prepare"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
        help_text="One login = one career profile.",
    )
    target_role = models.CharField(
        max_length=120, help_text="e.g. Software Engineer Intern"
    )
    target_company = models.CharField(max_length=120, blank=True)
    experience_level = models.CharField(
        max_length=5, choices=ExperienceLevel.choices, default=ExperienceLevel.STUDENT
    )
    resume_summary = models.TextField(
        blank=True,
        help_text="Plain-text resume the parser turns into an initial skill list.",
    )
    resume_file = models.FileField(
        upload_to="resumes/",
        blank=True,
        null=True,
        help_text="Original upload from the drag-and-drop area on the setup screen.",
    )
    target_interview_date = models.DateField(
        null=True,
        blank=True,
        help_text="Deadline Beacon plans backwards from. Blank = open-ended prep.",
    )
    preparation_timeline_weeks = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(52)],
        help_text="Weeks the user says they have. Drives the length of the roadmap.",
    )
    primary_concern = models.CharField(
        max_length=6,
        choices=PrimaryConcern.choices,
        blank=True,
        help_text="Optional. Used to weight which skill gaps get tackled first.",
    )
    # Declared through SkillAssessment so the link between a candidate and a
    # skill always carries a score and a date, never a bare association.
    skills = models.ManyToManyField(
        Skill,
        through="SkillAssessment",
        related_name="candidates",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Most recently updated profile first - whoever is actively preparing
        # sits at the top of the coach dashboard.
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} -> {self.target_role}"

    def get_absolute_url(self):
        """Canonical page for this candidate."""
        return reverse("preparation:candidate_detail", args=[self.pk])

    @property
    def days_until_interview(self):
        """Days left before the target interview, or None if no date is set."""
        if not self.target_interview_date:
            return None
        return (self.target_interview_date - timezone.localdate()).days

    @property
    def readiness_percent(self):
        """The "Overall Readiness" figure shown on the roadmap screen.

        Derived, not stored: the mean of each assessment's proficiency measured
        against what the target role requires, capped at 100 per skill so one
        very strong skill cannot hide a gap elsewhere.
        """
        assessments = list(self.assessments.all())
        if not assessments:
            return 0
        ratios = [
            min(a.proficiency_score / a.required_level, 1) if a.required_level else 1
            for a in assessments
        ]
        return round(sum(ratios) / len(ratios) * 100)


class SkillAssessment(models.Model):
    """The result of Beacon's adaptive quiz for one candidate on one skill.

    This is the "skill gap" row: proficiency_score is what the candidate can do,
    required_level is what the target role demands, and the difference between
    them is what the plan generator turns into tasks.
    """

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,  # scores are meaningless without their profile
        related_name="assessments",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,  # never silently delete scored history
        related_name="assessments",
    )
    proficiency_score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quiz result, 0-100.",
    )
    required_level = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Level the target role demands, 0-100.",
    )
    assessed_on = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)

    class Meta:
        # Newest assessment first, then by skill, for a stable readable order.
        ordering = ["-assessed_on", "skill__name"]
        constraints = [
            # One current score per candidate per skill: re-taking the quiz
            # updates the row instead of piling up duplicates.
            models.UniqueConstraint(
                fields=["candidate", "skill"],
                name="uniq_assessment_per_candidate_skill",
            ),
            # A gap only makes sense if both numbers sit on the same 0-100 scale.
            models.CheckConstraint(
                condition=models.Q(proficiency_score__lte=100)
                & models.Q(required_level__lte=100),
                name="scores_within_0_100",
            ),
        ]

    def __str__(self):
        return f"{self.skill.name}: {self.proficiency_score}/100 ({self.candidate_id})"

    @property
    def gap(self):
        """How far below the role's requirement this candidate currently is."""
        return max(self.required_level - self.proficiency_score, 0)


class PreparationPlan(models.Model):
    """A time-boxed preparation roadmap generated for one candidate.

    A candidate can hold several plans - one per target role, or a regenerated
    plan after a failed interview - so this is a ForeignKey, not a OneToOneField.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "DONE", "Completed"
        ARCHIVED = "ARCH", "Archived"

    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="plans",
    )
    title = models.CharField(max_length=150, help_text="e.g. 4-week SWE intern sprint")
    focus_role = models.CharField(max_length=120)
    start_date = models.DateField(default=timezone.localdate)
    target_date = models.DateField(help_text="Date the plan must be finished by.")
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.DRAFT)
    generated_by_ai = models.BooleanField(
        default=True,
        help_text="False when a user hand-writes or heavily edits the plan.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Soonest deadline first: the plan that needs attention sits on top.
        ordering = ["target_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "title"], name="uniq_plan_title_per_candidate"
            ),
            models.CheckConstraint(
                condition=models.Q(target_date__gte=models.F("start_date")),
                name="plan_ends_after_it_starts",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def get_absolute_url(self):
        """Canonical page for this plan."""
        return reverse("preparation:plan_detail", args=[self.pk])

    @property
    def completion_percent(self):
        """Share of tasks marked done - the number the progress tracker shows."""
        total = self.tasks.count()
        if total == 0:
            return 0
        done = self.tasks.filter(status=PlanTask.Status.DONE).count()
        return round(done / total * 100)

    @property
    def total_weeks(self):
        """Length of the roadmap in weeks (Screen 3 draws one row per week)."""
        span_days = (self.target_date - self.start_date).days
        return max(1, -(-span_days // 7))  # ceiling division

    @property
    def current_week(self):
        """Week number the user is in today, clamped to the plan's range.

        Screen 3 marks earlier weeks Completed, this one Current, and later
        ones Upcoming, so this single number drives all three states.
        """
        elapsed = (timezone.localdate() - self.start_date).days
        if elapsed < 0:
            return 1
        return min(elapsed // 7 + 1, self.total_weeks)


class PlanTask(models.Model):
    """One concrete action inside a plan, e.g. "Mock behavioral interview".

    Tasks are the unit the progress tracker updates. Each one points back at the
    skill it is meant to close the gap on, so progress can be reported per skill
    as well as per plan.
    """

    class Status(models.TextChoices):
        TODO = "TODO", "To do"
        IN_PROGRESS = "DOING", "In progress"
        DONE = "DONE", "Done"
        SKIPPED = "SKIP", "Skipped"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    plan = models.ForeignKey(
        PreparationPlan,
        on_delete=models.CASCADE,  # deleting a plan deletes the tasks inside it
        related_name="tasks",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,  # keep the task, just forget the tag
        null=True,
        blank=True,
        related_name="tasks",
        help_text="Skill gap this task is meant to close.",
    )
    title = models.CharField(max_length=150)
    week_number = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(52)],
        help_text="Which week of the roadmap this task belongs to (Screen 3).",
    )
    instructions = models.TextField(blank=True)
    rationale = models.TextField(
        blank=True,
        help_text=(
            "Why Beacon picked this task - shown under 'Why these "
            "recommendations?' and on the recommended-next card."
        ),
    )
    due_date = models.DateField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(
        default=60, validators=[MinValueValidator(5), MaxValueValidator(600)]
    )
    priority = models.IntegerField(choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=5, choices=Status.choices, default=Status.TODO)
    completed_on = models.DateField(null=True, blank=True)

    class Meta:
        # Roadmap week first, then priority and due date within the week -
        # exactly the order Screen 3 lists them in.
        ordering = ["week_number", "-priority", "due_date", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "title"], name="uniq_task_title_per_plan"
            )
        ]

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    def get_absolute_url(self):
        """Canonical page for this task."""
        return reverse("preparation:task_detail", args=[self.pk])
