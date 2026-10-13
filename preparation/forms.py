from django import forms

from .models import PlanTask


class PlanTaskForm(forms.ModelForm):
    class Meta:
        model = PlanTask
        fields = [
            "plan",
            "skill",
            "title",
            "week_number",
            "instructions",
            "rationale",
            "due_date",
            "estimated_minutes",
            "priority",
            "status",
        ]
        widgets = {
            "due_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "instructions": forms.Textarea(
                attrs={"rows": 4}
            ),
            "rationale": forms.Textarea(
                attrs={"rows": 4}
            ),
        }

# ---------------------------------------------------------------------------
# Onboarding (Assignment 5 - the start-from-scratch user journey)
# ---------------------------------------------------------------------------
from datetime import timedelta

from django.utils import timezone

from .models import CandidateProfile, Skill
from .onboarding import GENERAL_ROLE, INTEREST_CHOICES, MAX_ROLES, ROLE_CHOICES


class OnboardingForm(forms.Form):
    """Three steps: about you, your goal, your skills.

    1. Interests (what kind of work you enjoy), experience, biggest worry,
       and an optional free-text "about you" that is saved as the
       profile's resume summary.
    2. One to three target roles, or "General interview readiness", and
       either an interview date or, if there is none yet, a plan length.
    3. One 0-100 slider per catalog skill. These fields are built from the
       Skill table at runtime, so a skill added in the admin shows up here
       without a code change.
    """

    PREP_WEEK_CHOICES = [("4", "4 weeks"), ("6", "6 weeks"), ("8", "8 weeks"), ("12", "12 weeks")]

    interests = forms.MultipleChoiceField(
        choices=INTEREST_CHOICES, required=False,
        widget=forms.CheckboxSelectMultiple,
        label="What kind of work do you enjoy?",
    )
    experience_level = forms.ChoiceField(
        choices=CandidateProfile.ExperienceLevel.choices,
        initial=CandidateProfile.ExperienceLevel.STUDENT,
    )
    primary_concern = forms.ChoiceField(
        choices=[("", "No particular worry")] + list(CandidateProfile.PrimaryConcern.choices),
        required=False, label="Biggest worry about interviews",
    )
    about = forms.CharField(
        required=False, max_length=2000, label="Anything else? (optional)",
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "A line about your background, or paste your resume summary.",
        }),
    )

    target_roles = forms.MultipleChoiceField(
        choices=[(r, r) for r in ROLE_CHOICES],
        widget=forms.CheckboxSelectMultiple,
        label="Which roles are you preparing for?",
        error_messages={"required": "Pick at least one role, or General interview readiness."},
    )
    target_company = forms.CharField(max_length=120, required=False,
                                     label="Target company (optional)")
    has_interview = forms.ChoiceField(
        choices=[("yes", "I have an interview date"), ("no", "No interview yet")],
        widget=forms.RadioSelect, initial="no", label="Is an interview booked?",
    )
    target_interview_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}),
        label="Interview date",
    )
    prep_weeks = forms.ChoiceField(
        choices=PREP_WEEK_CHOICES, initial="6", required=False,
        label="How long do you want to prepare?",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_interview_date"].initial = (
            timezone.localdate() + timedelta(weeks=6)
        )
        self.skills = list(Skill.objects.order_by("category", "name"))
        for skill in self.skills:
            self.fields[f"skill_{skill.pk}"] = forms.IntegerField(
                min_value=0, max_value=100, initial=50, label=skill.name,
                widget=forms.NumberInput(attrs={"type": "range", "step": 5}),
            )

    def clean_target_roles(self):
        roles = self.cleaned_data["target_roles"]
        if len(roles) > MAX_ROLES:
            raise forms.ValidationError(f"Pick up to {MAX_ROLES} roles, so the plan stays focused.")
        if GENERAL_ROLE in roles and len(roles) > 1:
            # General is the "no specific role" option. Next to a specific
            # role it adds nothing, so it is dropped rather than shown.
            roles = [r for r in roles if r != GENERAL_ROLE]
        return roles

    def clean(self):
        data = super().clean()
        if data.get("has_interview") == "yes":
            date = data.get("target_interview_date")
            if not date:
                self.add_error("target_interview_date", "Add the date, or choose 'No interview yet'.")
            elif date < timezone.localdate():
                self.add_error("target_interview_date", "Pick a date in the future.")
        else:
            data["target_interview_date"] = None
            if not data.get("prep_weeks"):
                data["prep_weeks"] = "6"
        return data

    def skill_fields(self):
        """(skill, bound field) pairs, for grouping the sliders by category."""
        return [(skill, self[f"skill_{skill.pk}"]) for skill in self.skills]

    def ratings(self):
        return {skill.pk: self.cleaned_data[f"skill_{skill.pk}"] for skill in self.skills}
