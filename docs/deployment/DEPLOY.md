# Deploying Beacon (PythonAnywhere)

Live at <https://manavi2005.pythonanywhere.com/> (and the team mirror at
<https://simonhwang1998.pythonanywhere.com/>). The steps are the same for both.

## Every update

In a PythonAnywhere **Bash console**:

```bash
cd ~/11_Beacon
workon <venv>                       # the virtualenv named on the Web tab
bash scripts/deploy_pythonanywhere.sh
```

The script backs up the live database, pulls `main` without touching that
database, installs `requirements-production.txt`, migrates, creates the
shared cache table, collects static files, runs Django's deploy checks and
lists any missing settings. Then press
**Web tab > Reload** and open `/healthz/`:

```json
{"ok": true, "database": true, "ai": "on"}
```

`"ai": "off"` means no AI key is configured. `"paused"` means the provider
was unreachable in the last five minutes; see the allowlist note below.

## One-time setup

### 1. `.env` in the project folder

```
DJANGO_SECRET_KEY=<long random string>
LUMEN_API_KEY=<from your Lumen profile>
GOOGLE_OAUTH_CLIENT_ID=<from Google Cloud console>
GOOGLE_OAUTH_CLIENT_SECRET=<from Google Cloud console>
SITE_URL=https://manavi2005.pythonanywhere.com
# optional
DJANGO_ADMIN_URL=<something-hard-to-guess>/   # default admin/
AI_ACTIONS_SITE_PER_HOUR=6000                  # whole-site AI cap
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

`DJANGO_SECRET_KEY` is required: production refuses to start without a
long random one, because the development default is public and would let
anyone forge a session. Generate one with:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

### 2. Web tab

- **Source code / working directory:** `/home/<user>/11_Beacon`
- **WSGI file:** loads `beacon_core.wsgi`, which uses the production settings
- **Static files:** URL `/static/` → directory `/home/<user>/11_Beacon/staticfiles`
- **Force HTTPS:** on

### 3. Google sign-in

In Google Cloud console > APIs & Services > Credentials > the OAuth client,
add to **Authorized redirect URIs**, exactly:

```
https://manavi2005.pythonanywhere.com/accounts/google/login/callback/
https://simonhwang1998.pythonanywhere.com/accounts/google/login/callback/
http://127.0.0.1:8000/accounts/google/login/callback/
http://localhost:8000/accounts/google/login/callback/
```

Then, once, set the Site domain (allauth builds links from it):

```bash
python manage.py set_site_domain manavi2005.pythonanywhere.com --settings=beacon_core.settings.production
```

`Error 400: redirect_uri_mismatch` always means the address Beacon sent is
not in that list. Production sends `https://` because `production.py`
trusts PythonAnywhere's `X-Forwarded-Proto` header.

### 4. Daily reminders (Tasks tab)

Add a daily scheduled task:

```bash
cd ~/11_Beacon && /home/<user>/.virtualenvs/<venv>/bin/python manage.py send_reminders --settings=beacon_core.settings.production
```

Reminders are opt-in per user, sent at most once a day, and skipped on days
the person already practised.

### 5. Support console

Staff accounts get the support console at `/staff/`: usage and AI health,
people search, a per-person diagnosis with one-click fixes, problem reports
from the You page, server errors and an audit log. Make yourself a
superuser once, in a Bash console:

```bash
python manage.py createsuperuser --settings=beacon_core.settings.production
```

or promote the account you already sign in with:

```bash
python manage.py shell --settings=beacon_core.settings.production -c "from django.contrib.auth.models import User; User.objects.filter(username='YOUR_USERNAME').update(is_staff=True, is_superuser=True)"
```

Superusers can then make other people staff from the console. Security
details are in [../security.md](../security.md).

## Free accounts and outbound internet

PythonAnywhere's free tier can only reach sites on its
[allowlist](https://www.pythonanywhere.com/whitelist/). If
`lumen.computes.illinois.edu` (or `api.adzuna.com`) is not on it, Beacon
still works, falling back to its offline coach after the first failed call
(`/healthz/` shows `"ai": "paused"`). To get AI in production, either ask
PythonAnywhere to add the host (they accept requests for public APIs) or
use a paid account, which has unrestricted outbound access.

## If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Every page 500s after an update | static files not collected | rerun the script; it runs `collectstatic` |
| "no such table: studio_..." | migrations not applied | rerun the script; it runs `migrate` |
| Pages unstyled | static mapping missing | Web tab: `/static/` → `.../staticfiles` |
| Google: `redirect_uri_mismatch` | URI not registered | add it exactly as listed above |
| `"ai": "paused"` on `/healthz/` | host not on the allowlist, or a bad key | see the section above |
| Lost signups after a pull | live DB overwritten | restore the newest `~/db-live-*.sqlite3` backup the script made |
| `ImproperlyConfigured: Set DJANGO_SECRET_KEY` | key missing or weak | generate one (above), put it in `.env`, Reload |
| "no such table: beacon_cache" | cache table missing | `python manage.py createcachetable --settings=beacon_core.settings.production` |
| Someone locked out of sign-in | 8 wrong passwords in 15 min | wait, or Support console > their page > Unlock sign-in |
