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

Requires Python 3.11 and about 1 GB of disk for the Python packages, plus model downloads (below).

```bash
git clone https://github.com/manavi2005/11_Beacon.git && cd 11_Beacon
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # includes torch, transformers, sentence-transformers
cp .env.example .env                # then set DJANGO_SECRET_KEY (and optionally an AI key, below)
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000>, sign up, and type the role you're working toward. To skip setup, `python manage.py seed_demo_data` adds demo accounts (see `preparation/management/commands/seed_demo_data.py`).

`requirements-production.txt` is the same list without torch and transformers, for small hosts: everything still works, Ask Beacon uses keyword search, and answer screening is skipped.

### Using the AI features

| Feature | Where | Try |
|---|---|---|
| **Ask Beacon** (retrieval over Beacon's guide, local embeddings) | **Ask** in the side bar, `/ask/` | "How is my readiness percentage calculated?" |
| Practice questions and grading | **Practice**, `/session/` | Answer a question; feedback appears under it |
| Mock interview with a STAR report | **Interview**, `/interview/` | Speak or type answers |
| Coach chat | **Coach**, `/coach/` | "What should I focus on this week?" |
| Resume reading and role suggestions | Setup, `/start/` | Upload a PDF resume |

How each one works, the model choices and the evaluation are in **[README_AI.md](README_AI.md)**. To re-run the evaluation: `python manage.py evaluate_ask`.

### Models and downloads

No model weights are in the repository (`.gitignore` excludes `*.bin`, `*.safetensors`, `*.pt`, `*.pth`). Models download from Hugging Face into `~/.cache/huggingface` on first use:

| Model | Used for | Size | When it downloads |
|---|---|---:|---|
| `BAAI/bge-small-en-v1.5` | Ask Beacon embeddings | ~130 MB | First question on `/ask/` (about 5 s to build the index) |
| `Qwen/Qwen2.5-1.5B-Instruct` | Local answer screening in the weekly-plan tasks | ~3 GB | First screened answer; set `LOCAL_LLM_ENABLED=false` to skip |

Text generation uses an open-weight model through one OpenAI-compatible endpoint configured in `.env`:

| Setting | Effect |
|---|---|
| `LUMEN_API_KEY` | UIUC NCSA Lumen, `nemotron-3-super-120b-a12b` (free for the university). Recommended locally. |
| `LLM_API_KEY` | Groq's free tier, `openai/gpt-oss-120b` by default (`LLM_BASE_URL` and `LLM_MODEL` point it anywhere OpenAI-compatible, e.g. Ollama at `http://localhost:11434/v1`). |
| neither | A free keyless public endpoint serving `gpt-oss-20b`. Slower, but everything works. |
| `LLM_ENABLED=false` | No AI. Every feature falls back to transparent rules, which is how the tests run. |

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
  engine.py        readiness, forecast, streaks, XP, and the ranking: one
                   scoring function orders today's skills (urgency, gap, market
                   demand, cohort difficulty with Bayesian shrinkage, exploration)
  models.py        SkillMemory holds the forgetting curve: due at 85% recall
  cards.py         fresh questions per person and skill; grading with feedback
  interview.py     mock interviewer turns and the STAR report
  chat.py          the coach, grounded in the person's own progress
  knowledge/       Ask Beacon: guide, chunking, local embeddings, BM25, cited answers
  reminders.py     opt-in daily nudges
support/         staff console: diagnosis and fixes per person, problem
                 reports, error log, append-only audit trail (/staff/)
beacon_core/security.py   rate limits, brute-force lockout, CSP and headers
preparation/     the original data model (profiles, skills, assessments, plans),
                 public API, charts and the coach/cohort views
templates/studio, static/studio   the design system and pages
research/        model-selection lab, multi-model cost analysis, small-LM study, RAG study
docs/            AI system design, public API, deployment, project history
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

- [How the AI works: workflow, models, evaluation](README_AI.md)
- [Prompting and output validation in detail](docs/ai-system.md)
- [Public API](docs/public-api/README.md)
- [Deploying](docs/deployment/DEPLOY.md)
- [Security and abuse protection](docs/security.md)
- [Project history](docs/project-history.md)
