from django.contrib import admin

from .models import Card, DayLog, InterviewSession, Preferences, RoleBlueprint, SkillMemory


@admin.register(RoleBlueprint)
class RoleBlueprintAdmin(admin.ModelAdmin):
    list_display = ("title", "stage", "source", "created_at")
    list_filter = ("source", "stage")
    search_fields = ("title",)


@admin.register(SkillMemory)
class SkillMemoryAdmin(admin.ModelAdmin):
    list_display = ("candidate", "skill", "strength", "required", "stability", "due_at", "reps")
    search_fields = ("candidate__user__username", "skill__name")


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("candidate", "skill", "kind", "score", "source", "created_at")
    list_filter = ("kind", "source", "is_review")
    search_fields = ("candidate__user__username", "skill__name")


@admin.register(DayLog)
class DayLogAdmin(admin.ModelAdmin):
    list_display = ("candidate", "date", "mood", "cards_done", "interviews_done", "xp", "readiness")
    list_filter = ("mood",)


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ("candidate", "role", "mode", "score", "started_at", "finished_at")
    list_filter = ("mode",)


@admin.register(Preferences)
class PreferencesAdmin(admin.ModelAdmin):
    list_display = ("candidate", "email_reminders", "last_reminded", "blueprint")
