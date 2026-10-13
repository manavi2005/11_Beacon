# Assignment 5: Authentication, a public API, and its uses

Production site: <https://simonhwang1998.pythonanywhere.com/>
Public API: <https://simonhwang1998.pythonanywhere.com/api/skills/summary/>

## Part 1: Internal authentication

Custom login, signup, and POST-only logout live in `preparation/views.py`, with
templates in `templates/registration/`. `LOGIN_URL`, `LOGIN_REDIRECT_URL` and
`LOGOUT_REDIRECT_URL` are set in `beacon_core/settings/base.py`. Every page
except login and signup requires a login, and `base.html` only shows the
protected links once you are signed in. Tests: `AuthenticationTests`.

## Part 2: Google OAuth

django-allauth with the Google provider. The credentials come from
`GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` in `.env`, never from
the database. The same Google client has both redirect URIs registered:

```
http://127.0.0.1:8000/accounts/google/login/callback/
https://simonhwang1998.pythonanywhere.com/accounts/google/login/callback/
```

"Continue with Google" appears on both the login and signup pages
(`templates/registration/_google_button.html`).

## Part 3: One public API, everything else protected

| Endpoint | Access | Why |
|---|---|---|
| `/api/skills/summary/` | **Public** | Only aggregates (counts and averages per skill), so nobody can be identified |
| `/api/assessments/` | Protected, 401 JSON | One row per person per skill |
| `/api/market-demand/?q=` | Protected, 401 JSON | Calls an external API on our behalf |
| `/api/whoami/` | Protected, 401 JSON | Describes the signed-in account |
| `/vega-lite/chart<N>.json` | Protected, 401 JSON | Internal chart specs |
| `/api/skills/` | Protected, redirects to login | Browser-facing catalog API |
| `/reports/candidates.csv` and `.json` | Protected, redirects to login | Per-candidate exports |

Protected JSON APIs answer `401` with a JSON body rather than redirecting to
the HTML login page, because a script or chart cannot do anything with a
redirect to markup. The public API sends `Access-Control-Allow-Origin: *`
so the online Vega-Lite editor can read it. The protected ones do not.
Tests: `PublicVsProtectedApiTests`.

The public API also answers `?format=csv` with the same rows, for
spreadsheets (see use 2 below).

### 3.2 and 3.3: Vega-Lite

[`group-11-vega-lite-API-demo.txt`](group-11-vega-lite-API-demo.txt) is the
full spec. Its data is `{"url": "https://simonhwang1998.pythonanywhere.com/api/skills/summary/"}`
with no inline values. It draws a grouped bar chart of current proficiency
against the required level for every assessed skill, sorted by the widest gap.
The spec's field names (`skill`, `category`, `learners`, `avg_proficiency`,
`avg_required`, `avg_gap`) match the API exactly.

Screenshot from the Vega-Lite editor:
[`a5-part3-vega-lite-editor.png`](../screenshots/a5-part3-vega-lite-editor.png).

### 3.4: Three alternative uses

All three read the same public URL, with no login and no copied data.

**Use 1: a Python report script.**
[`alt_uses/use1_python_report.py`](alt_uses/use1_python_report.py) turns the
12 skill rows into a category-level report, weighted by how many candidates
were assessed, and names the one skill each category should work on first.
This is what a career-centre advisor planning next term's workshops would
want: "Technical is the weakest area, start with SQL", not a table of skills.
Output: [`alt_uses/use1_output.txt`](alt_uses/use1_output.txt).

**Use 2: importing into Google Sheets or Excel.**
`=IMPORTDATA("https://simonhwang1998.pythonanywhere.com/api/skills/summary/?format=csv")`
puts the live data in a sheet, and a `QUERY` formula averages the gap per
category for a chart. The sheet refreshes from the API on its own, so nobody
has to re-export anything.
[`alt_uses/use2_spreadsheet_import.py`](alt_uses/use2_spreadsheet_import.py)
is the test code. It fetches the CSV exactly as `IMPORTDATA` does, checks it
matches the JSON, and runs the same per-category calculation as the formula.

**Use 3: statistical analysis in a notebook.**
[`alt_uses/use3_notebook_analysis.ipynb`](alt_uses/use3_notebook_analysis.ipynb)
loads the API with one `pd.read_json(url)` call. It runs descriptive
statistics and a correlation, then asks a question the site itself never
answers: are the preparation tasks aimed at the widest gaps? It flags three
skills with an above-median gap but below-median task coverage: Git, data
structures, and failure questions.
Chart: [`a5-part3-use3-notebook-chart.png`](../screenshots/a5-part3-use3-notebook-chart.png).
An HTML copy with all outputs is next to the notebook.

## The start-from-scratch journey (for the demo)

A brand-new user (username signup, or a first Google sign-in) goes straight
to **`/welcome/`**. They pick a target role and interview date, then rate
themselves 0-100 on each skill. Each slider shows what that role requires,
and a ring projects their readiness live. Submitting creates their
`CandidateProfile`, one `SkillAssessment` per skill, and a dated
`PreparationPlan`. The plan's tasks come from the widest gaps first, spread
across the weeks (rule-based, `preparation/onboarding.py`; this is the seam
the AI coach will replace). **`/me/`** then shows their readiness, gaps and
week-by-week plan. Tasks can be ticked off in place, and only by their owner.
Tests: `FromScratchJourneyTests`.

**Flexible goals.** No interview booked? Choose a 4, 6, 8 or 12-week
open-ended plan instead of a date. Preparing for several roles? Pick up to
three, and each skill is held to the highest bar among them. No idea yet?
Pick the interests that fit (building software, data, products, people,
markets), and Beacon suggests matching roles. Or choose *General interview
readiness*, which weights storytelling and communication over role-specific
skills.

**Resume and LinkedIn import.** Step 1 can read a resume PDF, a `.txt`, or
pasted text (`preparation/resume.py`). It finds evidence for each catalog
skill (quoting where), ticks matching interests, suggests roles, and starts
those sliders at a modest rating that the user then confirms. LinkedIn has no
public profile API, and scraping it breaks its terms, so the supported route
is LinkedIn's own *More > Save to PDF*, which the same parser reads (and
recognises as a LinkedIn export). The upload is read in memory and never
stored. A sample resume is built in for demos (*Use the sample resume*).
Tests: `FlexibleGoalsTests`, `ResumeImportTests`.

On the login page the lighthouse beam follows the mouse. The video script
(`video/script.md`) is built around this journey.

## Submission checklist

1. Public API production URL: `https://simonhwang1998.pythonanywhere.com/api/skills/summary/`
2. GitHub URL: `https://github.com/manavi2005/11_Beacon`
3. Vega-Lite script: `docs/a5/group-11-vega-lite-API-demo.txt`
4. Vega-Lite editor screenshot: `docs/screenshots/a5-part3-vega-lite-editor.png`
5. Demo video: see [`video/`](video/)
