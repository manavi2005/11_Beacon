# Demo video script: Beacon, Phase 1 (target 4:45, hard limit 5:00)

The video follows **one brand-new user from scratch**: a student who has
never used Beacon signs up, gets diagnosed, and gets a plan. Then it shows
the coach's view and the APIs underneath.

Record on the **production** site, <https://simonhwang1998.pythonanywhere.com/>,
in a fresh incognito window so you start signed out. Record at 1920×1080
(QuickTime: File > New Screen Recording). Close other tabs and turn on Do
Not Disturb.

## Before you record

- [ ] Production is updated to the latest `main` (`../DEPLOY.md`), and
      `/welcome/` loads when signed in.
- [ ] **Pick an unused username for the demo**, e.g. `maya_demo1`. A
      username can only be signed up once; for a retake, use `maya_demo2`.
- [ ] If you will show *Continue with Google* as the new user, use a Google
      account that has **never** signed in to the production site.
      Otherwise you land on your existing account, not onboarding. For a
      guaranteed fresh start, use the username signup form.
- [ ] Emails are filled in on `opening-slide.html`.
- [ ] The Vega-Lite spec is ready to paste, and a terminal is open in
      `docs/a5/alt_uses/`.
- [ ] Do one full rehearsal. Dragging the sliders to sensible values is
      what takes time.

**Suggested ratings (Data Analyst at Spotify)** give a clear plan with SQL
at the top: SQL 40, Python 55, STAR 35, data structures 45, system design
30, product sense 70, Git 70, whiteboard 60, resume 65, everything else 50.

Suggested split: **A** opening and sign-up, **B** onboarding and plan,
**C** coach view and APIs.

---

## 0:00 to 0:30 · Opening slide (narrator A)

`opening-slide.html` full screen.

> "Today is **[month day], 2026**. We are Team Career Coaches, Group 11:
> Manavi Chaudhry, Chu-Yun Hwang, and Meet Kailash Mali. This is the first
> prototype of our startup product, **Beacon**, that we are developing in
> INFO 490 MG Fall 2026."

## 0:30 to 0:50 · The idea (narrator A, still on the slide)

> "Students preparing for interviews are told everything they could
> practise, but not what to practise next. Beacon diagnoses each skill
> against what the student's target role requires, turns the widest gaps
> into a week-by-week plan, and tracks readiness until interview day. Let us
> show it from the very beginning, as a brand-new student."

## 0:50 to 1:25 · Arriving and signing up (narrator A)

| Do | Say |
|---|---|
| Open the production URL. It redirects to the login page. | "Everything in Beacon needs an account, so a new visitor lands here." |
| **Move the mouse slowly across the lighthouse.** The beam follows it. | "That's our beacon. It follows you." (Pause one beat; it lands.) |
| Point at the nav: only *Log In* and *Sign Up*. | "Signed out, the navigation hides every private page." |
| Click **Sign Up**. Enter `maya_demo1` and a password. Submit. | "Sign-up is our own page, with Django's password rules. Google sign-in is right here too, through django-allauth, and it works on this deployed domain." |

## 1:25 to 2:20 · Onboarding: from blank account to diagnosis (narrator B)

| Do | Say |
|---|---|
| You land on **Welcome**. Choose *Data Analyst*, type *Spotify*, leave the date about 6 weeks out. | "A new account knows nothing about Maya yet, so Beacon asks two things. First, what she is aiming for and when." |
| **Next: rate your skills.** Drag SQL down to 40, and watch the ring. | "Then an honest self-rating per skill. The dark tick on each slider is what a Data Analyst role actually expects, and the ring projects her readiness live as she answers." |
| Set the rest quickly (ratings above), then click **Light my beacon**. | "Submit, and Beacon builds her profile, records every score, and generates a plan." |

## 2:20 to 3:05 · Her plan (narrator B)

| Do | Say |
|---|---|
| **My plan** loads with "Your beacon is lit". Pause on it. | "This page is now hers: target role, a countdown to her interview, and her readiness." |
| Point at **Your widest gaps**. | "Her widest gap is SQL, 45 points below the bar, so that's where the plan starts." |
| Scroll to **Week by week**. Read one task's *why* line. | "Every task says why it's there: she rated SQL at 40, and Data Analyst roles expect 85." |
| **Tick the two week-1 tasks.** The progress bar moves and week 1 turns green. | "As she practises, she ticks tasks off and her progress updates instantly." |

## 3:05 to 3:35 · The coach's view (narrator C)

| Do | Say |
|---|---|
| Click **Dashboard**. Let the rings animate. | "A career coach sees the whole cohort: readiness for every candidate, and the widest gaps across everyone." |
| Press **⌘K**, type `maya`, Enter. | "And can jump to any student, skill or page in one shortcut." |
| Open **Job market**, search `analyst`. | "Beacon also pulls live job postings from a public jobs API, and ranks skills by how often employers ask for them times how far our students are behind." |

## 3:35 to 4:30 · APIs and data (narrator C)

| Do | Say |
|---|---|
| Open `/api/skills/summary/`. | "Beacon has exactly one public API: this skill summary. It is aggregates only, so no individual can be identified." |
| In a signed-out window, open `/api/assessments/`. | "Every other API is protected. Signed out, it answers 401." |
| Vega-Lite editor with the spec pasted; point at `data.url`. | "The Vega-Lite editor reads our production URL directly, with no copied data." |
| Terminal: `python use1_python_report.py` | "The same API in a Python script, rolled up by category." |
| The Google Sheet with `IMPORTDATA`. | "Imported live into Google Sheets with one formula." |
| The notebook chart. | "And analysed in a notebook. That found three skills with wide gaps but few practice tasks, which is our next content to write." |

## 4:30 to 4:45 · Close (narrator C)

| Do | Say |
|---|---|
| Click **Log Out**. You return to the lighthouse. | "Logging out locks everything again. In the next phase, an AI coach replaces our rule-based planner, using the same diagnosis Maya just gave. Thank you." |

---

**If you run long:** trim the coach's view first (skip the job market, about
15 s), then the Sheets and notebook lines (about 10 s). Keep the
from-scratch story intact; it is the heart of the demo.
