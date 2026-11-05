from django.contrib import admin

from .models import ErrorEvent, StaffAction, SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("user__username", "message")


@admin.register(ErrorEvent)
class ErrorEventAdmin(admin.ModelAdmin):
    list_display = ("kind", "path", "user", "created_at")
    search_fields = ("kind", "path", "message")


@admin.register(StaffAction)
class StaffActionAdmin(admin.ModelAdmin):
    list_display = ("actor", "action", "target", "created_at")
    list_filter = ("action",)
    # The audit trail is append-only, even in the admin.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
