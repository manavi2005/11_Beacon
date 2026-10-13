# Beacon: documentation index

**Team Career Coaches (Group 11)** | Manavi Chaudhry | Chu-Yun Hwang | Meet Kailash Mali

Start here. This page maps each assignment section to the files that answer it,
so nothing has to be hunted for.

---

## How this folder is organized

The assignment requires `docs/` to contain three specific folders -
`wireframes/`, `branching_strategy/` and `notes/` - so those stay exactly where
they are and keep their required names. Everything that was previously loose at
the top level of `docs/` is now grouped by **topic**, and this index provides the
**by-assignment-section** view on top of it.

Topic grouping was chosen over renaming folders after assignment sections for two
reasons: the three required folder names are fixed and cannot be renamed, and the
same document often serves more than one section (the branching strategy is
Section 1 evidence but also a standing team process). Grouping by topic keeps
each file in one obvious place, and this index handles the section mapping.

```
docs/
├── README.md               <- you are here: index + section mapping
├── wireframes/v1/          <- REQUIRED folder: Part 3 wireframes
├── branching_strategy/     <- REQUIRED folder: branch diagram + written strategy
├── notes/notes.txt         <- REQUIRED folder: weekly running log
├── data_model/             <- the data layer (ER diagram, design justification)
└── screenshots/            <- browser output, grouped by assignment section
    ├── section1-*.png      <- Assignment 2
    ├── section2-*.png      <- Assignment 2
    ├── section3-*.png      <- Assignment 2
    ├── a3-section1-*.png   <- Assignment 3: home, navigation, detail via link
    ├── a3-section2-*.png   <- Assignment 3: search and aggregations
    ├── a3-section3-*.png   <- Assignment 3: the styled UI
    ├── a3-section4-*.png   <- Assignment 3: the charts page
    ├── a4-part1-*.png      <- Assignment 4: Vega-Lite charts
    ├── a4-part3-*.png      <- Assignment 4: the reports page
    ├── a4-part2-*.png      <- Assignment 4: external API
    ├── admin/              <- Django Admin list views (earlier assignment)
    └── superseded/         <- older captures, kept for the record only
```

---

## Section 1: Structure, Security & GitHub Workflow

