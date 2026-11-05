# Security and abuse protection

What Beacon defends against if it's public and busy, how, and where the code
is. Read with [deployment/DEPLOY.md](deployment/DEPLOY.md).

## Threats and defences

| Threat | Defence | Code |
|---|---|---|
| Password guessing / credential stuffing | 8 failed logins per account or 30 per address in 15 minutes, then a 429. Successful logins never count. Covers the admin login too. | `beacon_core/security.py` (`AbuseGuardMiddleware`) |
| Bot signups to farm free AI | 8 signups per address per hour | same |
| Running up the AI bill | AI actions capped per person (150/h), per address (400/h) and site-wide (6000/h, then a polite "busy") | `studio/views.py` (`ai_budget`) |
| Provider outage hanging every request | Circuit breaker pauses AI for 5 minutes after the provider fails; the offline coach takes over | `studio/ai.py` |
| Scraping the public API | 60 requests per minute per address; results cached and keyed on a data fingerprint | `preparation/views.py` (`public_api`) |
| Seeing someone else's data | Every per-person query is scoped to the signed-in user (`preparation/visibility.py`, `get_object_or_404(..., candidate__user=request.user)`); someone else's record is a 404 | tests in `studio/tests.py`, `preparation/tests.py` |
| XSS (including prompt-injected AI output) | Templates auto-escape; JS escapes before `innerHTML`; coach text is escaped then formatted; a Content-Security-Policy allows only this site's scripts plus nonced inline blocks, so injected markup can't run | `beacon_core/security.py` (`SecurityHeadersMiddleware`) |
| CSRF | Django's CSRF middleware on every POST; the token comes from the template, and the cookie is HttpOnly in production | settings |
| Clickjacking | `frame-ancestors 'none'` and `X-Frame-Options: DENY` | same |
| Session theft / downgrade | Secure, HttpOnly cookies; HSTS for a year; https enforced by the host | `beacon_core/settings/production.py` |
| Forged sessions from a leaked key | Production refuses to start with a missing, short or default `DJANGO_SECRET_KEY` | same |
| Open redirects | `next` targets checked with `url_has_allowed_host_and_scheme` | login and delete views |
| Oversized requests | 3 MB request bodies, 5 MB resumes, 15 MB recordings, text truncated before it reaches the AI | settings, `preparation/resume.py`, `studio/views.py` |
| Admin login hunting | The admin path is set by `DJANGO_ADMIN_URL` | `beacon_core/urls.py` |
| Spoofed client addresses | Proxy headers are believed only in production, where the proxy sets them itself | `security.client_ip` |
| Staff overreach | Console changes go through one function that checks permission and writes an append-only audit log; only superusers can grant staff | `support/actions.py` |

Every limit trip is logged to the `beacon.security` logger, which goes to the
server error log in production.

## Why the counters live in the database cache

PythonAnywhere runs several web workers. With per-process memory, each worker
keeps its own count, so every limit is silently multiplied by the number of
workers. Production uses Django's database cache (`createcachetable` runs in
the deploy script), which all workers share and which needs no extra service.
At much larger scale, switch `CACHES` to Redis; nothing else changes.

## Scaling notes

- **SQLite** is fine for a class deployment and early users. It serialises
  writes, so production waits up to 20 s for a lock instead of failing. Past
  a few hundred concurrent users, move to Postgres: set `DATABASES` from an
  environment variable and run `migrate`.
- **AI cost** is bounded by the site-wide cap. Raise
  `AI_ACTIONS_SITE_PER_HOUR` in `.env` as usage grows.
- **Static files** are content-hashed and served by the host, not Django.

## Not covered (yet)

- No CAPTCHA on signup. The per-address limit stops simple floods. A
  distributed botnet would need Cloudflare Turnstile or similar.
- No email verification, because accounts have no email-based powers. Add
  it before allowing password reset by email.
- No 2FA for staff. Use Google sign-in for staff accounts, so Google's 2FA
  applies.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository instead of a
public issue.
