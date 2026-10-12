"""Template context shared by every page.

Assignment 5, Part 2.
"""

from django.conf import settings


def google_oauth(request):
    """Whether Google login is usable on this machine.

    The templates need to know, because the credentials are read from the
    environment and are legitimately absent in development, in CI, and on a
    teammate's machine who has not set them. Rendering the button there would
    send the user to Google and bring them back to an error page.

    Checking both halves rather than one: a client id with no secret fails at
    the token exchange, which is a far more confusing failure than the button
    simply not being there.
    """
    provider = settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
    app = provider.get("APP", {})
    return {
        "google_oauth_configured": bool(app.get("client_id") and app.get("secret")),
    }
