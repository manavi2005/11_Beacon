# Beacon — Data Model Design Notes

**Project 1, Part 4 · Team Career Coaches (Group 11)**

This file answers the "documented and justified" requirements of Part 4: why the
project and app are named what they are, why there are five models, why each
relationship uses the `on_delete` behaviour it does, and what each constraint
protects against.

---

## 1. Naming decisions

| Name | Type | Why |
|---|---|---|
| `Beacon` | repo / project root | Product name from our Part-3 idea description. A beacon guides someone through fog, which is what the app does for a first job search. |
| `beacon_core` | `startproject` folder | This folder holds **no features** — only settings, routing and WSGI/ASGI entry points. Calling it `beacon` would shadow the repo folder name and make imports ambiguous; `_core` communicates "control centre". |
| `preparation` | `startapp` folder | The app owns one bounded domain: everything about *preparing* for an interview — diagnosing skills, generating a plan, tracking progress. Django app names are lowercase and describe a domain, not a layer, so `preparation` rather than `main` or `app1`. |
| `templates/preparation/` | template folder | Mirrors the app name so Django's template loader never confuses two apps' `dashboard.html`. |

**How this scales to the team.** Part 4 asks for one working app. As we build
features, each teammate gets their own app folder next to `preparation`, each with
its own `models.py`, `views.py`, `urls.py` and `templates/` sub-folder:

| Feature (from our idea description) | Planned app |
|---|---|
| Resume & goal identification | `profiles` |
| Skills diagnosis (adaptive quiz) | `diagnostics` |
| Plan generator | `preparation` (this one) |
| Progress tracker | `progress` |

