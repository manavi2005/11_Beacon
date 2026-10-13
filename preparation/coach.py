"""Beacon's AI coach: personal recommendations and a question box.

Two engines behind one interface, so the page never breaks:

  LLM    any OpenAI-compatible chat API, configured entirely from .env.
         With no key it uses Pollinations' free anonymous tier (OpenAI's
         open-weight gpt-oss-20b, no account needed); with LLM_API_KEY set
         it uses LLM_BASE_URL / LLM_MODEL, by default Groq's free tier with
         open-weight Llama 3.3 70B. Both are on PythonAnywhere's outbound
         allowlist, so it works on the deployed site with no local model. Swapping provider later - Hugging
         Face, OpenRouter, Together, a self-hosted vLLM or Ollama - is a
         change of those three settings, not of this code, because they all
         speak the same /chat/completions API.

  Rules  the deterministic coach: widest gap first, concrete tasks, a
         practice question from a small bank. Used when LLM_ENABLED is off,
         when the LLM is slow, rate-limited or down, or when its answer fails validation. It is
         also what CI and the test suite run against.

Privacy: the LLM sees the candidate's target roles, experience level,
timeline, skill scores and plan - the things a coach needs - and never their
name, username, email or resume text (build_context leaves them out, and a
test checks the outgoing request).

Cost and abuse: advice is cached per user for six hours (keyed on their data,
so it refreshes when their scores or progress change), and questions are
limited per user per hour.
"""

import hashlib
import json
import re
import time

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import PlanTask, PreparationPlan
from .onboarding import INTERESTS, TASKS_BY_SKILL

ADVICE_TTL = 6 * 60 * 60
FAILURE_TTL = 2 * 60
ASKS_PER_HOUR = 20
MAX_QUESTION = 600
TIMEOUT_SECONDS = 25
RETRY_WAIT_SECONDS = 5

# One strong practice question per skill, for the rules engine.
QUESTION_BANK = {
    "Data structures & algorithms": "Given an array of numbers, return the two that add up to a target. Talk through brute force first, then improve it.",
    "SQL & relational modeling": "Write a query that returns each customer's most recent order. How would you handle ties?",
    "Python fundamentals": "What is the difference between a list and a generator, and when would you choose each?",
    "System design basics": "Design a URL shortener. Where does it break first as traffic grows?",
    "Version control with Git": "Walk me through resolving a merge conflict on a shared branch.",
    "STAR-format storytelling": "Tell me about a time you had to deliver results with an unclear goal.",
    "Handling failure questions": "Tell me about a project that failed. What would you do differently?",
    "Negotiating an offer": "The recruiter asks for your salary expectation. What do you say?",
    "Product sense": "How would you improve the app you use most every day? Who is it for, and how would you measure success?",
    "Financial markets basics": "Explain what moves a bond's price when interest rates rise.",
    "Whiteboard communication": "Explain a project you built to someone non-technical in two minutes.",
    "Resume & elevator pitch": "Tell me about yourself, in under 90 seconds.",
}
DEFAULT_QUESTION = "Tell me about a time you learned something difficult quickly."


class CoachError(Exception):
    pass