| Requirement | Where to look |
|---|---|
| Split settings pattern | [`beacon_core/settings/`](../beacon_core/settings/) - `base.py`, `development.py`, `production.py` |
| `DEBUG` True in dev / False in prod | `development.py` line 11, `production.py` line 12 |
| `ALLOWED_HOSTS` configured | `development.py` line 13, `production.py` lines 15-19 |
| `.env` for `SECRET_KEY` + API keys | [`.env.example`](../.env.example) is committed; `.env` is git-ignored |
| Secrets absent from code and commits | [`.gitignore`](../.gitignore) line 2 ignores `.env` |
| Proper `.gitignore` | [`.gitignore`](../.gitignore) |
| Non-main branch + merge back via PR | [`branching_strategy/README.md`](branching_strategy/README.md) |
| `docs/` with the three required folders | `wireframes/`, `branching_strategy/`, `notes/` |
| Weekly progress notes | [`notes/notes.txt`](notes/notes.txt) |
| Runs in dev and prod mode | See [README section 1](../README.md#1-quick-start) |

## Section 2: Views (FBV + CBV)

| View | Kind | URL | Code | Screenshot |
|---|---|---|---|---|
| `skill_catalog_manual` | FBV, `HttpResponse` | `/skills/manual/` | [views.py](../preparation/views.py) | [`section2-view1-fbv-httpresponse.png`](screenshots/section2-view1-fbv-httpresponse.png) |
| `skill_catalog_render` | FBV, `render()` | `/skills/` | [views.py](../preparation/views.py) | [`section2-view2-fbv-render.png`](screenshots/section2-view2-fbv-render.png) |
| `PlanBoardView` | CBV, base `View` | `/plans/cbv-base/` | [views.py](../preparation/views.py) | [`section2-view3-cbv-base-view.png`](screenshots/section2-view3-cbv-base-view.png) |
| `PlanTaskListView` | CBV, generic `ListView` | `/tasks/` | [views.py](../preparation/views.py) | [`section2-view4-cbv-generic-listview.png`](screenshots/section2-view4-cbv-generic-listview.png) |
| `PlanTaskDetailView` | CBV, generic `DetailView` (extra) | `/tasks/<pk>/` | [views.py](../preparation/views.py) | - |

Routing, with `name=` on every route: [`preparation/urls.py`](../preparation/urls.py).

The written comparison the bonus asks for - *HttpResponse vs render* and
*Base CBV vs Generic CBV* - is at the end of
[`notes/notes.txt`](notes/notes.txt), under
"SECTION 2 BONUS".

## Section 3: Templates

| Requirement | Where to look |
|---|---|
| `base.html` with `{% block title %}` and `{% block content %}` | [`templates/base.html`](../templates/base.html) |
| Feature list template extending `base.html` | [`templates/preparation/skill_list.html`](../templates/preparation/skill_list.html) |
| `{% for %}` + `{% empty %}` | every list template; `skill_list.html` lines 23-40 |
| Meaningful empty-state message | `skill_list.html` - distinguishes "no match for filter" from "catalog empty" |
| Template reuse across views | `skill_list.html` is rendered by **both** function-based views |
| Normal list state screenshot | [`section3-template-normal-list-state.png`](screenshots/section3-template-normal-list-state.png) |
| Empty state screenshot | [`section3-template-empty-state.png`](screenshots/section3-template-empty-state.png) |

To reproduce the empty state without touching the database, visit
`/skills/?q=zzzz` - the filter matches nothing and the `{% empty %}` branch
fires.

---

## Assignment 4: Internal API, Vega-Lite and an external API

| Requirement | Where to look |
|---|---|
| Internal JSON API, GET only, from the models, chart-ready | `/api/skills/summary/`, `/api/assessments/` - [`preparation/vega.py`](../preparation/vega.py) row builders |
| Bar chart (aggregated summary) | [`vega_lite/chart1.vl.json`](vega_lite/chart1.vl.json), source [`preparation/vega_lite/skill_gap_bar.vl.json`](../preparation/vega_lite/skill_gap_bar.vl.json) |
| Line or scatter chart | [`vega_lite/chart2.vl.json`](vega_lite/chart2.vl.json), source [`preparation/vega_lite/assessment_scatter.vl.json`](../preparation/vega_lite/assessment_scatter.vl.json) |
| `data: {url: ...}`, no inline data | Both specs. `VegaLiteTests.test_specs_load_data_by_url_and_never_inline` enforces it |
| Charts embedded in an HTML page | `/vega-lite/` - [`templates/preparation/vega_lite.html`](../templates/preparation/vega_lite.html) |
| Chart outputs on dedicated endpoints | `/vega-lite/chart1.png`, `/vega-lite/chart2.png` (and `.json` for each spec) |
| Screenshots of working charts | [`a4-part1-vega-lite-chart1.png`](screenshots/a4-part1-vega-lite-chart1.png), [`a4-part1-vega-lite-chart2.png`](screenshots/a4-part1-vega-lite-chart2.png) |
| External keyless API, `?q=`, `requests.get(params=, timeout=5)`, `raise_for_status()` | [`preparation/market.py`](../preparation/market.py) `fetch_postings()` |
| Errors handled | `MarketDataError` -> 400 / 502 / 504 JSON; the page shows a message |
| Combined with internal data, processed, not stored | `market_report()`: demand per skill x the role cohort's average gap |
| New internal endpoint for the processed result | `/api/market-demand/?q=data analyst`, page at `/market/?q=data analyst` |

Full explanation: [README section 13](../README.md#13-vega-lite-charts-and-an-external-api).

---

## The data layer (earlier assignment, still current)

| File | What it holds |
|---|---|
| [`data_model/design_notes.md`](data_model/design_notes.md) | Why five models, why each `on_delete`, what each constraint protects, and which wireframe screen maps to which model |
| [`data_model/er_diagram.pdf`](data_model/er_diagram.pdf) | Entity-relationship diagram (`.png` and `.dot` alongside) |
| [`data_model/generate_er_diagram.py`](data_model/generate_er_diagram.py) | Regenerates the `.dot` from `models.py` |
| [`data_model/constraint_validation.txt`](data_model/constraint_validation.txt) | Saved output of `python manage.py verify_constraints` - 8 checks, all passing |
| [`screenshots/admin/`](screenshots/admin/) | Django Admin list view per model |

## Design

| File | What it holds |
|---|---|
| [`wireframes/v1/beacon_wireframes_v1.pdf`](wireframes/v1/beacon_wireframes_v1.pdf) | All five screens, desktop and mobile, plus rationale |
| [`wireframes/v1/`](wireframes/v1/) | The same screens as individual PNGs |

## Process

| File | What it holds |
|---|---|
| [`notes/notes.txt`](notes/notes.txt) | Weekly log: what we did, decisions, open questions, TODOs |
| [`branching_strategy/README.md`](branching_strategy/README.md) | Branch naming, the cycle, commit-message style, file ownership, conflict handling |
| [`branching_strategy/diagram.png`](branching_strategy/diagram.png) | Visual of the branch-and-merge flow |

---

## Assignment 3, Section 1 - URL linking and navigation

| Requirement | Where to look |
|---|---|
| Home page at `/`, no 404 | `dashboard` in [views.py](../preparation/views.py), route in [urls.py](../preparation/urls.py) |
| Navigation bar, 3+ items, `{% url %}` only | [`templates/base.html`](../templates/base.html), 10 links, every one reversed with `{% url %}` |
| Detail pages keyed by primary key | `/skills/<pk>/`, `/plans/<pk>/`, `/candidates/<pk>/`, `/tasks/<pk>/` |
| Each list row links to its detail page | `candidate_list.html`, `skill_list.html`, `plan_list.html`, `task_list.html` |
| `get_absolute_url()` on the model | `Skill`, `CandidateProfile`, `PreparationPlan`, `PlanTask` in [models.py](../preparation/models.py) |
| Used in templates instead of `{% url %}` | `{{ object.get_absolute_url }}`, 21 uses across 10 templates |
| End-to-end flow | models.py -> urls.py -> views.py -> templates, walked through in `notes.txt` |
| Screenshots | [home](screenshots/a3-section1-home-page.png), [navigation](screenshots/a3-section1-navigation-and-list.png), [detail via link](screenshots/a3-section1-detail-via-link.png) |

## Assignment 3, Section 2 - ORM queries and data presentation

| Requirement | Where to look |
|---|---|
| List of objects from one model | `/candidates/`, `CandidateListView` |
| Search form using `request.GET` | `/search/skills/`, `skill_search` |
| Search form using `request.POST` | `/search/candidates/`, `CandidateSearchView` |
| Why each method | GET keeps the skill filter shareable as a link; POST keeps personal candidate data out of the URL and history. Reasoned through in `notes.txt` |
| Field lookups | `__icontains`, `__exact`, `__gt` |
| Relationship spanning with `__` | `assessments__candidate__target_role`, `plan__candidate__target_role`, `user__first_name` |
| Total, via `count()` | `/insights/`, the `totals` dict |
| Grouped summary, `annotate` + `Count` | skills per category, tasks per plan, learners per skill |
| `{% for %}` with `{% empty %}` | every list template |
| Screenshots | [GET search](screenshots/a3-section2-search-get.png), [aggregations](screenshots/a3-section2-aggregations.png) |

## Assignment 3, Section 3 - Static files and UI styling

| Requirement | Where to look |
|---|---|
| `static/` directory configured | `STATICFILES_DIRS` in [base.py](../beacon_core/settings/base.py); project level, reasoning in `notes.txt` |
| Static files load correctly | `STATIC_URL`, `STATIC_ROOT`, both finders left on |
| `{% load static %}` | first line of [`templates/base.html`](../templates/base.html) |
| Custom CSS file linked | [`static/css/beacon.css`](../static/css/beacon.css), linked with `{% static 'css/beacon.css' %}` |
| Colours | navy and orange brand tokens on `:root`, navy for structure, orange for anything actionable |
| Layout | masthead, pill nav, content card, stat tiles, progress meters, responsive under 700px |
| Fonts | system font stack, no network request |
| Logo / header | [`static/img/beacon-logo.svg`](../static/img/beacon-logo.svg), used in the masthead and as the favicon |
| Screenshot with CSS applied | [dashboard](screenshots/a3-section3-styled-dashboard.png), [insights](screenshots/a3-section3-styled-insights.png), [search](screenshots/a3-section3-styled-search.png), [mobile](screenshots/a3-section3-styled-mobile.png) |
| README UI note | [README, "Look and feel"](../README.md) |
| Static organisation write-up | `notes.txt`, "STATIC FILE ORGANIZATION" |
| Cache busting (bonus) | `ManifestStaticFilesStorage` in [production.py](../beacon_core/settings/production.py); write-up in `notes.txt` |

## Assignment 3, Section 4 - Data visualization

| Requirement | Where to look |
|---|---|
| ORM-based aggregation | [`charts.py`](../preparation/charts.py): `values()` + `Count`, filtered `Count` with `Q`, and two `Avg` aggregates |
| Chart generated correctly | Four figures, each with a title, axis labels, and a legend where there is more than one series |
| Image endpoint works | `/charts/skills-by-category.png`, `/charts/plan-progress.png`, `/charts/skill-gap.png`, `/charts/task-status.png`, each returning `image/png` |
| Returned with `HttpResponse` | `_png()` in [views.py](../preparation/views.py), sets `Content-Type` and `Content-Length` |
| `BytesIO` | `render_png()` in `charts.py`; RAM trade-off written up in `notes.txt` |
| Headless rendering | `matplotlib.use("Agg")` before use, and `Figure()` rather than `pyplot`, so no figure registry to leak |
| Displayed on a page | [`templates/preparation/charts.html`](../templates/preparation/charts.html) |
| Heading, caption, alt text | one `<h2>`, one `<figcaption>` naming the query, and descriptive `alt` per figure |
| Screenshot | [charts page](screenshots/a3-section4-charts-page.png) |

## Assignment 4, Part 3 - CSV and JSON exports, reports page

| Requirement | Where to look |
|---|---|
| CSV export for one model | `/reports/candidates.csv`, `export_candidates_csv` in [views.py](../preparation/views.py) |
| `Content-Type: text/csv` | set with `charset=utf-8`, so names with non-ASCII characters survive a spreadsheet |
| `Content-Disposition` + timestamped filename | `candidates_YYYY-MM-DD_HH-MM.csv`, built by `export_filename()` |
| First row is column headers | `write_csv()` writes the readable labels from `EXPORT_COLUMNS`, not the machine keys |
| Rows pulled from the DB, ordered | `export_queryset()`, ordered by username so two downloads are comparable |
| JSON export, same model | `/reports/candidates.json`, `export_candidates_json` |
| `generated_at`, `record_count`, `candidates` | the three top-level keys of the payload |
| `JsonResponse(json_dumps_params={"indent": 2})` | in `export_candidates_json` |
| Linked from a visible page, with buttons | Download CSV / Download JSON on [`/reports/`](../templates/preparation/reports.html) |
| Reports page with 2+ grouped summaries | by experience level, by target role, and tasks per plan (done vs all) |
| One totals line | `report_totals()`, rendered as stat tiles plus a sentence |
| Tables with headers and `{% empty %}` | all four tables in `reports.html` |
| Screenshot | [reports page](screenshots/a4-part3-reports-page.png) |

## Assignment 5, Part 1 - Internal Django authentication

| Requirement | Where to look |
|---|---|
| 1.1 Custom login page | `/accounts/login/`, `login_view` in [views.py](../preparation/views.py), [`registration/login.html`](../templates/registration/login.html) |
| 1.1 Custom signup page | `/accounts/signup/`, `signup_view`, [`registration/signup.html`](../templates/registration/signup.html) |
| 1.2 Logout | `/accounts/logout/`, POST-only; the nav carries a form, not a link |
| 1.3 `LOGIN_URL` | [`base.py`](../beacon_core/settings/base.py), so dev and prod agree |
| 1.3 `LOGIN_REDIRECT_URL` | `base.py`, pointing at a route that exists |
| 1.3 `LOGOUT_REDIRECT_URL` | `base.py` |
| 1.4 Protected sections | every page except login and signup; anonymous users get 302 to the login form |
| 1.4 Protected API | `/api/whoami/` answers 401 JSON; `/api/skills/` and `/reports/candidates.json` redirect |
| 1.5 Nav hidden before login | `{% if user.is_authenticated %}` in [`base.html`](../templates/base.html) |
| 1.5 Nav visible after login | same block, plus the logout form |

## Assignment 5, Part 2 - Google OAuth

| Requirement | Where to look |
|---|---|
| 2.1 Install and configure allauth | `django-allauth==65.19.7` in [requirements.txt](../requirements.txt); apps, `SITE_ID`, middleware and backends in [base.py](../beacon_core/settings/base.py) |
| 2.2 Google Cloud credentials | read from `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`; names documented in [.env.example](../.env.example) |
| 2.3 Localhost redirect URI | `http://127.0.0.1:8000/accounts/google/login/callback/` |
| 2.3 Production redirect URI | `https://<domain>/accounts/google/login/callback/` |
| 2.4 Button on login page | [`registration/login.html`](../templates/registration/login.html) includes `_google_button.html` |
| 2.4 Button on signup page | [`registration/signup.html`](../templates/registration/signup.html), same include |
| Both backends kept | `ModelBackend` + allauth's, so username/password still works |
| Degrades without credentials | [`context_processors.py`](../preparation/context_processors.py) hides the button |
| Deploy helper | `python manage.py set_site_domain <host>` |
| Screenshots | [login](screenshots/a5-part2-google-login-button.png), [signup](screenshots/a5-part2-google-signup-button.png) |

---

## Assignment 5, Part 3 - One public API, Vega-Lite, three alternative uses

Full write-up: [`a5/README.md`](a5/README.md).

| Requirement | Where to look |
|---|---|
| One public API; all others protected | `/api/skills/summary/` is public. Every other JSON API returns 401 when signed out (`api_login_required` in `preparation/views.py`, tests in `PublicVsProtectedApiTests`) |
| Vega-Lite chart on the deployed public API | [`a5/group-11-vega-lite-API-demo.txt`](a5/group-11-vega-lite-API-demo.txt) |
| Editor screenshot | [`screenshots/a5-part3-vega-lite-editor.png`](screenshots/a5-part3-vega-lite-editor.png) |
| Three alternative uses, with code and output | [`a5/alt_uses/`](a5/alt_uses/): Python report, spreadsheet import, notebook |

## Assignment 5, Part 4 - Demo video

Submitted separately; the recording materials are kept outside the
repository. Before recording, update production with
[`a5/DEPLOY.md`](a5/DEPLOY.md).

## Product features (final deployment stage)

| Feature | Where to look |
|---|---|
| Start from scratch: onboarding, interests, flexible goals | `/welcome/`, [`preparation/onboarding.py`](../preparation/onboarding.py) |
| Resume / LinkedIn PDF import | [`preparation/resume.py`](../preparation/resume.py), sample in [`a5/demo/`](a5/demo/) |
| Tasks done on the platform, graded, ratings follow evidence | `/me/tasks/<id>/`, [`preparation/practice.py`](../preparation/practice.py) |
| AI coach (free open model; any OpenAI-compatible API) | [`preparation/coach.py`](../preparation/coach.py), settings in `.env.example` |
| Students see only their own data; staff see the cohort | [`preparation/visibility.py`](../preparation/visibility.py) |
| Menu defined as data | [`preparation/navigation.py`](../preparation/navigation.py) |

## UI polish (final deployment stage)

Lighthouse login and signup pages, a dashboard with readiness rings and
widest-gap bars, and a Ctrl/Cmd+K command palette. Screenshots:
`screenshots/a5-ui-*.jpg`.
