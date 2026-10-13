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
- [ ] `LLM_API_KEY` is set on the server, so the coach shows *AI · ...*, not
      *Beacon rules* (see `../DEPLOY.md`). Without it the demo still works,
      but skip the "open-source model" line.
- [ ] The Vega-Lite spec is ready to paste, and a terminal is open in
      `docs/a5/alt_uses/`.
- [ ] Do one full rehearsal on production (see `../DEPLOY.md`). Delete the
      rehearsal account afterwards in Django admin > Users.

**Demo persona:** Maya, using the built-in sample resume (a data-analytics
student). It is served by the site, so there is no file to find on
camera: click **Use the sample resume** on step 1. After the import, drag
**STAR-format storytelling** to 30 and **Product sense** to 45 so the plan
has clear top gaps.

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

## 1:25 to 2:25 · Onboarding: from blank account to diagnosis (narrator B)

| Do | Say |
|---|---|
| You land on **Welcome**, step 1. Click **Use the sample resume** (or drop Maya's PDF). | "A new account knows nothing about Maya, so instead of a long form, she can hand Beacon her resume, or her LinkedIn profile saved as a PDF. It's read once and never stored." |
| Point at the results: 5 skills, the quoted evidence, *Working with data* ticked. | "Beacon found SQL five times, Python four, Git three, and quotes where. It also noticed she enjoys working with data." |
| **Next.** Data Analyst is pre-selected and *Suggested for you*. Also tick **Product Manager**. | "It suggests Data Analyst. She's also curious about product, so she picks both, and Beacon holds her to the tougher bar of the two." |
| Leave **No interview yet** and choose **8 weeks**. | "She has no interview booked yet, so she gets an open-ended eight-week plan instead." |
| **Next.** Point at a *from resume* tag, then drag STAR storytelling down to 30. The ring moves. | "Her resume gave her a head start on these sliders, but a resume shows you used a skill, not how good you are. So she adjusts honestly, and the ring projects her readiness live." |
| **Light my beacon.** | "Submit, and Beacon builds her profile and her plan." |

## 2:25 to 3:25 · Her plan and her AI coach (narrator B)

| Do | Say |
|---|---|
| **My plan** loads with "Your beacon is lit". Pause on it. | "This page is now hers: both target roles, her eight-week timeline, and her readiness." |
| Point at **Your widest gaps**. | "Her widest gaps are the ones her resume couldn't show, like storytelling and product sense, so that's where the plan starts." |
| Scroll to **Week by week**. Read one task's *why* line. | "Every task says why it's there: what she rated herself, and what the tougher of her roles expects." |
| **Tick the two week-1 tasks.** The progress bar moves and week 1 turns green. | "As she practises, she ticks tasks off and her progress updates instantly." |
| Scroll up to **Your coach**. Point at the badge (*AI · Llama 3.3 70B via Groq*). | "And because Beacon is an AI coach: an open-source model reads her scores and plan, never her name, and tells her what to focus on this week." |
| Click **Answer it and get feedback**, type a 2-line answer, and press **Ask**. | "She can practise right here. The coach gives feedback on her answer, including whether it follows the STAR structure." |

## 3:25 to 3:45 · The coach's view (narrator C)

| Do | Say |
|---|---|
| Click **Dashboard**. Let the rings animate. | "A career coach sees the whole cohort: readiness for every candidate, and the widest gaps across everyone." |
| Press **⌘K**, type `maya`, Enter. | "And can jump to any student, skill or page in one shortcut." |
| Open **Job market**, search `analyst`. | "Beacon also pulls live job postings from a public jobs API, and ranks skills by how often employers ask for them times how far our students are behind." |

## 3:45 to 4:35 · APIs and data (narrator C)

| Do | Say |
|---|---|
| Open `/api/skills/summary/`. | "Beacon has exactly one public API: this skill summary. It is aggregates only, so no individual can be identified." |
| In a signed-out window, open `/api/assessments/`. | "Every other API is protected. Signed out, it answers 401." |
| Vega-Lite editor with the spec pasted; point at `data.url`. | "The Vega-Lite editor reads our production URL directly, with no copied data." |
| Terminal: `python use1_python_report.py` | "The same API in a Python script, rolled up by category." |
| The Google Sheet with `IMPORTDATA`. | "Imported live into Google Sheets with one formula." |
| The notebook chart. | "And analysed in a notebook. That found three skills with wide gaps but few practice tasks, which is our next content to write." |

## 4:35 to 4:50 · Close (narrator C)

| Do | Say |
|---|---|
| Click **Log Out**. You return to the lighthouse. | "Logging out locks everything again. In the next phase, an AI coach replaces our rule-based planner, using the same diagnosis Maya just gave. Thank you." |

---

**If you run long:** trim the coach's view first (skip the job market, about
15 s), then the Sheets and notebook lines (about 10 s). The cohort
dashboard can go entirely if needed; the AI coach should stay. Keep the
from-scratch story intact; it is the heart of the demo.
