"""Django Admin configuration for the preparation app.

Every model is registered so a grader (or a teammate) can create, view and edit
records, and see relationships as dropdowns, without writing any SQL.
"""

from django.contrib import admin

from .models import CandidateProfile, PlanTask, PreparationPlan, Skill, SkillAssessment


class SkillAssessmentInline(admin.TabularInline):
    """Edit a candidate's quiz scores directly on their profile page."""

    model = SkillAssessment
    extra = 1
    autocomplete_fields = ["skill"]


class PlanTaskInline(admin.TabularInline):
    """Edit tasks directly on the plan they belong to."""

    model = PlanTask
    extra = 1
    fields = [
        "week_number",
        "title",
        "skill",
        "priority",
        "status",
        "due_date",
        "estimated_minutes",
    ]
    ordering = ["week_number"]


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "assessment_count"]
    list_filter = ["category"]
    search_fields = ["name", "description"]

    @admin.display(description="Times assessed")
    def assessment_count(self, obj):
        return obj.assessments.count()


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "target_role",
        "target_company",
        "experience_level",
        "target_interview_date",
        "days_left",
        "readiness",
    ]
    list_filter = ["experience_level", "target_company", "primary_concern"]
    search_fields = ["user__username", "user__first_name", "target_role"]
    inlines = [SkillAssessmentInline]

    @admin.display(description="Days to interview")
    def days_left(self, obj):
        return obj.days_until_interview

    @admin.display(description="Readiness")
    def readiness(self, obj):
        return f"{obj.readiness_percent}%"


@admin.register(SkillAssessment)
class SkillAssessmentAdmin(admin.ModelAdmin):
    list_display = ["candidate", "skill", "proficiency_score", "required_level", "gap"]
    list_filter = ["skill__category", "assessed_on"]
    search_fields = ["candidate__user__username", "skill__name"]
    autocomplete_fields = ["skill"]

    @admin.display(description="Gap")
    def gap(self, obj):
        return obj.gap


@admin.register(PreparationPlan)
class PreparationPlanAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "candidate",
        "focus_role",
        "status",
        "target_date",
        "week_position",
        "progress",
    ]
    list_filter = ["status", "generated_by_ai"]
    search_fields = ["title", "focus_role", "candidate__user__username"]
    date_hierarchy = "target_date"
    inlines = [PlanTaskInline]

    @admin.display(description="Week")
    def week_position(self, obj):
        return f"{obj.current_week} of {obj.total_weeks}"

    @admin.display(description="Completion")
    def progress(self, obj):
        return f"{obj.completion_percent}%"


@admin.register(PlanTask)
class PlanTaskAdmin(admin.ModelAdmin):
    list_display = ["title", "plan", "week_number", "skill", "priority", "status", "due_date"]
    list_filter = ["status", "priority", "week_number", "skill__category"]
    search_fields = ["title", "plan__title"]
    autocomplete_fields = ["skill"]
    list_editable = ["status"]