class CoachBusy(CoachError):
    """The provider is rate-limiting us (HTTP 402/429). On the free keyless
    tier that means 'one request every few seconds', not a real failure."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def llm_config():
    """Which model to call: the keyed provider if a key is set, otherwise the
    free keyless tier. See the AI coach block in settings/base.py."""
    key = getattr(settings, "LLM_API_KEY", "")
    if key:
        return {
            "base_url": getattr(settings, "LLM_BASE_URL", "").rstrip("/"),
            "model": getattr(settings, "LLM_MODEL", ""),
            "label": getattr(settings, "LLM_MODEL", ""),
            "key": key,
            "provider": getattr(settings, "LLM_PROVIDER", "LLM"),
            "keyless": False,
        }
    return {
        "base_url": getattr(settings, "LLM_KEYLESS_BASE_URL", "").rstrip("/"),
        "model": getattr(settings, "LLM_KEYLESS_MODEL", ""),
        "label": getattr(settings, "LLM_KEYLESS_LABEL", ""),
        "key": "",
        "provider": getattr(settings, "LLM_KEYLESS_PROVIDER", "free tier"),
        "keyless": True,
    }


def llm_enabled():
    cfg = llm_config()
    return bool(getattr(settings, "LLM_ENABLED", True) and cfg["base_url"] and cfg["model"])


def engine_label():
    cfg = llm_config()
    if llm_enabled():
        return f"AI · {cfg['label'] or cfg['model']} via {cfg['provider']}"
    return "Beacon rules (AI switched off)"


# ---------------------------------------------------------------------------
# What the coach knows about you (and nothing more)
# ---------------------------------------------------------------------------
def build_context(profile):
    """Everything the coach needs, nothing that identifies the person."""
    today = timezone.localdate()
    assessments = sorted(
        profile.assessments.select_related("skill"),
        key=lambda a: a.required_level - a.proficiency_score,
        reverse=True,
    )
    plan = (
        profile.plans.filter(status=PreparationPlan.Status.ACTIVE).order_by("-created_at").first()
        or profile.plans.order_by("-created_at").first()
    )
    tasks = list(plan.tasks.select_related("skill").order_by("week_number", "pk")) if plan else []
    this_week = plan.current_week if plan else 1
    return {
        "target_roles": profile.target_roles or [profile.target_role],
        "experience": profile.get_experience_level_display(),
        "biggest_worry": profile.get_primary_concern_display() or None,
        "interests": [INTERESTS[k][0] for k in (profile.interests or []) if k in INTERESTS],
        "timeline": (
            f"interview in {(profile.target_interview_date - today).days} days"
            if profile.target_interview_date
            else f"no interview booked; {profile.preparation_timeline_weeks}-week open-ended plan"
        ),
        "readiness_percent": profile.readiness_percent,
        "skills": [
            {
                "skill": a.skill.name,
                "self_rating": a.proficiency_score,
                "required": a.required_level,
                "gap": a.required_level - a.proficiency_score,
            }
            for a in assessments
        ],
        "plan": {
            "week": this_week,
            "of_weeks": plan.total_weeks if plan else 0,
            "tasks_done": sum(t.status == PlanTask.Status.DONE for t in tasks),
            "tasks_total": len(tasks),
            "this_week": [
                {"task": t.title, "done": t.status == PlanTask.Status.DONE}
                for t in tasks if t.week_number == this_week
            ],
        },
    }


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------
def rule_advice(ctx):
    gaps = [s for s in ctx["skills"] if s["gap"] > 0]
    plan = ctx["plan"]
    if not gaps:
        return {
            "headline": "You meet the bar on every skill you rated.",
            "focus_skill": None,
            "why": "Nothing is below what your target roles require. Keep sharp with mock interviews.",
            "actions": [
                "Do one full mock interview this week and record it.",
                "Ask a friend to grill you on your two strongest stories.",
                "Consider a more senior target role to stretch further.",
            ],
            "practice_question": DEFAULT_QUESTION,
            "encouragement": "Strong position. Stay consistent rather than cramming.",
        }
    focus = gaps[0]
    tasks = [t for t, _ in TASKS_BY_SKILL.get(focus["skill"], [])][:2]
    next_gap = gaps[1]["skill"] if len(gaps) > 1 else None
    actions = tasks + ([f"Then start on {next_gap}, your next-widest gap."] if next_gap else [])
    done, total = plan["tasks_done"], plan["tasks_total"]
    if total and done == 0:
        cheer = "Start small: tick off one task today and the plan gets easier from there."
    elif total and done < total:
        cheer = f"{done} of {total} tasks done. Keep the streak going this week."
    else:
        cheer = "You've cleared your plan. Retake the diagnosis to measure the progress."
    return {
        "headline": f"This week, focus on {focus['skill']}.",
        "focus_skill": focus["skill"],
        "why": (
            f"You rated it {focus['self_rating']}; your target expects {focus['required']}. "
            f"At {focus['gap']} points it is your widest gap, so it moves your readiness most."
        ),
        "actions": actions[:3],
        "practice_question": QUESTION_BANK.get(focus["skill"], DEFAULT_QUESTION),
        "encouragement": cheer,
    }


def rule_answer(ctx, question):
    advice = rule_advice(ctx)
    return (
        "The AI coach isn't available right now, so here is what your plan says. "
        f"{advice['headline']} {advice['why']} Next: {advice['actions'][0] if advice['actions'] else ''}"
    )


# ---------------------------------------------------------------------------
# LLM engine
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Beacon, a warm, direct career coach for students and early-career "
    "candidates preparing for job interviews. You are given a JSON profile: "
    "target roles, timeline, self-rated skills (0-100) against what the roles "
    "require, and their current preparation plan. Ground every recommendation "
    "in that data - name the specific skill and numbers. Be concrete and brief. "
    "Never invent facts about the person beyond the profile."
)

ADVICE_INSTRUCTIONS = (
    "Reply with only a JSON object with these keys: "
    '"headline" (one sentence, what to focus on this week), '
    '"focus_skill" (exactly one skill name from the profile, or null), '
    '"why" (one or two sentences using their numbers), '
    '"actions" (a list of exactly 3 short, concrete actions for this week), '
    '"practice_question" (one realistic interview question for the focus skill), '
    '"encouragement" (one sentence, specific to their progress).'
)


def _chat(messages, *, json_mode=False, max_tokens=600, patient=False):
    """One chat completion. patient=True (used for grading, which the user is
    actively waiting on) retries a busy free tier twice, after 6 and 10 s."""
    cfg = llm_config()
    body = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {}
    # The free keyless tier allows roughly one request every few seconds per
    # server, and says so with 402/429. One short wait and retry covers the
    # common case of two requests close together (advice, then a question).
    waits = ([6, 10] if patient else [RETRY_WAIT_SECONDS]) if cfg["keyless"] else []
    attempts = len(waits) + 1
    for attempt in range(attempts):
        try:
            response = requests.post(
                f"{cfg['base_url']}/chat/completions",
                json=body,
                headers=headers,
                timeout=TIMEOUT_SECONDS + (15 if cfg["keyless"] else 0),
            )
            if response.status_code in (402, 429):
                if attempt + 1 < attempts:
                    time.sleep(waits[attempt])
                    continue
                raise CoachBusy("The free AI model is busy right now.")
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except CoachBusy:
            raise
        except requests.Timeout as exc:
            raise CoachError("The AI coach took too long to answer.") from exc
        except requests.HTTPError as exc:
            raise CoachError(f"The AI provider returned HTTP {exc.response.status_code}.") from exc
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise CoachError("The AI coach could not be reached.") from exc
    raise CoachBusy("The free AI model is busy right now.")


def _parse_advice(text, ctx):
    """Validate the model's JSON. Anything off-spec is rejected, not shown."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise CoachError("The AI answer was not JSON.")
    try:
        data = json.loads(match.group(0))
    except ValueError as exc:
        raise CoachError("The AI answer was not valid JSON.") from exc

    def text_field(key, limit):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise CoachError(f"The AI answer had no {key}.")
        return value.strip()[:limit]

    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        raise CoachError("The AI answer had no actions.")
    skill_names = {s["skill"] for s in ctx["skills"]}
    focus = data.get("focus_skill")
    return {
        "headline": text_field("headline", 200),
        "focus_skill": focus if focus in skill_names else None,
        "why": text_field("why", 400),
        "actions": [str(a).strip()[:200] for a in actions if str(a).strip()][:3],
        "practice_question": text_field("practice_question", 300),
        "encouragement": text_field("encouragement", 200),
    }


