from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .analytics import PROVIDERS, sample_data, summarize


@never_cache
@login_required
def index(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied("This dashboard is restricted to superusers.")
    days = request.GET.get("days", "30")
    days = int(days) if days in {"7", "14", "30"} else 30
    provider = request.GET.get("provider", "all")
    provider = provider if provider in PROVIDERS else "all"
    today = timezone.localdate()
    start = (today-timedelta(days=days-1)).isoformat()
    rows = [r for r in sample_data(today) if r["day"] >= start and (provider == "all" or r["provider"] == provider)]
    data = summarize(rows, today, days)
    return render(request, "dashboard/index.html", dict(data=data, days=days, provider=provider, providers=PROVIDERS))
