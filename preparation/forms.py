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