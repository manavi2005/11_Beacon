# Demo video script: Beacon, Phase 1 (target 4:40, hard limit 5:00)

Record on the **production** site, <https://simonhwang1998.pythonanywhere.com/>.
Use a fresh incognito window so you start signed out. Record at 1920×1080
(QuickTime: File > New Screen Recording). Close other tabs and turn on Do
Not Disturb first.

**Before recording, check:**
- The site has been redeployed with the latest `main` (see `../DEPLOY.md`),
  and `/market/?q=analyst` loads postings.
- You can log in with Google on production.
- The emails in `opening-slide.html` are filled in.
- `docs/a5/group-11-vega-lite-API-demo.txt` is ready to paste.
- A terminal is open in `docs/a5/alt_uses/`.

Suggested split: **A** opening and auth, **B** product walkthrough,
**C** APIs and data. Each narrator only needs their own section.

---

## 0:00 to 0:30 · Opening slide (narrator A)

Show `opening-slide.html` full screen.

> "Today is **[month day], 2026**. We are Team Career Coaches, Group 11:
> Manavi Chaudhry, Chu-Yun Hwang, and Meet Kailash Mali. This is the first
> prototype of our startup product, **Beacon**, that we are developing in
> INFO 490 MG Fall 2026."

## 0:30 to 0:55 · What Beacon is (narrator A, still on the slide)

> "Students preparing for interviews are told everything they could
> practise, but not what to practise next. Beacon diagnoses each skill
> against what the student's target role actually requires. It turns the
> widest gaps into a week-by-week preparation plan, and tracks readiness
> until interview day. This phase is the full non-AI foundation: the data
> model, authentication, and APIs that the AI coach will build on."

## 0:55 to 1:45 · Authentication (narrator A)

| Do | Say |
|---|---|
| Open the production URL. You land on `/accounts/login/`. | "Everything is behind a login. Opening the site signed-out sends you to our login page." |
| Point at the nav: only *Log In* and *Sign Up*. | "Before login, the navigation hides every protected page." |
| Click **Sign Up**, show the form, then go back. | "We have our own signup and login pages, built on Django's auth forms with the password rules applied." |
| Click **Continue with Google**, pick the account. | "And Google sign-in through django-allauth, working here on our deployed PythonAnywhere domain, not just locally." |
| Land on the dashboard and point at the full nav. | "Once signed in, the full navigation appears." |

## 1:45 to 2:55 · The product (narrator B)

| Do | Say |
|---|---|
| Dashboard: let the numbers and rings animate. | "The dashboard shows the cohort at a glance. Each ring is a candidate's readiness against their target role, and the bars on the right are the widest skill gaps across everyone." |
| Click a low ring, e.g. **Bharat Patel**. | "Clicking a candidate shows their goal, every skill score, and their biggest gaps." |
| Press **⌘K** (or Ctrl K), type `sql`, Enter. | "Anything in Beacon is one shortcut away: pages, candidates, skills and plans." |
| On the skill page, show the assessments. | "Each skill page shows who has been assessed on it and which tasks target it." |
| Open **Job market**, search `analyst`. | "Beacon pulls live remote job postings from a public jobs API and counts how often employers ask for each skill. It ranks skills by employer demand times our candidates' gap, so effort goes where it pays off." |

## 2:55 to 4:25 · APIs and data (narrator C)

| Do | Say |
|---|---|
| Open `/api/skills/summary/` in the signed-in window. | "Beacon exposes exactly one public API: this skill summary. It is aggregates only, counts and averages per skill, so no individual can be identified." |
| In the **incognito** window, open `/api/assessments/`. | "Every other API is protected. Signed out, it answers 401 with a JSON error instead of data." |
| In incognito, open `/api/skills/summary/`. | "The public one still answers with no login at all." |
| Vega-Lite editor: paste the spec and point at `data.url`. | "Here it is in the Vega-Lite editor. The chart reads our production URL directly, with no copied data, comparing current proficiency against what roles require." |
| Terminal: `python use1_python_report.py` | "Three other ways to use the same API. First, a Python script that rolls it up by category: Technical is the weakest area, and SQL is the first thing to fix." |
| Google Sheet with the `IMPORTDATA` formula and chart. | "Second, Google Sheets imports it live with one formula, through a CSV form of the same endpoint." |
| Notebook chart. | "Third, a notebook analysis asks whether our coaching is aimed at the right skills. It found three skills with wide gaps but few preparation tasks, which is our next content priority." |

## 4:25 to 4:45 · Close (narrator C)

| Do | Say |
|---|---|
| Click **Log Out**. You return to the login page. | "Logging out returns you to the login page and hides everything again. Next phase, the AI coach generates these plans automatically. Thank you." |

---

**Timing check:** about 4:45. If you run long, cut the Sign Up detour
(about 10 s) and the skill page (about 10 s) first.
