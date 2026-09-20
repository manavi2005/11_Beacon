"""Production settings - deployed server.

Run with:  python manage.py runserver --settings=beacon_core.settings.production
(In real deployment, gunicorn/uwsgi loads beacon_core.wsgi, which points here.)
"""

import os

from .base import *  # noqa: F401,F403

# DEBUG = False so visitors never see tracebacks, file paths or settings.
DEBUG = False

# With DEBUG = False, Django refuses any host that is not listed here.
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "beacon.example.com").split(",")
    if h.strip()
]

# A real deployment must supply its own key through the environment.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", SECRET_KEY)  # noqa: F405

# Basic hardening that costs nothing to switch on.
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
