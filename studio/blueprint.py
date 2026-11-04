"""Any career, not just tech: the skill blueprint for whatever role you type.

v1 knew seven roles, hard-coded in preparation/onboarding.py. Here a role
title is turned into 6-8 skills, each with the level an interviewer expects
and one line on why, by the AI model. Blueprints are cached per role title,
so the second "Registered Nurse" is instant and every nurse is measured on
the same bar. The seven presets remain as the offline fallback.
"""

from django.utils.text import slugify

from preparation.models import Skill
from preparation.onboarding import GENERAL_ROLE

from . import ai
from .models import RoleBlueprint, clamp

CATEGORIES = {
    "technical": Skill.Category.TECHNICAL,
    "behavioral": Skill.Category.BEHAVIORAL,
    "domain": Skill.Category.DOMAIN,
    "communication": Skill.Category.COMMUNICATION,
}

# Every interview, in every field, tests these. A blueprint always has at
# least one of them so the mock interviewer and STAR practice have a home.
UNIVERSAL = [
    {"name": "STAR-format storytelling", "category": "behavioral", "required": 75,
     "why": "Every interviewer asks for a time you did something; structure wins."},
    {"name": "Resume & elevator pitch", "category": "communication", "required": 70,
     "why": "The first two minutes decide how the rest of the interview goes."},
]

SYSTEM = (
    "You are a hiring expert who knows what interviews test in every field: healthcare, "
    "education, design, trades, finance, law, hospitality, government, science and tech. "
    "Reply with JSON only."
)


def _prompt(title, experience):
    return (
        f'Role: "{title}". Candidate experience: {experience or "early career"}.\n'
        "List the 7 skills an interviewer for this exact role assesses most. Mix role-specific "
        "knowledge and practical skills with the people skills that matter for this job. Use "
        "short, specific skill names (2-5 words) a candidate would recognise, never vague ones "
        "like 'hard work'. Include exactly one of 'STAR-format storytelling' or "
        "'Resume & elevator pitch' among the 7.\n"
        'Return {"title": canonical role title, "summary": one sentence on what the job is, '
        '"skills": [{"name", "category": one of technical|domain|behavioral|communication, '
        '"required": integer 50-90, the level a strong hire shows, "why": one sentence on why '
        "this role's interviews test it}]}"
    )


def _validate(data, title):
    skills, seen = [], set()
    for row in data.get("skills") or []:
        if not isinstance(row, dict):
            continue
        name = ai.clean(row.get("name"), 60).strip(" .")
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        try:
            required = int(row.get("required", 70))
        except (TypeError, ValueError):
            required = 70
        skills.append({
            "name": name[:1].upper() + name[1:],
            "category": str(row.get("category", "domain")).lower()
            if str(row.get("category", "")).lower() in CATEGORIES else "domain",
            "required": clamp(required, 40, 95),
            "why": ai.clean(row.get("why"), 200),
        })
    if len(skills) < 4:
        raise ai.Unavailable("The AI blueprint had too few skills.")
    names = {s["name"].lower() for s in skills}
    if not names & {u["name"].lower() for u in UNIVERSAL}:
        skills.append(dict(UNIVERSAL[0]))
    return {
        "title": ai.clean(data.get("title"), 140) or title,
        "summary": ai.clean(data.get("summary"), 300),
        "skills": skills[:9],
    }


def _fallback(title):
    """Offline blueprint built from the title itself, for any field.

    Without the AI model Beacon cannot know what a chemist or a nurse is
    tested on, so it does not pretend to: it builds an honest field-neutral
    bar around the person's own role (knowledge, applying it, explaining it)
    plus the interview skills every field shares. When the model is back,
    regenerate() replaces it with a specific one.
    """
    role = title or "your target role"
    return {
        "title": title,
        "summary": "",
        "skills": [
            {"name": f"{role} fundamentals"[:60], "category": "domain", "required": 75,
             "why": "Interviewers check the core knowledge the job is built on."},
            {"name": f"Applying {role} skills to real scenarios"[:60], "category": "technical",
             "required": 70, "why": "Most interviews include a 'what would you do if' scenario."},
            {"name": "Explaining your work clearly", "category": "communication", "required": 70,
             "why": "You will be asked to walk through a project or decision you made."},
            {"name": "Problem solving under pressure", "category": "behavioral", "required": 65,
             "why": "Every field wants to see how you think when things go wrong."},
            *[dict(u) for u in UNIVERSAL],
        ],
    }


def get_blueprint(title, experience=""):
    """The cached blueprint for a role, generating it on first request.
    A fallback blueprint is retried with the model next time it is asked for."""
    title = " ".join((title or "").split())[:140] or GENERAL_ROLE
    slug = slugify(title)[:140] or "general"
    existing = RoleBlueprint.objects.filter(slug=slug).first()
    if existing and (existing.source == RoleBlueprint.Source.AI or not ai.enabled()):
        return existing
    try:
        data = _validate(ai.ask_json(SYSTEM, _prompt(title, experience)), title)
        source, label = RoleBlueprint.Source.AI, ai.label()
    except ai.Unavailable:
        data = _fallback(title)
        source, label = RoleBlueprint.Source.PRESET, ""
    if existing and source != RoleBlueprint.Source.AI:
        return existing
    blueprint, _ = RoleBlueprint.objects.update_or_create(
        slug=slug,
        defaults={"title": data["title"], "summary": data["summary"],
                  "skills": data["skills"], "source": source, "model_label": label},
    )
    return blueprint


def ensure_skills(blueprint):
    """Skill rows for every skill in the blueprint, created on first use."""
    result = []
    for row in blueprint.skills:
        skill = Skill.objects.filter(name__iexact=row["name"]).first()
        if not skill:
            skill = Skill.objects.create(
                name=row["name"][:100],
                category=CATEGORIES.get(row["category"], Skill.Category.DOMAIN),
                description=row.get("why", ""),
            )
        result.append((skill, row))
    return result

