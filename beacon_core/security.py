"""Abuse protection shared by every app: rate limits and security headers.

Threats this covers, for a site anyone can sign up to:

  credential stuffing / brute force   failed logins are limited per account
                                      and per address; a locked account says
                                      so without confirming the password
  signup floods                       new accounts are limited per address,
                                      so bots can't mint accounts to get
                                      fresh AI allowances
  AI bill / resource exhaustion       AI actions are capped per person, per
                                      address and site-wide (studio.views)
  XSS                                 a Content-Security-Policy allows
                                      scripts only from this site, plus inline
                                      blocks carrying a per-request nonce
  clickjacking, sniffing, leaking     frame-ancestors 'none', nosniff,
                                      same-origin referrers, no camera or
                                      location access

The counters live in the cache. Production uses the database cache so all
web workers share one count (per-process memory would let an attacker
multiply every limit by the number of workers).
"""

import logging
import secrets
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render
from django.urls import reverse

log = logging.getLogger("beacon.security")


# --------------------------------------------------------------------------
# Who is asking
# --------------------------------------------------------------------------
def client_ip(request):
    """The visitor's address.

    Behind PythonAnywhere's proxy REMOTE_ADDR is the proxy, and the real
    address is in X-Real-IP, which the proxy sets itself (anything the
    visitor sent is overwritten). X-Forwarded-For is only trusted for its
    last hop, the one the proxy appended. Without TRUST_PROXY_HEADERS no
    header is believed, so nobody can dodge a limit by inventing one.
    """
    meta = request.META
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        real = meta.get("HTTP_X_REAL_IP", "").strip()
        if real:
            return real[:64]
        forwarded = [p.strip() for p in meta.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if forwarded:
            return forwarded[-1][:64]
    return meta.get("REMOTE_ADDR", "unknown")[:64]


# --------------------------------------------------------------------------
# Fixed-window counters
# --------------------------------------------------------------------------
def _key(bucket, ident, window):
    return f"rl:{bucket}:{ident}:{int(time.time() // window)}"


def hit(bucket, ident, window):
    """Count one event; return the count in the current window."""
    key = _key(bucket, ident, window)
    if cache.add(key, 1, window + 5):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, window + 5)
        return 1


def count(bucket, ident, window):
    return cache.get(_key(bucket, ident, window), 0)


def clear(bucket, ident, window):
    cache.delete(_key(bucket, ident, window))


def allow(bucket, ident, limit, window):
    """Count one event and say whether it is within the limit."""
    return hit(bucket, ident, window) <= limit


# --------------------------------------------------------------------------
# Login and signup limits
# --------------------------------------------------------------------------
LOGIN_WINDOW = 15 * 60
LOGIN_FAILS_PER_ACCOUNT = 8      # then that account waits out the window
LOGIN_FAILS_PER_IP = 30          # many accounts from one address
SIGNUP_WINDOW = 60 * 60
SIGNUPS_PER_IP = 8


def login_locked(username, ip):
    return (count("login-user", username.lower()[:150], LOGIN_WINDOW) >= LOGIN_FAILS_PER_ACCOUNT
            or count("login-ip", ip, LOGIN_WINDOW) >= LOGIN_FAILS_PER_IP)


def unlock_login(username):
    """Staff support: let someone try again now."""
    clear("login-user", username.lower()[:150], LOGIN_WINDOW)


def too_many(request, message, status=429):
    response = render(request, "429.html", {"message": message}, status=status)
    response["Retry-After"] = "900"
    return response


class AbuseGuardMiddleware:
    """Limits on the sign-in, sign-up and admin login forms.

    Only failures count toward a login lock: a correct password is never
    blocked by someone else's failed guesses unless the whole address is
    hammering. The check runs before the password is even looked at, so a
    locked account gives an attacker nothing to learn.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._paths = None

    def paths(self):
        if self._paths is None:
            self._paths = {
                "login": {reverse("preparation:login"), reverse("admin:login")},
                "signup": {reverse("preparation:signup"), "/accounts/signup/"},
            }
        return self._paths

    def __call__(self, request):
        if request.method != "POST" or not getattr(settings, "RATE_LIMITS_ENABLED", True):
            return self.get_response(request)
        paths = self.paths()
        ip = client_ip(request)
        if request.path in paths["login"]:
            username = str(request.POST.get("username", ""))
            if login_locked(username, ip):
                log.warning("login locked: user=%r ip=%s", username[:40], ip)
                return too_many(request, "Too many sign-in attempts. For your safety, "
                                         "please wait 15 minutes and try again.")
            response = self.get_response(request)
            # A successful login redirects; a failed one re-renders the form.
            if response.status_code == 200:
                hit("login-user", username.lower()[:150], LOGIN_WINDOW)
                hit("login-ip", ip, LOGIN_WINDOW)
            return response
        if request.path in paths["signup"]:
            if not allow("signup-ip", ip, SIGNUPS_PER_IP, SIGNUP_WINDOW):
                log.warning("signup limit: ip=%s", ip)
                return too_many(request, "Lots of accounts have been made from this "
                                         "network recently. Please try again in an hour.")
        return self.get_response(request)


# --------------------------------------------------------------------------
# Security headers
# --------------------------------------------------------------------------
def csp_nonce(request):
    """Template context: {{ csp_nonce }} for the few inline <script> blocks."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}


def relaxed_csp(*extra_script_sources, allow_eval=False):
    """Decorator for one view that needs more than the default policy,
    such as the Vega-Lite page (CDN scripts; Vega compiles expressions)."""
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            request.csp_extra = {"script": list(extra_script_sources), "eval": allow_eval}
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        extra = getattr(request, "csp_extra", {"script": [], "eval": False})
        scripts = ["'self'", f"'nonce-{request.csp_nonce}'", *extra["script"]]
        if extra["eval"]:
            scripts.append("'unsafe-eval'")
        policy = "; ".join([
            "default-src 'self'",
            "script-src " + " ".join(scripts),
            # Inline style attributes are used for widths and animation
            # delays; styles can't run code, so allowing them is low risk.
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' data: blob:",
            "media-src 'self' blob:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "object-src 'none'",
            # Google sign-in redirects the form post to Google.
            "form-action 'self' https://accounts.google.com",
        ])
        header = ("Content-Security-Policy-Report-Only"
                  if getattr(settings, "CSP_REPORT_ONLY", False) else "Content-Security-Policy")
        response.headers.setdefault(header, policy)
        response.headers.setdefault("Permissions-Policy",
                                    "camera=(), geolocation=(), payment=(), usb=(), microphone=(self)")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response
