"""Resume (and LinkedIn profile PDF) parser for onboarding.

Rule-based, like the rest of Phase 1: no AI, no external service. It reads
the text of a resume and answers three questions to speed up onboarding:

    which catalog skills does it show evidence of, and how much?
    what kind of work does the person seem drawn to? (interests)
    which roles fit that?

The skill patterns are the same ones the job-market analysis uses
(market.SKILL_KEYWORDS), so "PostgreSQL" counts as SQL evidence in both
places.

LinkedIn: there is no public API for reading someone's profile, and scraping
it breaks LinkedIn's terms. But LinkedIn lets every user export their own
profile with More > Save to PDF, and that PDF is just another resume to this
parser. That is the supported route.

Privacy: the upload is read in memory and discarded. Nothing from it is
stored; only the suggestions it produces pre-fill the onboarding form, and
the user confirms or changes every one of them.
"""

import io
import re

from .market import _pattern_for
from .models import Skill
from .onboarding import suggested_roles

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 10
MAX_CHARS = 60_000

# Evidence -> a starting self-rating. Deliberately modest: a resume shows a
# skill was used, not how well, so the slider starts in the middle and the
# user adjusts it. Skills with no evidence are left alone.
RATING_FOR_MENTIONS = {1: 55, 2: 65}

# Where a job-ad pattern means something different inside a resume. Every
# resume says "resume" or "CV", which is not evidence of pitching yourself
# well, so this skill looks for actual speaking and pitching instead.
RESUME_OVERRIDES = {
    "Resume & elevator pitch": [
        r"elevator pitch(?:es)?", r"public speaking", r"pitch(?:ed|ing)?\b",
        r"toastmasters", r"keynote",
    ],
}
RATING_MANY = 70   # multiples of 5: the sliders step by 5

# Words that suggest what kind of work someone enjoys -> interest keys
# (onboarding.INTERESTS).
INTEREST_PATTERNS = {
    "build": r"\b(?:software|developer|engineer(?:ing)?|full[- ]stack|backend|frontend|api|deploy(?:ed)?)\b",
    "data": r"\b(?:data|analytics?|analy[sz]ed|sql|tableau|power bi|statistics|dashboards?|pandas)\b",
    "product": r"\b(?:product|roadmaps?|stakeholders?|launch(?:ed)?|feature prioriti[sz]ation|go[- ]to[- ]market)\b",
    "people": r"\b(?:user research|interviews?|usability|figma|ux|design thinking|personas?|survey)\b",
    "markets": r"\b(?:finance|financial|trading|investment|equity|portfolio management|bank(?:ing)?|markets?)\b",
}
INTEREST_THRESHOLD = 3


class ResumeError(Exception):
    """Something the user can fix: wrong file type, too big, unreadable."""


def extract_text(upload=None, pasted=""):
    """Plain text from an uploaded PDF/.txt, or from pasted text."""
    if upload is None:
        text = pasted or ""
    else:
        if upload.size > MAX_BYTES:
            raise ResumeError("That file is over 5 MB. Try a smaller PDF.")
        name = (upload.name or "").lower()
        data = upload.read()
        if name.endswith(".pdf") or data[:5] == b"%PDF-":
            text = _pdf_text(data)
        elif name.endswith(".txt"):
            text = data.decode("utf-8", errors="replace")
        else:
            raise ResumeError("Upload a PDF or a .txt file, or paste the text instead.")
    text = text[:MAX_CHARS]
    if len(text.strip()) < 40:
        raise ResumeError(
            "Couldn't find any text in that. If it's a scanned image, paste the text instead."
        )
    return text


def _pdf_text(data):
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ResumeError("That PDF is password-protected. Export an unlocked copy.")
        return "\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PAGES])
    except ResumeError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise ResumeError("That PDF couldn't be read. Try re-exporting it.") from exc


def _evidence(text, match, width=60):
    start = max(match.start() - width, 0)
    end = min(match.end() + width, len(text))
    snippet = " ".join(text[start:end].split())
    return ("..." if start else "") + snippet + ("..." if end < len(text) else "")


def analyse(text):
    """Skill evidence, interests and suggested roles from resume text."""
    # LinkedIn's "Save to PDF" export has a fixed layout: a "Top Skills"
    # sidebar and "Page N of M" footers. A plain resume that merely links to
    # a LinkedIn profile does not, so the link alone is not enough.
    looks_like_linkedin = (
        "Top Skills" in text
        and "Experience" in text
        and bool(re.search(r"Page \d+ of \d+", text))
    )

    skills = []
    for skill in Skill.objects.order_by("name"):
        if skill.name in RESUME_OVERRIDES:
            pattern = re.compile(r"\b(?:" + "|".join(RESUME_OVERRIDES[skill.name]) + r")\b", re.I)
        else:
            pattern = _pattern_for(skill.name)
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        skills.append({
            "id": skill.pk,
            "field": f"id_skill_{skill.pk}",
            "name": skill.name,
            "mentions": len(matches),
            "rating": RATING_FOR_MENTIONS.get(len(matches), RATING_MANY),
            "evidence": _evidence(text, matches[0]),
        })
    skills.sort(key=lambda s: -s["mentions"])

    interests = [
        key for key, pattern in INTEREST_PATTERNS.items()
        if len(re.findall(pattern, text, re.I)) >= INTEREST_THRESHOLD
    ]
    return {
        "source": "linkedin" if looks_like_linkedin else "resume",
        "characters": len(text),
        "skills": skills,
        "interests": interests,
        "suggested_roles": suggested_roles(interests)[:3],
    }
