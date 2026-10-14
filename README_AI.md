# Beacon: AI system description

How Beacon gets data from a user to a language model and back safely. The model
choice is backed by the 15-model lab in
[`llm-test/ai_prototype.ipynb`](llm-test/ai_prototype.ipynb).

Beacon uses text AI for four jobs, across two engines: a hosted chat API
reached over HTTP, and a Hugging Face model whose weights this process loads
itself with `transformers`.


| Job | Where it appears | Code |
|---|---|---|
| **Coach advice:** this week's focus, three actions and a practice question, plus a question box | *My plan* | `preparation/coach.py` |
| **Grading written practice:** a STAR story, a pitch, or an explanation of what was read | Task workspace, `/me/tasks/<id>/` | `preparation/practice.py` |
| **Reading a resume:** skill evidence to pre-fill onboarding | Onboarding step 1 | `preparation/resume.py` |
| **Screening written practice before grading:** on topic, substantive, provisional score | Task workspace, on submit and on `POST /me/tasks/<id>/screen/` | `preparation/local_llm.py` (local weights) |

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

## 4. The local model

`preparation/local_llm.py` holds a Hugging Face model in this process through
the `transformers` library. The weights download themselves into the Hugging
Face cache the first time an answer is screened, so a fresh checkout needs
nothing beyond `pip install -r requirements.txt`.

**What it does.** It screens a written practice answer before the hosted model
is asked to write feedback on it: the hybrid shape the assignment describes,
where the local model filters and the API generates. It returns three fields,
`on_topic`, `substantive` and a provisional `score`. An answer that is off
topic or has no real content stops there and never costs an API call, which is
exactly the input the hosted model would have had nothing to work with on. An
injection attempt is caught before it reaches the larger model.

**Which model, and why.** `Qwen/Qwen2.5-1.5B-Instruct`, the budget
recommendation from the lab in `llm-test/ai_prototype.ipynb`. It returned
valid JSON on every matrix task and placed a weak answer correctly where
several larger models did not, at about a third of the memory of the 4B tier.
Screening is a narrow classification job, so the lab's quality-first pick
would buy accuracy this task does not need. `LOCAL_LLM_MODEL` swaps it for any
other model from the lab without a code change.

**Prompting.** Few-shot with three graded demonstrations, which is what the
lab's Route A comparison found for this size of model: examples did not fix
output format, because format was already reliable at zero-shot. What they
fixed was judgement, taking the smaller models from 50% to 83% correct at no
extra latency.

**Measured on an M4 Pro, model already cached:** about 5 seconds for the first
call including the load, then 0.7 to 1.4 seconds per screen. Generation is
deterministic (`do_sample=False`), so resubmitting the same text cannot move a
rating for no reason.

**Loading.** Never at import. A module-level import of `transformers` would
make every management command and the whole test suite pay for torch, so the
pipeline is built on first real use, behind a lock because the development
server is threaded, and reused for the life of the process. A load failure is
remembered rather than retried, so a machine without the weights does not
restart a slow download on every request.

**What happens when it is not there.** Nothing breaks. `LOCAL_LLM_ENABLED` is
off in production and in CI, a missing or unloadable model is caught and
treated as "no screening", and grading carries on through the hosted coach
exactly as it did before this existed. `manage.py test` forces it off, so no
test run can start a multi-gigabyte download by accident.

**Honest limitation.** The screener is lenient on thin answers. Asked to judge
"I worked on a group project once and there were some problems but we fixed
them", it answered `substantive: true` with a score of 73. That is the same
leniency the lab measured in task T3 for models of this size, and it is why
the provisional score is only ever used as a fallback and never to overrule
the hosted model's grade. The failure direction is the safe one: a thin answer
passes the screen and is then graded properly by the larger model, rather than
being wrongly rejected.

## 5. Configuration

The model and provider are set only in `.env` (`LLM_BASE_URL`, `LLM_MODEL`,
`LLM_API_KEY`), which is git-ignored, so no key is ever in the repository.
`LLM_ENABLED=false` switches every AI call to the rule-based fallback. The
test suite and CI run that way, so they never call a real model.

The local model is configured the same way and needs no key, because there is
no account behind it: `LOCAL_LLM_ENABLED` to switch it off, `LOCAL_LLM_MODEL`
to point it at a different Hugging Face model, `LOCAL_LLM_DEVICE` to pin it to
`cuda`, `mps` or `cpu` on a machine where the default choice is wrong.

`GET /api/local-model/` reports whether it is on, which model is configured
and whether the weights have loaded yet, without triggering a download. It is
the quickest way to tell a misconfigured deployment from a slow one.

Two requirements files, because `torch` and `transformers` come to about
2.5 GB installed before any weights, and PythonAnywhere's free tier allows
512 MB in total:

| File | For | Contains |
|---|---|---|
| `requirements.txt` | Local development, and the grader's machine | Everything, including `torch`, `transformers` and `accelerate` |
| `requirements-production.txt` | A small host such as PythonAnywhere | The same list without those three |
