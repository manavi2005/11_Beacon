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

## Before you pull: the committed database

`db.sqlite3` is committed to the repository (the assignment requires it).
The copy on PythonAnywhere is the **live** database, though, and it changes
every time someone signs up. If a commit you pull also changes
`db.sqlite3`, `git pull` will refuse:

```
error: Your local changes to the following files would be overwritten by merge:
        db.sqlite3
```

The safe way through is to set the live database aside, pull, then put it
back, so the server always keeps its own data:

```bash
cp db.sqlite3 ~/db-live-$(date +%F).sqlite3      # 1. save the live database
git checkout -- db.sqlite3                       # 2. let git update the file
git pull origin main                             # 3. pull
cp ~/db-live-$(date +%F).sqlite3 db.sqlite3      # 4. put the live database back
```

Then carry on with `migrate` as usual. Skipping step 4 would replace every
production account with the repository's copy.

None of the commits in this release change `db.sqlite3`, so a plain
`git pull` should just work. New fields reach the live database through
`migrate`, not through the file.

## Why each step matters this time

- **`collectstatic` is required.** This release adds `static/js/beacon.js`
  and changes `beacon.css`.
  Production uses `ManifestStaticFilesStorage`, which raises an error, and
  so returns a 500 on every page, when a template asks for a static file
  that was never collected.
- **`pip install` is required:** this release adds `pypdf` (the resume
  parser). It is pure Python, so it installs on PythonAnywhere with no
  build tools.
- **`migrate` is required:** migration `0003` adds
  `CandidateProfile.target_roles` and `.interests`, and `0004` adds the
  `TaskAttempt` table. Without them, onboarding and the task workspace fail
  with "no such column" / "no such table".

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
3. Click **Use the sample resume**. It reports "found 5 skills" and ticks
   *Working with data*. **Next**: Data Analyst is pre-selected. Leave
   **No interview yet**. **Next**: SQL, Python and Git sliders are tagged
   *from resume*.
4. **Light my beacon**. `/me/` opens with "Your beacon is lit", gaps, and weeks.
5. Open a week-1 task. For SQL or Python it is a quiz, otherwise a writing
   box. Submit it: you see the score, feedback, and "Skill 40 → 54".
   *My plan* then shows the task done (✓ score) and a Recent activity row.
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

## The AI coach in production

**It works with no setup.** With no key in `.env`, the coach uses
Pollinations' free anonymous tier, which serves OpenAI's open-weight
`gpt-oss-20b` with no account at all. `text.pollinations.ai` is on
PythonAnywhere's allowlist. On **My plan** the badge should read
*AI · gpt-oss-20b via Pollinations (free, no key)*.

That tier is slow (about 10-15 s an answer) and rate-limited (about one
request every few seconds per server). Beacon caches advice for 6 hours,
retries once when busy, and otherwise falls back to its rule-based coach,
so the page never breaks. It is fine for a demo, not for many users.

**Faster and more reliable, still free: add a Groq key.**

1. Create a free key at <https://console.groq.com/keys>.
2. Add it to `.env` on PythonAnywhere: `LLM_API_KEY=gsk_...`
3. **Web tab > Reload.** The badge changes to
   *AI · llama-3.3-70b-versatile via Groq* (Meta's open-weight Llama 3.3 70B).

**Why that matters on PythonAnywhere's free plan:** it runs a single web
worker. While one person waits on a slow model, everyone else's page loads
wait too. Groq answers in a second or two, which keeps that wait short.

**Scaling to many users later:** change `LLM_BASE_URL`, `LLM_MODEL` and
`LLM_API_KEY` to a paid or self-hosted endpoint (Hugging Face, Together,
OpenRouter, or your own vLLM/Ollama server). `.env.example` lists ready
values. No code changes are needed. At that point, also move model calls
off the request thread (a task queue) and add more web workers.

To switch the AI off entirely: `LLM_ENABLED=false`.

## Google OAuth in production

Nothing changes in this release. For reference, the Google client must keep
both redirect URIs, `.env` on the server must hold `GOOGLE_OAUTH_CLIENT_ID`
and `GOOGLE_OAUTH_CLIENT_SECRET`, and the Sites entry (Django admin > Sites)
must use the production domain:

```
http://127.0.0.1:8000/accounts/google/login/callback/
https://simonhwang1998.pythonanywhere.com/accounts/google/login/callback/
```
