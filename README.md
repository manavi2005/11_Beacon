# Beacon

**Walk into your next interview ready, for any career.**

Beacon is a personal interview coach. Tell it what you're working toward
(analytical chemist, ICU nurse, teacher, brand designer, software engineer,
anything) and it:

- **builds the blueprint** of skills that role's interviews actually test, with the bar for each;
- **practises you for ten minutes a day** with questions written fresh for you every time, graded with specific feedback and a stronger example answer;
- **remembers what you forget**: every skill fades on a forgetting curve, and Beacon brings it back just before you'd lose it (spaced repetition);
- **lets you rehearse out loud** with a mock interviewer that listens and follows up, then breaks your answers down by STAR and rewrites your weakest one in your own words;
- **talks it through** with you as a coach that knows your goal and your numbers;
- **stays a safe space**: private by default, no leaderboards, a gentle mode for rough days, streaks that forgive rest days, and reminders only if you ask for them.

Built by Manavi Chaudhry, Chu-Yun Hwang and Meet Kailash Mali.

---

## Run it

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-production.txt   # or requirements.txt to include the local model
cp .env.example .env                          # set DJANGO_SECRET_KEY and LUMEN_API_KEY
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000>, sign up, and type the role you're working toward.

### The AI provider

Every AI feature goes through one OpenAI-compatible endpoint configured in `.env`:

| Setting | Effect |
|---|---|
| `LUMEN_API_KEY` | Uses UIUC NCSA Lumen (`nemotron-3-super-120b-a12b` by default, `LLM_MODEL` to change). Recommended. |
| `LLM_API_KEY` + `LLM_BASE_URL` + `LLM_MODEL` | Any other OpenAI-compatible provider (Groq, OpenRouter, Hugging Face, Ollama). |
| neither | A free, keyless public model. Slower, but everything works. |
| `LLM_ENABLED=false` | No AI at all. Every feature falls back to transparent, field-neutral rules, which is how the tests run. |

Keys live only in `.env`, which git ignores.

### Daily reminders

Reminders are opt-in per user (under **You**). Schedule this once a day:

```bash
python manage.py send_reminders
```

Set `SITE_URL` and the `EMAIL_*` values in `.env` for real delivery; development prints emails to the console.

---

## How it's built

Django 5, server-rendered pages, vanilla JS, no build step.

```
studio/          the product (v2)
  blueprint.py     role -> skills and the bar for each, cached per role (any field)
  engine.py        readiness, today's queue, forecast, forgiving streaks, XP
  models.py        SkillMemory holds the forgetting curve: due at 85% recall
  cards.py         fresh questions per person and skill; grading with feedback
  interview.py     mock interviewer turns and the STAR report
  chat.py          the coach, grounded in the person's own progress
  reminders.py     opt-in daily nudges
preparation/     the original data model (profiles, skills, assessments, plans),
                 public API, charts and the coach/cohort views
templates/studio, static/studio   the design system and pages
research/        model-selection labs, multi-model cost analysis, small-LM study
docs/            AI system design, public API, deployment, course history
```

Every AI call has a fallback, and every model reply is validated before it is
shown: JSON schemas, score ranges, and HTML escaped with only bold and
bullets allowed. Candidate text is passed to models as data, with instructions
never to follow commands inside it.

## Tests

```bash
LLM_ENABLED=false LOCAL_LLM_ENABLED=false python manage.py test
```

CI runs the same on every push.

## More

- [How the AI features work](docs/ai-system.md)
- [Public API](docs/public-api/README.md)
- [Deploying](docs/deployment/DEPLOY.md)
- [Course history and assignment documentation](docs/course-history.md)