def llm_advice(ctx):
    content = _chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ADVICE_INSTRUCTIONS + "\n\nProfile:\n" + json.dumps(ctx)},
        ],
        json_mode=True,
    )
    return _parse_advice(content, ctx)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
def _cache_key(user_id, ctx):
    digest = hashlib.sha256(json.dumps(ctx, sort_keys=True).encode()).hexdigest()[:16]
    return f"coach:advice:{user_id}:{digest}"


def get_advice(profile, *, refresh=False):
    """{"advice": {...}, "engine": "...", "source": "llm"|"rules", "note": str|None}"""
    ctx = build_context(profile)
    key = _cache_key(profile.user_id, ctx)
    if not refresh:
        cached = cache.get(key)
        if cached:
            return cached

    result = {"advice": None, "engine": engine_label(), "source": "rules", "note": None}
    if llm_enabled():
        try:
            result["advice"] = llm_advice(ctx)
            result["source"] = "llm"
        except CoachError as exc:
            result["note"] = f"{exc} Showing Beacon's rule-based advice instead."
            result["engine"] = "Beacon rules (fallback)"
    if result["advice"] is None:
        result["advice"] = rule_advice(ctx)
    # Cache successes for hours. Cache a fallback briefly too, so that every
    # visit to My plan does not spend the free tier's small request budget
    # retrying a model that just said it was busy.
    cache.set(key, result, ADVICE_TTL if result["source"] == "llm" else FAILURE_TTL)
    return result


def _allow_question(user_id):
    key = f"coach:asks:{user_id}:{timezone.now():%Y%m%d%H}"
    count = cache.get(key, 0)
    if count >= ASKS_PER_HOUR:
        return False
    cache.set(key, count + 1, 60 * 60)
    return True


def ask(profile, question):
    """{"answer": str, "engine": str, "source": "llm"|"rules"|"limit"}"""
    question = (question or "").strip()[:MAX_QUESTION]
    ctx = build_context(profile)
    if not question:
        return {"answer": "Ask me anything about your preparation.", "engine": engine_label(), "source": "rules"}
    if not llm_enabled():
        return {"answer": rule_answer(ctx, question), "engine": engine_label(), "source": "rules"}
    if not _allow_question(profile.user_id):
        return {
            "answer": f"That's {ASKS_PER_HOUR} questions this hour - take a break and try again soon.",
            "engine": engine_label(), "source": "limit",
        }
    try:
        answer = _chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT + (
                    " Answer the candidate's question in under 150 words. If they share "
                    "a practice answer, give feedback: what worked, what to tighten, and "
                    "whether it follows STAR (Situation, Task, Action, Result)."
                )},
                {"role": "user", "content": "Profile:\n" + json.dumps(ctx)
                    + "\n\nQuestion:\n" + question},
            ],
            max_tokens=400,
        )
        return {"answer": answer.strip(), "engine": engine_label(), "source": "llm"}
    except CoachBusy:
        return {
            "answer": ("The free AI model is busy right now - it serves one request every "
                       "few seconds. Try again in about 15 seconds."),
            "engine": engine_label(), "source": "busy",
        }
    except CoachError as exc:
        return {
            "answer": f"{exc} " + rule_answer(ctx, question),
            "engine": "Beacon rules (fallback)", "source": "rules",
        }
