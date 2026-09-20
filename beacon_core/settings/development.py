"""Development settings - local machines only.

Run with:  python manage.py runserver
(manage.py already defaults to this module, so no --settings flag is needed.)
"""

from .base import *  # noqa: F401,F403

# DEBUG = True shows full tracebacks, file paths and settings on any error.
# Useful locally, dangerous in production - see production.py.
DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]  # testserver = Django test client

# Print emails to the terminal instead of sending them.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
