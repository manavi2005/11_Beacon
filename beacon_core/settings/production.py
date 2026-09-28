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


# ---------------------------------------------------------------------------
# Static files: cache busting
# ---------------------------------------------------------------------------
# The problem this solves. Static files want a long cache lifetime, because
# re-downloading an unchanged stylesheet on every page view is waste. But a
# long lifetime and a fixed filename are a bad pair: ship a fix to
# beacon.css and every browser that already cached it keeps the old copy
# until the cache expires. The user sees a half-broken page and "hard refresh"
# becomes the support answer.
#
# ManifestStaticFilesStorage removes the conflict. collectstatic hashes the
# contents of each file into its name:
#
#     css/beacon.css  ->  css/beacon.6f4e1b2a9c3d.css
#
# and writes staticfiles.json mapping the plain name to the hashed one.
# {% static "css/beacon.css" %} reads that manifest, so templates keep naming
# the file the readable way and the served URL carries the hash.
#
# The filename now depends on the content, so editing the CSS changes the URL,
# and a changed URL is a different cache entry that the browser has to fetch.
# Nothing expires early, nothing stale is served, and the cache can be set to
# a year without risk.
#
# Development deliberately does not use this: manage.py runserver serves
# straight from STATICFILES_DIRS, an edit shows up on reload, and there is no
# manifest to keep in step.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}
