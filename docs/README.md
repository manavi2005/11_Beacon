# Beacon: documentation index

**Team Career Coaches (Group 11)** | Manavi Chaudhry | Chu-Yun Hwang | Meet Kailash Mali

Start here. This page maps each assignment section to the files that answer it,
so nothing has to be hunted for.

---

## How this folder is organised

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
| Search form using `request.POST` | `/search/candidates/`, `candidate_search` |
| Why each method | GET keeps the skill filter shareable as a link; POST keeps personal candidate data out of the URL and history. Reasoned through in `notes.txt` |
| Field lookups | `__icontains`, `__exact`, `__gt` |
| Relationship spanning with `__` | `assessments__candidate__target_role`, `plan__candidate__target_role`, `user__first_name` |
| Total, via `count()` | `/insights/`, the `totals` dict |
| Grouped summary, `annotate` + `Count` | skills per category, tasks per plan, learners per skill |
| `{% for %}` with `{% empty %}` | every list template |
| Screenshots | [GET search](screenshots/a3-section2-search-get.png), [aggregations](screenshots/a3-section2-aggregations.png) |
