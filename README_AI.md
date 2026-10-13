# Beacon: AI system description

How Beacon gets data from a user to a language model and back safely. The model
choice is backed by the 15-model lab in
[`llm-test/ai_prototype.ipynb`](llm-test/ai_prototype.ipynb).

Beacon uses text AI for three jobs:

| Job | Where it appears | Code |
|---|---|---|
| **Coach advice:** this week's focus, three actions and a practice question, plus a question box | *My plan* | `preparation/coach.py` |
| **Grading written practice:** a STAR story, a pitch, or an explanation of what was read | Task workspace, `/me/tasks/<id>/` | `preparation/practice.py` |
| **Reading a resume:** skill evidence to pre-fill onboarding | Onboarding step 1 | `preparation/resume.py` |

```
 user input ──► Django view ──► validate & preprocess ──► prompt builder ──► LLM
 (form / upload)  (login, owner,    (trim, cap, strip PII,   (role, task,         │
                   CSRF checks)      build JSON context)      format, safety)      │
                                                                                   ▼
 page / JSON ◄── render safely ◄── validate the reply ◄────────────────────── raw text
                 (escaped text)    (JSON schema, ranges; on failure use rules fallback)
```

## 1. Data input: how user data is captured

All AI input comes from the signed-in user's own forms. Nothing is scraped and
nothing is collected in the background.

| Input | How it is captured | Stored? |
|---|---|---|
| Target roles, interview date or plan length, interests, experience, biggest worry | Onboarding form (`OnboardingForm`): choice fields and a date | Yes, on `CandidateProfile` |
| Self-rating per skill, 0-100 | Onboarding sliders, one per catalog skill | Yes, as `SkillAssessment` rows |
| Resume or LinkedIn "Save to PDF" | File upload (PDF or `.txt`) or pasted text, `POST /welcome/resume/` | **No.** Read in memory and discarded; only the suggestions it yields pre-fill the form |
| Practice answers | Text box in the task workspace | Yes, as `TaskAttempt.response` with the grade |
| Quiz answers | Radio buttons, graded by code, not by an LLM | Yes, as `TaskAttempt` |
| Questions to the coach | The *Ask your coach* box on *My plan*, sent as JSON | No |

Every one of these endpoints needs a login, rejects other users' data (another
user's task is a 404), and uses Django's CSRF protection.

## 2. Preprocessing: what happens before the LLM sees anything

**Validation first.** Django forms check types and ranges before any model is
called: ratings must be 0-100, an interview date must be in the future, at most
three roles may be chosen, and a written answer needs at least 15 words.
Anything that fails is returned to the user with a message, and the LLM is
never called.

**Size caps.** Every input is capped so a single request cannot run up cost or
latency:

| Input | Limit |
|---|---|
| Resume upload | 5 MB, the first 10 PDF pages, 60,000 characters of text |
| Written practice answer | 6,000 characters stored; the first 4,000 go to the grader |
| Coach question | 600 characters |

**Text extraction and cleanup.** PDFs are converted to plain text with `pypdf`.
Encrypted or unreadable files and scanned images with no text layer are
rejected with a clear message instead of being sent on.

**Structured context, not raw records.** The coach does not receive database
rows. `build_context()` assembles a small JSON object: target roles,
experience level, timeline, readiness percentage, each skill's self-rating
against the required level (sorted widest gap first), and this week's tasks.

**Personal data stripped.** That context deliberately leaves out the user's
name, username, email and resume text. The model only needs scores and goals,
and a test checks the outgoing request to prove these fields are absent.

**Instructions and user text kept apart.** The instructions live in the
system message, and the user's text travels separately, as a value inside a
JSON object (`{"answer": "…"}` for grading, the profile object for advice). It
is never pasted into the instructions. Each system prompt fixes the role, the
exact JSON output format and its length limits, and tells the model to judge
only the data given.

**Prompt layout validated in the lab.** The notebook's prompts use the full
production layout from class: Role, Task, Constraints, Output format, Safety
boundary, Length. In those prompts user text is also fenced in
`<data>…</data>` tags that the model is told to treat as data, never as
instructions. That is the layout we carry into the local-model integration.

**Rules-first where an LLM isn't needed.** Resume skill detection uses keyword
patterns, and quizzes have fixed answer keys. Those paths are deterministic,
free and instant, and they never touch an LLM.

## 3. Safety guardrails

### Malicious or abusive input

| Risk | Guardrail |
|---|---|
| **Prompt injection** ("ignore previous instructions…") inside an answer or resume | User text is sent as data, separate from the instructions. More importantly, the app only ever uses the model's reply as JSON in a fixed shape, validated field by field, so an injected instruction cannot make the app do anything new. At worst it produces a reply that fails validation and falls back to rules. The notebook's test T5 measures each candidate model's resistance, using `<data>` fencing. |
| Oversized or junk input | Length caps and minimum-content checks (above), applied before any model call |
| Unauthorised access | Login on every AI endpoint; queries filtered by owner, so anyone else's data is a 404; CSRF on every POST |
| Abuse and cost | Coach questions are limited to 20 per user per hour. Advice is cached for 6 hours per user, and keyed on their data, so it refreshes only when their scores or plan change. |
| Privacy | No name, email or resume text is sent to the model. Uploaded resumes are never written to disk. |

### Broken or untrustworthy output

| Risk | Guardrail |
|---|---|
| Reply isn't JSON, or has wrong or missing fields | The first `{…}` object is extracted and parsed; every required field is checked for type and range (for example, an integer `score` from 0 to 100). Anything else is rejected and never shown. |
| Model invents things | A `focus_skill` that isn't one of the user's real skills is discarded, and long strings are truncated. |
| Model is slow, rate-limited or down | A 25-second timeout. On the free tier, a busy reply (HTTP 402/429) is retried after a short wait. If the model still can't answer, Beacon falls back to its **rule-based** coach and grader, and the page says which one answered. |
| Output injecting HTML or script | Model text is rendered with `textContent`. Chat answers are HTML-escaped first and given only bold, italic and list formatting. |
| A grade being wrong | One attempt moves a skill rating only 40% of the way toward the score, so a single bad grade cannot swing readiness. Every attempt is stored with its before-and-after rating. |

### Configuration

The model and provider are set only in `.env` (`LLM_BASE_URL`, `LLM_MODEL`,
`LLM_API_KEY`), which is git-ignored, so no key is ever in the repository.
`LLM_ENABLED=false` switches every AI call to the rule-based fallback. The
test suite and CI run that way, so they never call a real model.
