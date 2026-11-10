"""Gentle daily reminders, opt-in only.

One email at most per day, never on a day the person has already practised,
and only when there is a real reason: skills starting to fade, or a streak
that would otherwise lapse. The wording invites, it never scolds.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from . import engine
from .models import Preferences


def message_for(profile, today=None):
    """(subject, body) or None when there's nothing worth saying."""
    memories = list(profile.memories.select_related("skill"))
    now = timezone.now()
    fading = [m for m in memories if m.reps and m.is_due(now)]
    streak = engine.streak(profile, today)
    if streak["done_today"]:
        return None
    name = profile.user.first_name or profile.user.username
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    link = f"{site}/today/" if site else "/today/"
    if fading:
        names = ", ".join(m.skill.name for m in fading[:3])
        subject = f"{len(fading)} skill{'s' if len(fading) != 1 else ''} worth a quick review"
        lead = (f"{names} {'is' if len(fading) == 1 else 'are'} just starting to fade. "
                f"A {max(3, len(fading[:5]) * 3)}-minute review now keeps "
                f"{'it' if len(fading) == 1 else 'them'} for days longer.")
    elif streak["days"] >= 2:
        subject = f"Keep your {streak['days']}-day streak going"
        lead = "One short session today keeps your rhythm. Even a single question counts."
    else:
        return None
    body = (f"Hi {name},\n\n{lead}\n\n{link}\n\nNot today? That's fine too: rest is part of it.\n\n"
            "Beacon\n\nYou're getting this because you turned on reminders. "
            "Turn them off any time under You in Beacon.")
    return subject, body


def send_due(today=None):
    today = today or timezone.localdate()
    sent = 0
    prefs = (Preferences.objects.filter(email_reminders=True)
             .exclude(last_reminded=today)
             .select_related("candidate__user"))
    for pref in prefs:
        profile = pref.candidate
        if not profile.user.email:
            continue
        message = message_for(profile, today)
        if not message:
            continue
        send_mail(message[0], message[1], None, [profile.user.email], fail_silently=True)
        pref.last_reminded = today
        pref.save(update_fields=["last_reminded"])
        sent += 1
    return sent
