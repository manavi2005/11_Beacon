# Beacon — An AI Personal Career Coach

**INFO 490 MG · Team Career Coaches (Group 11)**
Manavi Chaudhry · Chu-Yun Hwang · Meet Kailash Mali

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

# 6. create an admin login (required — see note below)
python manage.py createsuperuser

# 7. run
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

**Step 6 is not optional.** `db.sqlite3` is git-ignored, so a fresh clone builds
its database from scratch, and `seed_demo_data` creates only the six candidate
accounts — no superuser. Without step 6 there is no way to log in at `/admin/`.
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
| `/skills/manual/` | Skill catalog, response assembled by hand | **FBV — `HttpResponse`** |
| `/skills/` | Skill catalog, same page via the shortcut | **FBV — `render()`** |
| `/plans/cbv-base/` | Every preparation plan | **CBV — base `View`** |
| `/tasks/` | Every task across every plan | **CBV — generic `ListView`** |
| `/tasks/<pk>/` | One task in full | CBV — generic `DetailView` (extra) |
| `/admin/` | Django Admin for all five models | — |

The four bolded rows are the four required kinds of view.

**Seeing the empty state:** `/skills/?q=zzzz` filters the catalog down to nothing
and fires the `{% empty %}` branch, without deleting anything from the database.

---

## 3. Directory structure

```
11_Beacon/
├── README.md
├── manage.py                     # defaults to settings.development
├── requirements.txt
├── db.sqlite3                    # git-ignored; rebuilt with migrate + seed
├── .env                          # local secrets — git-ignored, never committed
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
├── preparation/                  # feature app: diagnose → plan → track
│   ├── models.py                 # the five models
│   ├── admin.py                  # all five registered, with inlines
│   ├── views.py                  # the four graded views (+ dashboard)
│   ├── urls.py                   # every route named
│   ├── migrations/
│   └── management/commands/
│       ├── seed_demo_data.py
│       └── verify_constraints.py
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

**Start with [`docs/README.md`](docs/README.md)** — it maps every assignment
requirement to the file that answers it.

**Why these names**

- `beacon_core` — the `startproject` folder holds no features, only settings and
  routing. Naming it `beacon` would have collided with the repo folder and made
  imports ambiguous; `_core` says "control centre, not a feature".
- `preparation` — the `startapp` name is the domain it owns: everything about
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
`DEBUG = True` shows full tracebacks, file paths and settings on any error —
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

### View 1 — FBV, `HttpResponse`

```python
def skill_catalog_manual(request):
    template = loader.get_template("preparation/skill_list.html")
    html = template.render(context, request)
    return HttpResponse(html)
```

Three steps, all visible: find the template, render it to a string, wrap that
string in a response. This is what `render()` does internally.

### View 2 — FBV, `render()`

```python
def skill_catalog_render(request):
    return render(request, "preparation/skill_list.html", context)
```

Same template, same data, one line. Identical output to View 1 — the only thing
that changes is the plumbing, which is the point of putting them side by side.

### View 3 — CBV, base `View`

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

### View 4 — CBV, generic `ListView`

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
so a candidate–skill link always carries a score and a date — never a bare
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

Eight tests, no fixtures needed. They load each of the four graded views and
assert the right template and data came back, check that `{% empty %}` fires,
and guard against the multi-line `{# #}` comment bug that once printed template
notes onto every page. Not an assignment requirement — they are there so a later
change cannot quietly break the Section 2 deliverable.

### Constraints

```bash
python manage.py verify_constraints
```

Eight checks, each run inside a transaction that is rolled back, so the database
is never modified. Saved output: `docs/data_model/constraint_validation.txt`.

1. Duplicate `(candidate, skill)` assessment → rejected
2. Duplicate plan title for one candidate → rejected
3. `target_date` before `start_date` → rejected
4. Proficiency score of 140 → rejected by validators
5. Deleting a scored `Skill` → blocked by `PROTECT`
6. Deleting a `PreparationPlan` → its tasks cascade away
7. Deleting a tagged `Skill` → task survives, `skill` set to `NULL`
8. Deleting a `User` → their `CandidateProfile` cascades away

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
| [`docs/README.md`](docs/README.md) | **Start here** — index mapping each assignment section to the files that answer it |
| `docs/notes/notes.txt` | Running weekly log: decisions, open questions, reminders |
| `docs/branching_strategy/README.md` | Branch naming, workflow, file ownership, conflicts |
| `docs/branching_strategy/diagram.png` | Visual of the branch-and-merge flow |
| `docs/wireframes/v1/` | Part 3 wireframes — full PDF plus one PNG per screen |
| `docs/data_model/design_notes.md` | Why five models, why each `on_delete`, what each constraint protects |
| `docs/data_model/er_diagram.pdf` | Entity-relationship diagram |
| `docs/data_model/constraint_validation.txt` | Saved output of `verify_constraints` |
| `docs/screenshots/` | Browser output and Django Admin list views |
