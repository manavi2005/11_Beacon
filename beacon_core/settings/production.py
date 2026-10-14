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
    'SimonHwang1998.pythonanywhere.com'
] + [h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "beacon.example.com,127.0.0.1,localhost",
    ).split(",")
    if h.strip()
]

# A real deployment must supply its own key through the environment.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", SECRET_KEY)  # noqa: F405

# Basic hardening that costs nothing to switch on.
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# The local transformers model stays off here. Its weights alone are several
# times PythonAnywhere's 512 MB quota, and a free-tier worker has neither the
# memory nor the CPU seconds to run a 1.5B model per request. The hosted coach
# in preparation/coach.py serves the deployed site; screening is skipped and
# written answers go straight to it. Set LOCAL_LLM_ENABLED=true on a server
# that can actually hold the model.
LOCAL_LLM_ENABLED = os.environ.get("LOCAL_LLM_ENABLED", "false").lower() not in ("0", "false", "no", "off")

# LOGIN_URL, LOGIN_REDIRECT_URL and LOGOUT_REDIRECT_URL moved to base.py, so
# development gets them too. Defined only here, development fell back to
# Django's default LOGIN_REDIRECT_URL of "/accounts/profile/", which this
# project does not route.

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
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}
