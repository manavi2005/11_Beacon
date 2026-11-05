"""What the support console keeps: problem reports, server errors and an
audit trail of every change staff make to someone's account.

Staff can see a lot (that is the point of a support tool), so every change
they make is written to StaffAction with who, whom, what and when. Errors
record where things broke, never request bodies, so answers and resumes
don't end up in a log.
"""

from django.conf import settings
from django.db import models


class SupportTicket(models.Model):
    class Category(models.TextChoices):
        BUG = "BUG", "Something isn't working"
        AI = "AI", "Questions or feedback seem wrong"
        ACCOUNT = "ACCT", "Account or sign-in"
        DATA = "DATA", "My progress or data"
        OTHER = "OTHER", "Something else"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "DONE", "Resolved"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="support_tickets")
    category = models.CharField(max_length=5, choices=Category.choices, default=Category.BUG)
    message = models.TextField(max_length=3000)
    page = models.CharField(max_length=200, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=4, choices=Status.choices, default=Status.OPEN)
    staff_note = models.TextField(blank=True, help_text="Shown to the person when resolved.")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_category_display()} from {self.user}"


class ErrorEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="+")
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=200)
    kind = models.CharField(max_length=120)
    message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} at {self.path}"


class StaffAction(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name="+")
    target = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="staff_actions_received")
    action = models.CharField(max_length=40)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor} {self.action} {self.target or ''}".strip()
