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
from .onboarding import ROLE_CHOICES


class OnboardingForm(forms.Form):
    """Step 1 is the goal; step 2 is one 0-100 slider per catalog skill.

    The skill fields are built from the Skill table at runtime, so a skill
    added in the admin shows up here without a code change.
    """

    target_role = forms.ChoiceField(
        choices=[(r, r) for r in ROLE_CHOICES],
        initial="Software Engineer",
    )
    target_company = forms.CharField(max_length=120, required=False)
    experience_level = forms.ChoiceField(
        choices=CandidateProfile.ExperienceLevel.choices,
        initial=CandidateProfile.ExperienceLevel.STUDENT,
    )
    target_interview_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    primary_concern = forms.ChoiceField(
        choices=CandidateProfile.PrimaryConcern.choices,
        required=False,
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

    def clean_target_interview_date(self):
        value = self.cleaned_data["target_interview_date"]
        if value < timezone.localdate():
            raise forms.ValidationError("Pick a date in the future.")
        return value

    def skill_fields(self):
        """(skill, bound field) pairs, for grouping the sliders by category."""
        return [(skill, self[f"skill_{skill.pk}"]) for skill in self.skills]

    def ratings(self):
        return {skill.pk: self.cleaned_data[f"skill_{skill.pk}"] for skill in self.skills}
