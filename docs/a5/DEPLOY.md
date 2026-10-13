# Updating the live site (PythonAnywhere)

The site runs on the `SimonHwang1998` PythonAnywhere account at <https://simonhwang1998.pythonanywhere.com/>.
After this branch is merged into `main`, run the steps below in a
PythonAnywhere **Bash console**. Replace `<venv>` with the virtualenv name
on the Web tab, and `~/11_Beacon` with the clone path if it differs.

```bash
cd ~/11_Beacon
git pull origin main
workon <venv>
pip install -r requirements.txt
python manage.py migrate --settings=beacon_core.settings.production
python manage.py collectstatic --noinput --settings=beacon_core.settings.production
```

Then **Web tab > Reload**.

## Why each step matters this time

- **`collectstatic` is required.** This release adds `static/js/beacon.js`
  and changes `beacon.css`.
  Production uses `ManifestStaticFilesStorage`, which raises an error, and
  so returns a 500 on every page, when a template asks for a static file
  that was never collected.
- **`pip install`:** no new packages in this release, but it is cheap
  insurance if the virtualenv has drifted from `requirements.txt`.
- **`migrate`:** no new migrations. Onboarding writes to the existing
  models. It is safe to run, and it confirms the database is current.

## Check it worked

| URL | Expect |
|---|---|
| `/` | Redirects to the new lighthouse login page |
| `/api/skills/summary/` | JSON, no login needed |
| `/api/skills/summary/?format=csv` | CSV, no login needed |
| `/api/assessments/` (signed out) | `401` with a JSON error |
| `/market/?q=analyst` (signed in) | Job postings, credited to **Remotive** |
| Dashboard, press ⌘K | The command palette opens |
| Login page, move the mouse over the lighthouse | The beam follows the pointer |

## Rehearse the from-scratch demo on production

Do this once after deploying, with a throwaway username such as
`rehearsal1`. Every step writes to the production database, which is the
point: it proves the journey works there, not just locally.

1. Signed out, open the site. It redirects to the lighthouse login page.
2. **Sign Up** with the new username. You land on `/welcome/`.
3. Pick a role and date, then **Next**, then drag a few sliders. The ring updates.
4. **Light my beacon**. `/me/` opens with "Your beacon is lit", gaps, and weeks.
5. Tick a task. The progress bar moves without a reload.
6. **Dashboard** now shows the new candidate's ring; ⌘K finds them by name.

If step 4 errors, check that `collectstatic` ran (the page needs
`beacon.js` and the new CSS) and that `git pull` brought in
`preparation/onboarding.py`.

Rehearsal accounts appear in the cohort like any other candidate. Delete
them afterwards in **Django admin > Users**; deleting the user cascades to
their profile, scores and plan.

## Known limitation: PythonAnywhere free tier and external APIs

Free accounts can only make outbound requests to hosts on
[PythonAnywhere's allowlist](https://www.pythonanywhere.com/whitelist/).
Jobicy is not on it, so in production the job-market feature falls back to
Remotive, which is. Locally both work, and Jobicy is tried first. The page
and the JSON both say which source answered.

## Google OAuth in production

Nothing changes in this release. For reference, the Google client must keep
both redirect URIs, `.env` on the server must hold `GOOGLE_OAUTH_CLIENT_ID`
and `GOOGLE_OAUTH_CLIENT_SECRET`, and the Sites entry (Django admin > Sites)
must use the production domain:

```
http://127.0.0.1:8000/accounts/google/login/callback/
https://simonhwang1998.pythonanywhere.com/accounts/google/login/callback/
```
