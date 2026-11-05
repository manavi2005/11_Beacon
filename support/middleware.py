"""Record unhandled errors so support can see what broke for whom."""

import logging
from datetime import timedelta

from django.utils import timezone

log = logging.getLogger("beacon.support")
KEEP_DAYS = 30


class RecordErrorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Never let the recorder turn one error into two.
        try:
            from .models import ErrorEvent
            user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
            ErrorEvent.objects.create(
                user=user, method=request.method[:8], path=request.path[:200],
                kind=type(exception).__name__[:120], message=str(exception)[:500],
            )
            if timezone.now().minute == 0:  # cheap, occasional pruning
                ErrorEvent.objects.filter(
                    created_at__lt=timezone.now() - timedelta(days=KEEP_DAYS)).delete()
        except Exception:  # noqa: BLE001
            log.exception("could not record an error event")
        return None