That way two people never edit the same file, which is the division of labour the
assignment describes. With a three-person team and four feature areas, one area is
currently shared rather than owned — see
[`branching_strategy/README.md`](branching_strategy/README.md#who-owns-what).

---

## 2. Why these five models

We started from the four features in our Part-3 paper and asked: *what nouns does
this product actually store?*

| Feature | Noun | Model |
|---|---|---|
| "Transfers the user's resume into a skill list… dream company and job position" | the candidate's goal | `CandidateProfile` |
| "Assesses the candidate's skill proficiency with a short, self-adaptive quiz" | the thing being assessed | `Skill` |
| | the result of the assessment | `SkillAssessment` |
| "Builds a customized plan and practical roadmap" | the roadmap | `PreparationPlan` |
| "Tracks the preparation plan and iteratively updates strategies" | the trackable unit | `PlanTask` |

Two design decisions are worth defending in the demo:

**Why `Skill` is its own table rather than a text field on the assessment.**
If skills were free text, "Python", "python3" and "Py" would be three different
things and Beacon could never say "candidates targeting this role usually need
X". A shared catalog is what makes gap analysis and plan generation possible.

**Why `CandidateProfile` is separate from `User`.**
`django.contrib.auth.User` answers *who is logged in*: username, password, email.
`CandidateProfile` answers *what is this person preparing for*: target role,
target company, interview date, resume. Those change for entirely different
reasons. Keeping them apart means we never have to subclass or replace Django's
auth model as our product questions evolve — a `OneToOneField` is the standard
Django way to extend a user.

**Why `SkillAssessment` is a `through` model.**
`CandidateProfile.skills` is declared as
`ManyToManyField(Skill, through="SkillAssessment")`. A candidate is related to a
skill *only* by way of a score and a date. Using a plain M2M would have created a
join table with no room for `proficiency_score`, and we would have needed a second
table anyway.

---

## 3. `on_delete` justification

Every foreign key had to answer: *if the parent disappears, is the child still
meaningful?*

| Relationship | Behaviour | Reasoning |
|---|---|---|
| `CandidateProfile.user → User` | `CASCADE` | A career profile with no account behind it is orphaned data. Deleting the account must delete the profile (also the right behaviour for a data-deletion request). |
| `SkillAssessment.candidate → CandidateProfile` | `CASCADE` | Scores belong to the person. Without the profile, a row saying "72/100" identifies nobody. |
| `SkillAssessment.skill → Skill` | `PROTECT` | An admin tidying the skill catalog must not be able to silently destroy scored history. `PROTECT` forces them to reassign or delete the assessments deliberately first. This is the one place we chose safety over convenience. |
| `PreparationPlan.candidate → CandidateProfile` | `CASCADE` | Same logic as assessments: a plan exists for exactly one person. |
| `PlanTask.plan → PreparationPlan` | `CASCADE` | Tasks are *parts of* a plan, not independent objects. Deleting a plan should not leave 24 homeless tasks behind. |
| `PlanTask.skill → Skill` | `SET_NULL` | Here the tag is descriptive, not structural. "Practise 10 array problems" is still a valid task even if the *Data structures* skill is retired from the catalog, so we keep the task and drop the label. This is why the field is `null=True, blank=True`. |

The contrast between `SkillAssessment.skill` (`PROTECT`) and `PlanTask.skill`
(`SET_NULL`) is deliberate: **data about the past is protected, labels on future
work are disposable.**

---

## 4. Constraints and what they prevent

| Constraint | Prevents |
|---|---|
| `uniq_skill_name_per_category` (Skill) | Two "SQL" rows in the technical category, which would split one skill's history across two IDs. Scoped to category so "Storytelling" can legitimately exist as both a behavioural and a communication skill. |
| `uniq_assessment_per_candidate_skill` (SkillAssessment) | Duplicate scores for the same candidate and skill. Re-taking the quiz must **update** the row; otherwise "current proficiency" becomes ambiguous. |
| `uniq_plan_title_per_candidate` (PreparationPlan) | Two plans called "4-week sprint" for the same user — the user could not tell them apart in a list. Scoped to the candidate, since different users may reuse the same title. |
| `uniq_task_title_per_plan` (PlanTask) | The generator emitting the same task twice into one plan. |
| `scores_within_0_100` (CheckConstraint) | A gap calculation between numbers on different scales. Validators alone only run in forms; a `CheckConstraint` is enforced by the database itself. |
| `plan_ends_after_it_starts` (CheckConstraint) | A plan whose deadline precedes its start date, which would make every schedule calculation negative. |

`Meta.ordering` is set on all five models so lists are deterministic without every
view remembering to sort — plans by soonest deadline, tasks by priority then due
date, assessments newest first, skills grouped by category, profiles by most
recently updated.

---

## 5. Validation evidence

`python manage.py verify_constraints` runs eight checks and prints PASS/FAIL for
each; the saved output is in `docs/constraint_validation.txt`. Every check runs
inside a transaction that is rolled back, so running it never mutates the
submitted database. The checks cover both required demonstrations from the
assignment — "attempting to insert a duplicate record should fail" and "deleting a
parent record removes or blocks related records depending on your design".

---

## 6. Known limitations and next steps

- No plan-generation integration yet. `PreparationPlan.generated_by_ai` is the
  flag that will distinguish generated plans from hand-written ones once the
  generator is wired up; its API key will live in `.env`, never in the repo.
- Assessments store only the *current* score. If we later want a progress graph
  over time, we would add an `AssessmentHistory` table rather than relax the
  uniqueness constraint.
- No mock-interview, feedback or quiz-question models yet (see section 7).
- `PlanTask.completed_on` is set by hand today. It should be set automatically
  when `status` changes to `DONE`, via a `save()` override or a signal.

---

## 7. Alignment with the Part-3 wireframes

The wireframe deck defines five screens. Here is exactly what the data model
covers today and what it deliberately does not.

| Screen | Backed by | Status |
|---|---|---|
| 1. Career Goal & Resume Setup | `CandidateProfile` — `resume_file`, `resume_summary`, `target_role`, `target_company`, `target_interview_date`, `preparation_timeline_weeks`, `primary_concern` | Complete |
| 2. AI Skill Assessment | `Skill`, `SkillAssessment` store the **result** of the quiz | Partial — see below |
| 3. Personalized Roadmap | `PreparationPlan` (+ `total_weeks`, `current_week`, `candidate.readiness_percent`), `PlanTask.week_number`, `PlanTask.rationale` | Complete |
| 4. Progress & Practice | `PreparationPlan.completion_percent`, `SkillAssessment.proficiency_score` / `gap`, `PlanTask.estimated_minutes` / `status` / `rationale` | Complete |
| 5. AI Mock Interview & Feedback | nothing yet | Not modelled — see below |

**Screen 3 mapping in detail.** "Overall Readiness" is
`CandidateProfile.readiness_percent`, a derived average of proficiency against
required level — stored nowhere, so it can never go stale. The six-week timeline
comes from `PlanTask.week_number`; the Completed / Current / Upcoming state of
each row is a comparison against `PreparationPlan.current_week`, so one number
drives all three states. "Why these recommendations?" and the reason text on the
recommended-next card both read `PlanTask.rationale`.

**Screen 2 — the deliberate gap.** The quiz *questions* have no tables yet:
there is no `AssessmentQuestion`, `AnswerOption` or `QuestionResponse`. Today
Beacon can record that a candidate scored 72 on SQL, but not the ten questions
that produced that number. Part 4 recommends 3–5 models total and advises
starting small, so we modelled the assessment **outcome** — which is what the
roadmap and progress screens actually read — and left the question bank for the
part where the quiz is built. Adding it later is additive: `SkillAssessment`
gains a reverse relation and no existing field changes.

**Screen 5 — the deliberate gap.** Mock interviews need their own app
(`mock_interviews`) with roughly four models: a session, its questions, the
candidate's responses, and a feedback record holding the overall score, category
scores, strengths and areas to improve. Building it now would put the project at
eleven models before a single view exists. It is scoped as one teammate's
feature for a later part, and it attaches to the existing model cleanly through
a foreign key to `CandidateProfile`.

**A documentation inconsistency we are tracking.** The Part-3 paper lists four
features; the wireframes show five, because mock interviews were added during
design. Both documents should agree before the next submission — either the paper
gains a fifth proposed feature, or the mock-interview screen is described as an
extension of the practice feature.
