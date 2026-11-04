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


def enabled():
    return coach.llm_enabled() and not cache.get(DOWN_KEY)


def _call(**kwargs):
    try:
        return coach._chat(**kwargs)
    except coach.CoachError as exc:
        if any(marker in str(exc) for marker in _UNREACHABLE):
            cache.set(DOWN_KEY, str(exc), DOWN_SECONDS)
        raise


def label():
    return coach.engine_label()


def ask_json(system, user, *, max_tokens=6000, timeout=60, temperature=0.6):
    """Return the model's reply parsed as a JSON object, or raise Unavailable."""
    if not enabled():
        raise Unavailable("AI is switched off.")
    text = _call(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        json_mode=True, max_tokens=max_tokens, patient=True, timeout=timeout,
        temperature=temperature,
    )
    return parse_json(text)


def ask_text(system, messages, *, max_tokens=3000, timeout=45, temperature=0.7):
    if not enabled():
        raise Unavailable("AI is switched off.")
    return _call(
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=max_tokens, patient=True, timeout=timeout, temperature=temperature,
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
