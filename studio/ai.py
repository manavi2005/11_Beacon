"""One way to ask the configured model for JSON, shared by every v2 feature.

The provider is whatever preparation/coach.py is configured for (Lumen when
LUMEN_API_KEY is set). Every caller has a rules fallback, so a missing key,
a slow model or malformed JSON degrades the experience but never breaks it.
"""

import json
import re

from django.core.cache import cache

from preparation import coach

Unavailable = coach.CoachError

# Circuit breaker: when the provider can't be reached at all (network
# blocked, outage, bad key), stop trying for a few minutes so every page
# falls back to the offline coach at once instead of waiting on a timeout.
DOWN_KEY = "studio:ai-down"
DOWN_SECONDS = 300
# A single slow reply is not an outage, so timeouts don't trip it.
_UNREACHABLE = ("could not be reached", "HTTP 401", "HTTP 403", "HTTP 404", "HTTP 5")

# Slow mode: after a timeout or a rate-limit refusal, interactive features
# (the next practice question, grading, the mock interviewer's next line) use
# their instant offline versions for a couple of minutes instead of making
# someone wait out another slow call. Setup and reports still try the model.
SLOW_KEY = "studio:ai-slow"
SLOW_SECONDS = 120
_SLOW = ("took too long", "busy")

# Seconds an interactive action may spend on the model, retries included.
BUDGETS = {"card": 20, "grade": 25, "interview": 20, "report": 45, "chat": 30,
           "about": 40, "blueprint": 100}


def enabled():
    return coach.llm_enabled() and not cache.get(DOWN_KEY)


def slow():
    return bool(cache.get(SLOW_KEY))


def _call(**kwargs):
    try:
        return coach._chat(**kwargs)
    except coach.CoachError as exc:
        if any(marker in str(exc) for marker in _UNREACHABLE):
            cache.set(DOWN_KEY, str(exc), DOWN_SECONDS)
        elif any(marker in str(exc) for marker in _SLOW):
            cache.set(SLOW_KEY, str(exc), SLOW_SECONDS)
        raise


def label():
    return coach.engine_label()


def _ready(interactive):
    if not enabled():
        raise Unavailable("AI is switched off.")
    if interactive and slow():
        raise Unavailable("The AI is slow right now; using the instant version.")


def ask_json(system, user, *, max_tokens=6000, timeout=60, temperature=0.6,
             budget=None, interactive=False):
    """Return the model's reply parsed as a JSON object, or raise Unavailable.

    interactive=True for actions someone is actively waiting on: they skip
    the model while it is in slow mode and fall back at once."""
    _ready(interactive)
    text = _call(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True, max_tokens=max_tokens, patient=True, timeout=timeout,
        temperature=temperature, budget=budget,
    )
    return parse_json(text)


def ask_text(system, messages, *, max_tokens=3000, timeout=45, temperature=0.7,
             budget=None, interactive=False):
    _ready(interactive)
    return _call(
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=max_tokens, patient=True, timeout=timeout, temperature=temperature,
        budget=budget,
    ).strip()


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise Unavailable("The AI reply was not JSON.")
    try:
        data = json.loads(match.group(0))
    except ValueError as exc:
        raise Unavailable("The AI reply was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise Unavailable("The AI reply was not a JSON object.")
    return data


def clean(value, limit=600):
    """A single-line-ish string from model output, or ''."""
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]
