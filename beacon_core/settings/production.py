"""Production settings - deployed server.

Run with:  python manage.py runserver --settings=beacon_core.settings.production
(In real deployment, gunicorn/uwsgi loads beacon_core.wsgi, which points here.)
"""

import os

from .base import *  # noqa: F401,F403

# DEBUG = False so visitors never see tracebacks, file paths or settings.
DEBUG = False

# With DEBUG = False, Django refuses any host that is not listed here. Both
# team deployments are always allowed; DJANGO_ALLOWED_HOSTS adds more (a
# custom domain, say) without a code change.
TEAM_HOSTS = ["manavi2005.pythonanywhere.com", "simonhwang1998.pythonanywhere.com"]
ALLOWED_HOSTS = TEAM_HOSTS + [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip() and h.strip().lower() not in TEAM_HOSTS
]
# Forms posted over https from these hosts pass Django's CSRF origin check.
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("127.0.0.1", "localhost")
]

# A real deployment must supply its own key through the environment. The
# development fallback is public (it is in this repository), and anyone who
# knows the key can forge session cookies, so production refuses to start
# without a real one rather than running insecurely.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 40 or SECRET_KEY.startswith("django-insecure") or "replace" in SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY in .env to a long random value (see docs/deployment/DEPLOY.md)."
    )

# PythonAnywhere terminates HTTPS at its proxy and forwards plain HTTP to
# Django, with X-Forwarded-Proto saying what the visitor used. Without this,
# request.is_secure() is False, allauth builds an http:// Google callback,
# and Google rejects it with redirect_uri_mismatch because only the https://
# address is registered. Safe because the proxy always sets the header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# The proxy sets X-Real-IP itself, so rate limits can trust it here (and
# only here: locally there is no proxy and the header could be invented).
TRUST_PROXY_HEADERS = True

# Hardening that costs nothing to switch on.
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Pages read the CSRF token from the template, never the cookie, so scripts
# don't need to see it.
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
# Browsers remember to use https for a year, so a network attacker can't
# downgrade a visit to http. No includeSubDomains: the parent domain isn't ours.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
# PythonAnywhere's "Force HTTPS" switch does the redirect; set this on any
# host without one.
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "false").lower() in ("1", "true", "yes")
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
# Deliberate, so `check --deploy` stays quiet about them: HSTS preload and
# includeSubDomains are one-way doors for a domain we don't fully own, and
# the https redirect is done by the host (see SECURE_SSL_REDIRECT above).
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W008", "security.W021"]

# Several web workers serve requests at once. Rate-limit counters and the AI
# circuit breaker must be shared between them, or each worker keeps its own
# count and every limit is multiplied by the number of workers. The database
# cache is shared and needs no extra service (deploy runs createcachetable).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "beacon_cache",
        "OPTIONS": {"MAX_ENTRIES": 50000},
    }
}

# Under load SQLite writers queue for a lock; wait for it instead of failing
# with "database is locked". (At real scale, move to Postgres: see DEPLOY.md.)
DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = 20  # noqa: F405

# Warnings and errors, including every rate-limit trip, go to the server's
# error log, where PythonAnywhere shows them on the Web tab.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING"},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "beacon": {"handlers": ["console"], "level": "INFO"},
    },
}

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
