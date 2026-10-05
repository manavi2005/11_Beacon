# Beacon: An AI Personal Career Coach

**INFO 490 MG | Team Career Coaches (Group 11)**
Manavi Chaudhry | Chu-Yun Hwang | Meet Kailash Mali

Beacon turns a student's resume and target role into a diagnosed skill profile, a
time-boxed preparation plan, and a progress tracker. Instead of showing users
everything they could do, it tells them what to do next.

---

## Contents

1. [Quick start](#1-quick-start)
2. [What to look at](#2-what-to-look-at)
3. [Directory structure](#3-directory-structure)
4. [Settings and security](#4-settings-and-security)
5. [Views](#5-views)
6. [Templates](#6-templates)
7. [The data model](#7-the-data-model)
8. [Proving it works](#8-proving-it-works)
9. [Git workflow](#9-git-workflow)
10. [Documentation index](#10-documentation-index)
11. [Forms & User Input](#11-forms--user-input)
12. [Creating APIs](#12-creating-apis)
13. [Vega-Lite charts and an external API](#13-vega-lite-charts-and-an-external-api)

---

## 1. Quick start

From the folder containing `manage.py`:

```bash
# 1. virtual environment
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. install
pip install -r requirements.txt

# 3. secrets
cp .env.example .env               # then edit DJANGO_SECRET_KEY

# 4. build the database
python manage.py migrate

# 5. load realistic test data
python manage.py seed_demo_data

# 6. create an admin login (required - see note below)
python manage.py createsuperuser

# 7. run
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

**Step 6 is not optional.** `db.sqlite3` is git-ignored, so a fresh clone builds
its database from scratch, and `seed_demo_data` creates only the six candidate
accounts - no superuser. Without step 6 there is no way to log in at `/admin/`.
Any username and password will do; earlier submissions used `tester` /
`uiuc12345`.

The six seeded candidates are ordinary non-staff users and share the password
`beacon12345`.

**Running the production settings**

```bash
python manage.py runserver --settings=beacon_core.settings.production
```

`manage.py` defaults to `beacon_core.settings.development`, so no flag is needed
for everyday work. `wsgi.py` and `asgi.py` default to production, which is what a
real deployment loads.

---

## 2. What to look at

Every page is reachable from the navigation bar at the top of the site.

| URL | What it is | Kind of view |
|---|---|---|
| `/` | Row counts and a plan summary | FBV, `render()` |
| `/skills/manual/` | Skill catalog, response assembled by hand | **FBV, `HttpResponse`** |
| `/skills/` | Skill catalog, same page via the shortcut | **FBV, `render()`** |
| `/plans/cbv-base/` | Every preparation plan | **CBV, base `View`** |
| `/tasks/` | Every task across every plan | **CBV, generic `ListView`** |
| `/tasks/<pk>/` | One task in full | CBV, generic `DetailView` (extra) |
| `/skills/<pk>/` | One skill: assessments and tasks that target it | CBV, generic `DetailView` |
| `/plans/<pk>/` | One preparation plan and its tasks | CBV, generic `DetailView` |
| `/candidates/` | Every candidate, annotated with counts and averages | CBV, generic `ListView` |
| `/candidates/<pk>/` | One candidate: goal, scores, plans, biggest gaps | CBV, generic `DetailView` |
| `/search/skills/` | Skill search form (GET) | FBV, `render()` |
| `/search/candidates/` | Candidate lookup form (POST) | CBV, base `View` |
| `/insights/` | Totals and grouped summaries (`count()`, `annotate()`) | FBV, `render()` |
| `/charts/` | Four Matplotlib charts drawn from live ORM aggregates | FBV, `render()` |
| `/charts/*.png` | Each chart on its own URL, returning `image/png` | FBV, `HttpResponse` |
| `/api/skills/summary/` | One aggregated row per skill, chart-ready JSON | FBV, `JsonResponse` |
| `/api/assessments/` | One anonymous row per skill assessment, chart-ready JSON | FBV, `JsonResponse` |
| `/vega-lite/` | Two Vega-Lite charts loading the API above by URL | FBV, `render()` |
| `/vega-lite/chart<N>.json` | Each chart's spec, with an absolute data URL for the editor | FBV, `JsonResponse` |
| `/vega-lite/chart<N>.png` | Each Vega-Lite chart drawn on the server | FBV, `HttpResponse` |
| `/api/market-demand/?q=<role>` | Jobicy job postings joined with Beacon's skill gaps | FBV, `JsonResponse` |
| `/market/?q=<role>` | The same report as a page | FBV, `render()` |
| `/admin/` | Django Admin for all five models | - |

The four bolded rows are the four required kinds of view.

**Seeing the empty state:** `/skills/?q=zzzz` filters the catalog down to nothing
and fires the `{% empty %}` branch, without deleting anything from the database.

**Assignment 3 additions.** Every model now implements `get_absolute_url()`,
so list templates link to detail pages with `{{ object.get_absolute_url }}`
rather than rebuilding paths by hand, and every navigation link is reversed
with `{% url %}`. Two search forms demonstrate the GET/POST distinction:
`/search/skills/` filters the public skill catalog with `request.GET` so the
result stays shareable as a link, while `/search/candidates/` looks up
personal candidate records with `request.POST` so names and emails never
enter the URL or the browser history. `/insights/` presents database-side
aggregations: totals, skills grouped by category, and per-plan completion
counts.

**Look and feel.** The site is styled by one stylesheet,
[`static/css/beacon.css`](static/css/beacon.css), loaded with
`{% static %}` in `base.html`. It replaced the inline `<style>` block that
every page used to carry its own copy of. The layout is a navy masthead with
the Beacon lighthouse mark, a wrapping pill navigation, and page content on a
white card: tables get zebra striping and uppercase headers so a 24-row task
list stays readable, totals are shown as stat tiles rather than a two-column
table, plan progress gets a bar beside the percentage, and statuses are
colour-coded pills where the word still carries the meaning on its own. The
two brand colours are the university's, navy for structure and orange for
anything actionable. It reflows to one column on a phone, and the wider tables
scroll sideways inside their own box instead of crushing their columns.

In production, `ManifestStaticFilesStorage` serves the stylesheet under a
content-hashed name such as `beacon.a0c1fb82e482.css`, so it can be cached
indefinitely and a change to the file changes the URL. The reasoning is in
[`docs/notes/notes.txt`](docs/notes/notes.txt).

**Charts.** `/charts/` shows four Matplotlib figures, each drawn at request
time from an ORM aggregate and served from its own `.png` URL as
`image/png`. Nothing is precomputed and no image file is written to disk:
[`preparation/charts.py`](preparation/charts.py) renders into a `BytesIO`
buffer and the view returns the bytes. It uses the headless `Agg` backend
and builds `Figure` objects directly rather than through `pyplot`, which is
what keeps a long-running server from accumulating figures it never closes.

---

## 3. Directory structure

```
11_Beacon/
├── README.md
├── manage.py                     # defaults to settings.development
├── requirements.txt
├── db.sqlite3                    # git-ignored; rebuilt with migrate + seed
├── .env                          # local secrets - git-ignored, never committed
├── .env.example                  # committed template showing required keys
├── .gitignore
│
├── beacon_core/                  # control centre: settings and routing only
│   ├── settings/                 # split-settings package
│   │   ├── __init__.py
│   │   ├── base.py               # shared settings + .env loader
│   │   ├── development.py        # DEBUG = True
│   │   └── production.py         # DEBUG = False, hardened
│   ├── urls.py                   # includes each feature app's urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── preparation/                  # feature app: diagnose -> plan -> track
│   ├── models.py                 # the five models
│   ├── admin.py                  # all five registered, with inlines
│   ├── views.py                  # the four graded views (+ dashboard)
│   ├── urls.py                   # every route named
│   ├── migrations/
│   └── management/commands/
│       ├── seed_demo_data.py
│       └── verify_constraints.py
│
├── static/                       # our own assets, served by {% static %}
│   ├── css/beacon.css            # the whole site stylesheet
│   └── img/beacon-logo.svg       # lighthouse mark, used as logo and favicon
│
├── staticfiles/                  # git-ignored; collectstatic build output
│
├── templates/
│   ├── base.html                 # inherited by every page
│   └── preparation/
│       ├── dashboard.html
│       ├── skill_list.html       # shared by BOTH function-based views
│       ├── plan_list.html
│       ├── task_list.html
│       └── task_detail.html
│
└── docs/
    ├── README.md                 # documentation index, mapped to assignment sections
    ├── wireframes/v1/            # Part 3 wireframes, PDF + per-screen PNGs
    ├── branching_strategy/       # diagram.png + written strategy
    ├── notes/notes.txt           # running progress log
    ├── data_model/               # ER diagram, design justification, constraint output
    └── screenshots/              # browser output, named by assignment section
        ├── admin/                # Django Admin list views
        └── superseded/           # older captures, kept for the record
```

**Start with [`docs/README.md`](docs/README.md)** - it maps every assignment
requirement to the file that answers it.

**Why these names**

- `beacon_core` - the `startproject` folder holds no features, only settings and
  routing. Naming it `beacon` would have collided with the repo folder and made
  imports ambiguous; `_core` says "control centre, not a feature".
- `preparation` - the `startapp` name is the domain it owns: everything about
  *preparing* for an interview. Later parts add one app per teammate
  (`profiles`, `diagnostics`, `mock_interviews`, `progress`) beside it.

---

## 4. Settings and security

### Split settings

```
beacon_core/settings/
├── base.py          # everything shared. Never run directly.
├── development.py   # DEBUG = True,  ALLOWED_HOSTS = 127.0.0.1 / localhost
└── production.py    # DEBUG = False, ALLOWED_HOSTS from the environment
```

Both children start with `from .base import *`, then override only what differs.
`DEBUG = True` shows full tracebacks, file paths and settings on any error -
which is exactly why it is `False` in production, where a visitor must never see
them.

### Environment variables

`SECRET_KEY` and `ALLOWED_HOSTS` are read from a `.env` file that is listed in
`.gitignore` and has never been committed. `.env.example` **is** committed, so a
teammate cloning the repo can see which keys they need without ever seeing a real
value:

```
DJANGO_SECRET_KEY=replace-with-a-long-random-string
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
# Dummy placeholder until the plan generator is wired up:
PLAN_GENERATOR_API_KEY=dummy-key-not-a-real-secret
```

`base.py` contains a small hand-written `load_env()` rather than pulling in
`python-dotenv`, so the project runs with nothing installed except Django. A
production project would use `django-environ` instead.

`production.py` reads `SECRET_KEY` from the environment with no usable fallback,
so a misconfigured deployment fails loudly rather than running on a known key.

---

## 5. Views

`preparation/views.py` implements four kinds of view over the same domain. Each
is numbered in the file and wired to a named URL.

### View 1: FBV, `HttpResponse`

```python
def skill_catalog_manual(request):
    template = loader.get_template("preparation/skill_list.html")
    html = template.render(context, request)
    return HttpResponse(html)
```

Three steps, all visible: find the template, render it to a string, wrap that
string in a response. This is what `render()` does internally.

### View 2: FBV, `render()`

```python
def skill_catalog_render(request):
    return render(request, "preparation/skill_list.html", context)
```

Same template, same data, one line. Identical output to View 1 - the only thing
that changes is the plumbing, which is the point of putting them side by side.

### View 3: CBV, base `View`

```python
class PlanBoardView(View):
    template_name = "preparation/plan_list.html"

    def get(self, request):
        plans = PreparationPlan.objects.select_related("candidate__user")
        return render(request, self.template_name, {"plans": plans, ...})
```

Inheriting the bare `View` buys exactly one thing: dispatch by HTTP method. A GET
lands in `get()`, a POST would land in `post()`, with no branching on
`request.method`. The queryset, the context and the `render()` call are all still
written by hand.

### View 4: CBV, generic `ListView`

```python
class PlanTaskListView(ListView):
    model = PlanTask
    template_name = "preparation/task_list.html"
    context_object_name = "tasks"
    paginate_by = 25
```

`model = PlanTask` is the whole configuration. Django supplies the queryset, the
context and the pagination. `get_queryset()` is overridden only to add
`select_related()`, which avoids one extra query per row when the template prints
`task.plan.title` and `task.skill.name`.

An extra generic `DetailView` sits at `/tasks/<pk>/`, linked from the task list.

### URL routing

Every route in `preparation/urls.py` carries a `name=`, and the module sets
`app_name = "preparation"`, so templates reverse routes by name
(`{% url 'preparation:task_list' %}`) instead of hard-coding paths. Renaming a URL
pattern therefore never breaks a link.

A written comparison of when each kind of view actually earned its place in this
project is in `docs/notes/notes.txt`.

---

## 6. Templates

`base.html` defines `{% block title %}`, `{% block heading %}` and
`{% block content %}`, plus the shared navigation and styling. Every page extends
it, so branding and layout live in exactly one file.

**Template reuse.** `skill_list.html` is rendered by *both* function-based views.
If the two FBVs produced visibly different pages, the difference between
`HttpResponse` and `render()` would look bigger than it actually is; sharing the
template makes the comparison honest.

**Empty states.** Every list uses `{% for %}` with an `{% empty %}` branch, and
each empty message says what to do next rather than just reporting that nothing
was found:

```django
{% for skill in skills %}
  ...
{% empty %}
  {% if query %}
    No skills match "{{ query }}". Try a different filter.
  {% else %}
    The skill catalog is empty. Run
    <code>python manage.py seed_demo_data</code> to load the demo rows.
  {% endif %}
{% endfor %}
```

---

## 7. The data model

Five models, one app. Full reasoning in `docs/data_model/design_notes.md`; diagram in
`docs/data_model/er_diagram.pdf`.

| Model | Represents | Key relationship |
|---|---|---|
| `Skill` | One coachable competency in the shared catalog | referenced by assessments and tasks |
| `CandidateProfile` | A user's career goal, resume, timeline and main concern | `OneToOneField(User, CASCADE)` |
| `SkillAssessment` | One quiz result: proficiency vs required level | FK candidate `CASCADE`, FK skill `PROTECT` |
| `PreparationPlan` | A time-boxed roadmap for one candidate | FK candidate `CASCADE` |
| `PlanTask` | One action inside a plan, with its week and rationale | FK plan `CASCADE`, FK skill `SET_NULL` |

`CandidateProfile.skills` is a `ManyToManyField(Skill, through="SkillAssessment")`,
so a candidate-skill link always carries a score and a date - never a bare
association.

Three figures the wireframes show are **derived, not stored**, so they cannot go
stale: `CandidateProfile.readiness_percent` (Screen 3's Overall Readiness),
`PreparationPlan.completion_percent` (Screen 4's progress bar), and
`current_week` / `total_weeks` (Screen 3's Completed / Current / Upcoming states).

### Constraints

| Constraint | Model | Meaning |
|---|---|---|
| `uniq_skill_name_per_category` | Skill | no duplicate skill name inside a category |
| `uniq_assessment_per_candidate_skill` | SkillAssessment | one current score per candidate per skill |
| `uniq_plan_title_per_candidate` | PreparationPlan | no two plans with the same title for one person |
| `uniq_task_title_per_plan` | PlanTask | no duplicate task inside a plan |
| `scores_within_0_100` | SkillAssessment | `CheckConstraint` on both score fields |
| `plan_ends_after_it_starts` | PreparationPlan | `CheckConstraint`: `target_date >= start_date` |

### Seeded test data

| Table | Rows |
|---|---|
| Skill | 12 |
| CandidateProfile | 6 |
| SkillAssessment | 24 |
| PreparationPlan | 6 |
| PlanTask | 24 |

`python manage.py seed_demo_data --flush` rebuilds it from scratch.

---

## 8. Proving it works

### Smoke tests

```bash
python manage.py test preparation
```

41 tests, no fixtures needed. They load every page and assert the right
template and data came back, check that `{% empty %}` fires, exercise both
search forms, the aggregations and the chart endpoints, and guard against the
multi-line `{# #}` comment bug that once printed template notes onto every
page. Not an assignment requirement - they are there so a later change cannot
quietly break an earlier deliverable.

### Constraints

```bash
python manage.py verify_constraints
```

Eight checks, each run inside a transaction that is rolled back, so the database
is never modified. Saved output: `docs/data_model/constraint_validation.txt`.

1. Duplicate `(candidate, skill)` assessment -> rejected
2. Duplicate plan title for one candidate -> rejected
3. `target_date` before `start_date` -> rejected
4. Proficiency score of 140 -> rejected by validators
5. Deleting a scored `Skill` -> blocked by `PROTECT`
6. Deleting a `PreparationPlan` -> its tasks cascade away
7. Deleting a tagged `Skill` -> task survives, `skill` set to `NULL`
8. Deleting a `User` -> their `CandidateProfile` cascades away

### Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every pull
request into `main` and every push to it. On a clean Ubuntu runner with
Python 3.11 it installs `requirements.txt`, runs `manage.py check`, confirms no
model change is missing a migration, builds and seeds a fresh database, runs
`verify_constraints`, and runs the full test suite. A PR shows a green tick or
a red cross before anyone merges it, so a branch that breaks `main` is caught
on the PR rather than after the merge.

---

## 9. Git workflow

`main` is never worked on directly. Work happens on a branch cut from `main` and
returns through a pull request, so `main` always runs and is always submittable.

```bash
git checkout main && git pull origin main
git checkout -b feature/short-description
# ... small, frequent commits ...
git push -u origin feature/short-description
# open a pull request on GitHub, then merge
```

Branch prefixes: `feature/`, `fix/`, `docs/`. Full strategy, including file
ownership per teammate and conflict handling:
[`docs/branching_strategy/README.md`](docs/branching_strategy/README.md).

`.env` and `db.sqlite3` are both git-ignored. Teammates rebuild the database with
`python manage.py migrate && python manage.py seed_demo_data`.

---

## 10. Documentation index

| File | What it holds |
|---|---|
| [`docs/README.md`](docs/README.md) | **Start here** - index mapping each assignment section to the files that answer it |
| `docs/notes/notes.txt` | Running weekly log: decisions, open questions, reminders |
| `docs/branching_strategy/README.md` | Branch naming, workflow, file ownership, conflicts |
| `docs/branching_strategy/diagram.png` | Visual of the branch-and-merge flow |
| `docs/wireframes/v1/` | Part 3 wireframes - full PDF plus one PNG per screen |
| `docs/data_model/design_notes.md` | Why five models, why each `on_delete`, what each constraint protects |
| `docs/data_model/er_diagram.pdf` | Entity-relationship diagram |
| `docs/data_model/constraint_validation.txt` | Saved output of `verify_constraints` |
| `docs/screenshots/` | Browser output and Django Admin list views |

---

## 11. Forms & User Input

### 11.1 GET Search Form

Beacon includes a GET-based skill search and filtering form at:

```
/search/skills/
```

The form uses:

```
<form method="get">
```

The user can search by skill name and optionally filter by category or target
role. Because the form uses GET, the search parameters appear in the URL. For
example:

```
/search/skills/?q=python&category=TECH
```

This makes a skill search easy to bookmark, reload, and share.

The view reads the submitted values through `request.GET` and filters the
`Skill` queryset using Django ORM query parameters such as `name__icontains`
and `category__exact`.

### 11.2 POST Create Form

Beacon also includes a POST form for creating a new `PlanTask` at:

```
/tasks/create/
```

This form is implemented using the class-based `PlanTaskCreateView`, which
inherits from Django's generic `CreateView`.

The form is defined as a `ModelForm` based on the `PlanTask` model. Users can
provide information such as:

* Preparation plan
* Skill
* Task title
* Week number
* Instructions
* Rationale
* Due date
* Estimated time
* Priority
* Status

The form uses:

```
<form method="post">
```

and includes Django's CSRF protection:

```
{% csrf_token %}
```

When the user submits the form, Django validates the submitted values and
creates a new `PlanTask` database record. After a successful submission,
`CreateView` redirects to the new task's detail page using the model's
`get_absolute_url()` method.

This demonstrates the appropriate use of POST for a database-changing
operation rather than putting creation data in a URL.

### 11.3 POST Candidate Search

Beacon also has a POST-based candidate search at:

```
/search/candidates/
```

This form uses `request.POST` and includes `{% csrf_token %}`. The search
accepts a single term and searches candidate names, usernames, email
addresses, target roles, and target companies.

This is an additional example of handling submitted data with POST. Unlike
the task creation form, it does not modify the database.

POST is useful here because candidate search terms may contain personal
information. Using POST keeps the search term out of the URL. However, POST
does not encrypt the request or guarantee that the value is absent from
server-side logs; HTTPS is still required to protect data in transit.

### 11.4 GET vs POST Design

The forms demonstrate different purposes for the two HTTP methods:

| Form              | Method | Purpose                             |
| ----------------- | ------ | ----------------------------------- |
| Skill search      | GET    | Search/filter public reference data |
| PlanTask creation | POST   | Create a new database record        |
| Candidate search  | POST   | Submit a candidate lookup term      |

The skill search uses GET because the resulting filter can be represented by
URL parameters and shared or bookmarked. The PlanTask creation form uses POST
because it changes application data. The candidate search uses POST to avoid
putting potentially personal search terms directly in the URL.

### 11.5 CSRF Protection

The PlanTask creation form and candidate search form both include:

```
{% csrf_token %}
```

Django uses the CSRF token to help protect POST requests against
cross-site request forgery. The token is generated by Django and must be
included when the form is submitted.

### 11.6 Class-Based View

The PlanTask creation form is handled by:

```
PlanTaskCreateView(CreateView)
```

`CreateView` provides the standard GET/POST workflow for a model creation
form. GET displays the form, while POST validates and saves the submitted
data.

This satisfies the Section 5 requirement to adapt a class-based view to
handle GET and POST input.


---

## 12. Creating APIs

### 12.1 Skill JSON API

Beacon provides a public JSON endpoint for the skill catalog:

| Method | URL                                   | Purpose                   |
| ------ | ------------------------------------- | ------------------------- |
| GET    | `/api/skills/`                        | Return all skills as JSON |
| GET    | `/api/skills/?q=python`               | Filter skills by name     |
| GET    | `/api/skills/?category=TECH`          | Filter skills by category |
| GET    | `/api/skills/?q=python&category=TECH` | Apply both filters        |

The API is implemented as a function-based view in `preparation/views.py` using Django's `JsonResponse`.

The endpoint returns the number of matching skills and a list of skill records. Each result includes the skill's database ID, name, category code, and human-readable category label.

Example response:

```json
{
    "count": 1,
    "results": [
        {
            "id": 1,
            "name": "Python",
            "category": "TECH",
            "category_label": "Technical"
        }
    ]
}
```

The `q` parameter uses a case-insensitive substring search on the skill name. The `category` parameter filters by the exact category code. Both parameters can be supplied together.

### 12.2 HttpResponse vs JsonResponse

Beacon also demonstrates the difference between Django's `HttpResponse` and `JsonResponse`.

The existing skill catalog view uses `HttpResponse` to return rendered HTML, whose content type is:

```text
text/html; charset=utf-8
```

The skill API uses `JsonResponse`, whose content type is:

```text
application/json
```

The chart endpoints also use `HttpResponse`, but explicitly set their content type to `image/png` because they return PNG image data.

This demonstrates that `HttpResponse` is a general HTTP response class whose content type depends on the response data, while `JsonResponse` is specifically designed for JSON data.

### 12.3 API design plan

The first Beacon API serves the project's skill catalog because skills are reusable reference data that can be consumed independently from the HTML pages.

A future version could expose additional read-only project data, such as preparation plans, task progress, or candidate skill summaries. Any future endpoint would need to consider which information is appropriate to expose publicly, especially for candidate-related data.

---

## 13. Vega-Lite charts and an external API

Assignment 4, Parts 1 and 2. Code: [`preparation/vega.py`](preparation/vega.py),
[`preparation/market.py`](preparation/market.py), and the Assignment 4 block
at the end of [`preparation/views.py`](preparation/views.py).

### 13.1 Internal API for charts

| Method | URL | Returns |
|---|---|---|
| GET | `/api/skills/summary/` | One row per skill: `skill`, `category`, `learners`, `avg_proficiency`, `avg_required`, `avg_gap`, `tasks` |
| GET | `/api/assessments/` | One row per assessment: `skill`, `category`, `experience`, `proficiency`, `required`, `gap`, `assessed_on` |

Both return a bare JSON array of flat records, which is what Vega-Lite's
`data: {"url": ...}` reads with no format hints. The numbers are computed by
the database (`annotate()` with `Count` and `Avg`), not by Python loops.

`/api/assessments/` is deliberately anonymous: it carries scores, never a
candidate's name, username or email. These endpoints are public, and the
assignment expects classmates to load them in the Vega-Lite editor.

**Cross-origin access.** Every response carries
`Access-Control-Allow-Origin: *`, and an `OPTIONS` preflight is answered with
`Access-Control-Allow-Private-Network: true`. Without both, a page on another
site, such as the online Vega-Lite editor, cannot read the data. The endpoints
are read-only, so allowing any origin is safe: only GET, HEAD and OPTIONS
are accepted.

### 13.2 Vega-Lite charts

| Chart | Kind | Data | Spec | PNG |
|---|---|---|---|---|
| 1. Widest skill gaps | Bar, aggregated summary | `/api/skills/summary/` | `/vega-lite/chart1.json` | `/vega-lite/chart1.png` |
| 2. Proficiency against requirement | Scatter, with a y = x reference line | `/api/assessments/` | `/vega-lite/chart2.json` | `/vega-lite/chart2.png` |

The specs live in [`preparation/vega_lite/`](preparation/vega_lite/) as plain
JSON and use `data: {"url": ...}` with no inline values. A test enforces that.
`/vega-lite/` embeds both with vega-embed. The `.json` endpoint returns the
spec with an absolute data URL for whatever host served it, so it can be
pasted straight into the [Vega-Lite editor](https://vega.github.io/editor/).
Copies made against the local server are in
[`docs/vega_lite/`](docs/vega_lite/).

The `.png` endpoints draw the same specs on the server with `vl-convert`,
pinned to Vega-Lite 6.4, the same version the page loads from the CDN. When
drawing a PNG, the server hands vl-convert the rows the API would return,
rather than letting it fetch the API over HTTP. Fetching its own URL would
make the server wait on itself and hang on a single-worker deployment.

**Using the editor locally.** Run the server, open the editor, and paste in
`http://127.0.0.1:8000/vega-lite/chart1.json`'s contents. The first time,
Chrome asks whether `vega.github.io` may access devices on your local network.
Allow it, because that is the browser asking whether a public site may read
from `127.0.0.1`.

### 13.3 External API: Jobicy job postings

`/api/market-demand/?q=data analyst` answers one question: *of the skills
our candidates are behind on, which ones do employers hiring for that role
actually ask for?*

1. **Fetch.** `requests.get("https://jobicy.com/api/v2/remote-jobs",
   params={"count": 50, "tag": q}, timeout=5)`, then `raise_for_status()`.
   Jobicy is free and keyless. Open-Meteo was excluded by the assignment.
2. **Measure.** For each catalog skill, count how many postings mention it,
   using a keyword list per skill in `market.SKILL_KEYWORDS` (a "SQL"
   skill also matches "PostgreSQL"). Matches use word boundaries, so "git"
   does not match "digital".
3. **Triangulate.** Join those counts with the average gap (required minus
   proficiency) for candidates whose `target_role` matches `q`. If no
   candidate targets that role, all candidates are used, and the response
   says so.
4. **Rank.** `priority = demand % x positive gap / 100`, so a skill scores
   only if employers want it *and* candidates are behind on it.

Nothing from Jobicy is stored in the database. Each query's postings are
cached in memory for an hour, so a classroom loading the same page does not
send Jobicy one request each. Following Jobicy's terms, the page credits
Jobicy and links every posting to its original URL.

**Errors.** No `q` returns 400. A Jobicy timeout returns 504. An error
status, a dropped connection or a non-JSON body returns 502. Each is a JSON
`{"error": ...}`, never a traceback, and `/market/` shows the same message on
the page instead of failing.

### 13.4 Tests

`InternalApiTests`, `VegaLiteTests` and `MarketDemandTests` in
[`preparation/tests.py`](preparation/tests.py) cover the row shapes, the
anonymity of `/api/assessments/`, CORS, the specs having no inline data, the
PNG endpoints, and every Jobicy failure path. `requests.get` is mocked in
every test, so the suite never calls Jobicy.
