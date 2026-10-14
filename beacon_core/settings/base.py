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
import sys
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

    python-dotenv when it is installed, which is the normal case and what
    requirements.txt asks for. The stdlib fallback below keeps the project
    runnable with nothing but Django present, which is how it started and
    still how a teammate who has only pip-installed Django will see it.

    Neither path overwrites a variable that is already set, so a real
    environment variable always beats the file.
    """
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv(env_path, override=False)
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
                # The site menu, built from preparation/navigation.py.
                "preparation.navigation.navigation",
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

# ---------------------------------------------------------------------------
# AI coach (preparation/coach.py)
# ---------------------------------------------------------------------------
# Any OpenAI-compatible chat API, configured only here and in .env, so a
# provider swap is never a code change. Every host below is on
# PythonAnywhere's free-tier outbound allowlist.
#
# Three tiers, picked automatically:
#   1. LLM_API_KEY set     -> LLM_BASE_URL / LLM_MODEL (default: Groq,
#                             open-weight Llama 3.3 70B). Fast and reliable.
#   2. no key (default)    -> Pollinations' free anonymous tier, which needs no
#                             account at all and serves OpenAI's open-weight
#                             gpt-oss-20b. Slower and rate-limited, but it means
#                             the coach is AI-powered out of the box.
#   3. LLM_ENABLED=false   -> rules only. The test suite and CI run this way.
LLM_ENABLED = os.environ.get("LLM_ENABLED", "true").lower() not in ("0", "false", "no", "off")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "Groq")
LLM_KEYLESS_BASE_URL = os.environ.get("LLM_KEYLESS_BASE_URL", "https://text.pollinations.ai/openai")
LLM_KEYLESS_MODEL = os.environ.get("LLM_KEYLESS_MODEL", "openai")          # = gpt-oss-20b
LLM_KEYLESS_LABEL = os.environ.get("LLM_KEYLESS_LABEL", "gpt-oss-20b")
LLM_KEYLESS_PROVIDER = os.environ.get("LLM_KEYLESS_PROVIDER", "Pollinations (free, no key)")

# ---------------------------------------------------------------------------
# Local model (preparation/local_llm.py)
# ---------------------------------------------------------------------------
# The other half of the AI work: weights held in this process by the
# transformers library instead of a request to somebody's API. It screens a
# written practice answer before the hosted model is asked to write feedback
# on it.
#
# transformers downloads the weights into the Hugging Face cache on first use,
# so a fresh checkout needs no setup beyond `pip install -r requirements.txt`.
# The first screened answer pays for the download, roughly 3 GB for the
# default model; every one after that is local and free.
#
# The model is the lab's budget recommendation from
# llm-test/ai_prototype.ipynb, where it returned valid JSON on every matrix
# task at about 0.7 seconds per reply. Override with LOCAL_LLM_MODEL to try
# another one from the lab without touching code.
#
# Off by default in production: torch and the weights are several GB, far
# beyond PythonAnywhere's 512 MB quota. With it off the hosted coach still
# answers and nothing on the site changes except the screening stage.
LOCAL_LLM_ENABLED = os.environ.get("LOCAL_LLM_ENABLED", "true").lower() not in ("0", "false", "no", "off")
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
# Empty lets transformers choose. Set to "cuda", "mps" or "cpu" to pin it.
LOCAL_LLM_DEVICE = os.environ.get("LOCAL_LLM_DEVICE", "")

# Running the tests never loads real weights. Without this, `manage.py test`
# on a machine that has transformers installed would download several GB the
# first time somebody submitted a written answer in a test, which is a
# surprising thing for a test run to do and slow enough to look like a hang.
# The local-model tests switch it back on themselves and supply a fake
# pipeline, so the guard costs no coverage.
if "test" in sys.argv:
    LOCAL_LLM_ENABLED = False

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
