"""
Base (shared) settings for the Beacon project.

Split-settings pattern (Week 2):
    base.py         -> settings shared by every environment
    development.py  -> local machine, DEBUG = True
    production.py   -> deployed server, DEBUG = False

You never run base.py directly; you run one of the two children, which do
`from .base import *`.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# This file lives at:  <project root>/beacon_core/settings/base.py
# .parent -> settings/   .parent -> beacon_core/   .parent -> project root
# The extra .parent (compared to a default Django project) is needed because we
# moved settings.py one level deeper into a settings/ package.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Environment variables (.env) - Week 2, "three pillars of security"
# ---------------------------------------------------------------------------
def load_env(env_path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Written with the standard library only, so the project runs with nothing
    installed except Django. A production project would use python-dotenv or
    django-environ instead.
    """
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env(BASE_DIR / ".env")

# Never hard-code a real secret key. The fallback below is only good enough for
# a local classroom database; production.py refuses to start without a real one.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-key-replace-me-in-dotenv",
)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # django.contrib.sites is a hard requirement of allauth: a social login
    # callback has to know which domain it belongs to, and the Site row is
    # where that lives.
    "django.contrib.sites",
    # Assignment 5, Part 2: Google OAuth through django-allauth.
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Beacon feature apps
    "preparation",
]

# Which Site row the social callbacks belong to. Changing the deployed
# domain means updating that row (via the admin) as well as ALLOWED_HOSTS
# and the redirect URI registered with Google.
SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # allauth needs this to handle its own redirects and to keep the social
    # login flow's state between the outbound request and the callback.
    # Without it allauth raises ImproperlyConfigured at the first request.
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "beacon_core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-level templates/ folder, one sub-folder per feature app.
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Tells the templates whether Google credentials exist on
                # this machine, so the button is only shown when it works.
                "preparation.context_processors.google_oauth",
            ],
        },
    },
]

WSGI_APPLICATION = "beacon_core.wsgi.application"
ASGI_APPLICATION = "beacon_core.asgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Part 4 requires db.sqlite3 to sit at the project root (next to manage.py).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ---------------------------------------------------------------------------
# Authentication (Assignment 5, Part 1)
# ---------------------------------------------------------------------------
# These live in base.py rather than production.py so development and
# production behave the same way. Defined only in production, Django falls
# back to its own defaults everywhere else, and the default
# LOGIN_REDIRECT_URL is "/accounts/profile/", a route this project does not
# have: a successful login in development would land on a 404.
#
# @login_required and LoginRequiredMixin read LOGIN_URL to build the redirect,
# so naming the route here is what keeps "/accounts/login/" out of the view
# code.
LOGIN_URL = "preparation:login"
LOGIN_REDIRECT_URL = "preparation:dashboard"
LOGOUT_REDIRECT_URL = "preparation:login"


# ---------------------------------------------------------------------------
# Google OAuth via django-allauth (Assignment 5, Part 2)
# ---------------------------------------------------------------------------
# Two backends, both needed. ModelBackend keeps username/password working for
# the accounts created in Part 1; allauth's backend handles the social login.
# Dropping ModelBackend would lock out every existing user, including the
# superuser the admin needs.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# The credentials come from the environment, never from this file. .env is
# git-ignored; .env.example documents the two names without carrying values.
# Empty strings are a deliberate fallback rather than a crash: the test suite
# and CI have no Google credentials, and the rest of the site must still run
# without them. The button checks for them before rendering.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        # Configuring the app here rather than as a SocialApp row in the
        # database means the credentials live in the environment on each
        # machine, and nothing secret is ever written into db.sqlite3, which
        # this project commits.
        "APP": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        # Google has already verified the address it hands us, so making the
        # user confirm it by email again is friction with nothing behind it.
        "VERIFIED_EMAIL": True,
    }
}

# Let a Google login attach itself to an existing account with the same
# verified email, instead of refusing or silently creating a second account
# for the same person. Safe here only because VERIFIED_EMAIL is on: without
# that, anyone could claim an address they do not own.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Skip allauth's "you are about to sign in as ..." interstitial. The user
# just clicked a button that says Continue with Google; asking them to
# confirm again adds a page and tells them nothing.
SOCIALACCOUNT_LOGIN_ON_GET = True

# allauth's own account settings. Username and password stay the login
# method, because Part 1's forms are built on them.
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"

# A first-time Google sign-in creates an account with no profile, exactly
# like the signup form. Send it to onboarding too, instead of the cohort
# dashboard. Returning users still land on LOGIN_REDIRECT_URL.
ACCOUNT_SIGNUP_REDIRECT_URL = "preparation:onboarding"


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
# The URL prefix templates build on. {% static "css/beacon.css" %} becomes
# /static/css/beacon.css, so the path is never written out by hand.
STATIC_URL = "static/"

# Where our own CSS, images and fonts live in the repo. Project level rather
# than app level: the stylesheet and the logo belong to the whole site, not to
# the preparation app, and a second app would have to reach into a sibling
# app's folder to reuse them. App-level static/ is still the right home for
# anything only one app uses, and the app-directories finder keeps working
# alongside this.
STATICFILES_DIRS = [BASE_DIR / "static"]

# Where collectstatic gathers everything for a real deployment. Git-ignored:
# it is build output, assembled from STATICFILES_DIRS and each app's static/.
STATIC_ROOT = BASE_DIR / "staticfiles"

# User uploads (CandidateProfile.resume_file). Kept out of Git via .gitignore.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
