"""External job-market data, triangulated with Beacon's own skill gaps.

Assignment 4, Part 2. The question this answers for a candidate:

    "Of the skills I am weak in, which ones do employers hiring for my target
    role actually ask for?"

Beacon's database knows the first half (proficiency against required level,
per skill). It cannot know the second half, so it asks a public job board.

Source: Jobicy's remote-jobs API (docs: https://jobi.cy/apidocs). It is
keyless, and its only terms are that Jobicy is credited with a link and that
every job links to its original URL, which the API response and the page both
do. Open-Meteo was excluded by the assignment.

Nothing from Jobicy is stored in the database. Postings are fetched, measured
and thrown away; the only thing kept is a short-lived cache entry so that a
classroom full of people loading the same page does not hit Jobicy once each.

Pipeline, one function per step:

    fetch_postings(q)      requests.get with params=, timeout=5,
                           raise_for_status(); errors become MarketDataError
    skill_mentions(posts)  how many postings mention each catalog skill
    market_report(q)       joins those counts with the ORM's per-skill gaps
                           and ranks skills by demand x gap
"""

import html
import re

import requests
from django.core.cache import cache
from django.db.models import Avg, Count, Q

from .models import Skill

JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"
JOBICY_HOME = "https://jobicy.com"
TIMEOUT_SECONDS = 5
POSTING_LIMIT = 50
CACHE_SECONDS = 60 * 60

# How each catalog skill shows up in a job ad. Skill names are written for
# candidates ("SQL & relational modeling"); ads use different words
# ("PostgreSQL", "data modeling"). Patterns are matched case-insensitively
# with word boundaries, so "git" does not match "digital".
#
# A skill added later without an entry here falls back to its own name, so it
# is still measured, just less generously.
SKILL_KEYWORDS = {
    "Data structures & algorithms": [
        r"algorithms?", r"data structures?", r"computer science fundamentals",
    ],
    "Python fundamentals": [r"python"],
    "SQL & relational modeling": [
        r"sql", r"postgres(?:ql)?", r"mysql", r"relational databases?",
        r"data model(?:l)?ing",
    ],
    "System design basics": [
        r"system design", r"distributed systems?", r"scalab(?:le|ility)",
        r"microservices?",
    ],
    "Version control with Git": [r"git", r"github", r"gitlab", r"version control"],
    # "Stakeholders" or "cross-functional" would match nearly every ad and
    # say nothing about telling a structured story, so they are left out.
    "STAR-format storytelling": [
        r"storytelling", r"communicat(?:e|ing) (?:impact|results|insights)",
        r"behaviou?ral interviews?",
    ],
    "Handling failure questions": [
        r"resilien(?:t|ce)", r"growth mindset", r"learn from (?:mistakes|failure)",
        r"adaptab(?:le|ility)",
    ],
    # Not "salary" or "compensation": almost every ad mentions pay, which
    # measures the ad, not whether negotiation matters for the role.
    "Negotiating an offer": [r"negotiat(?:e|es|ing|ion|ions)"],
    "Product sense": [
        r"product sense", r"product thinking", r"user research", r"roadmaps?",
        r"customer needs",
    ],
    "Financial markets basics": [
        r"financ(?:e|ial)", r"fintech", r"trading", r"capital markets",
    ],
    "Whiteboard communication": [
        r"communication skills", r"presentations?", r"written and verbal",
        r"explain(?:ing)? complex",
    ],
    "Resume & elevator pitch": [r"portfolio", r"resume", r"cv", r"cover letter"],
}

_TAG_RE = re.compile(r"<[^>]+>")


class MarketDataError(Exception):
    """The job board could not be used. Carries an HTTP status for the view.

    504 when Jobicy did not answer in time, 502 for everything else that is
    Jobicy's fault (an error status, a dropped connection, a body that is not
    the JSON we expect). The caller never sees a raw requests exception.
    """

    def __init__(self, message, status=502):
        super().__init__(message)
        self.message = message
        self.status = status


# ---------------------------------------------------------------------------
# Step 1 - fetch
# ---------------------------------------------------------------------------
def fetch_postings(query):
    """Remote job postings matching `query`, newest first, from Jobicy.

    Cached per query for an hour. Jobicy's listings do not change faster than
    that, and the cache is what makes it reasonable to demo this live.
    """
    cache_key = "jobicy:" + re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            JOBICY_URL,
            params={"count": POSTING_LIMIT, "tag": query},
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": "Beacon career coach (INFO 490 class project)"},
        )
        response.raise_for_status()
        payload = response.json()
    except requests.Timeout as exc:
        raise MarketDataError(
            f"Jobicy did not respond within {TIMEOUT_SECONDS} seconds.", status=504
        ) from exc
    except requests.HTTPError as exc:
        raise MarketDataError(
            f"Jobicy returned HTTP {exc.response.status_code}."
        ) from exc
    except requests.RequestException as exc:
        raise MarketDataError("Could not reach Jobicy.") from exc
    except ValueError as exc:  # the body was not JSON
        raise MarketDataError("Jobicy sent a response that was not JSON.") from exc

    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise MarketDataError("Jobicy's response had no list of jobs in it.")

    postings = [
        {
            "title": html.unescape(job.get("jobTitle") or ""),
            "company": html.unescape(job.get("companyName") or ""),
            "url": job.get("url") or "",
            "level": job.get("jobLevel") or "",
            "published": (job.get("pubDate") or "")[:10],
            # Title + excerpt + full description, tags stripped, lowercased:
            # the text the skill patterns are matched against.
            "_text": _plain_text(
                job.get("jobTitle"), job.get("jobExcerpt"), job.get("jobDescription")
            ),
        }
        for job in jobs
        if isinstance(job, dict)
    ]
    cache.set(cache_key, postings, CACHE_SECONDS)
    return postings


def _plain_text(*parts):
    text = " ".join(p for p in parts if p)
    return html.unescape(_TAG_RE.sub(" ", text)).lower()


# ---------------------------------------------------------------------------
# Step 2 - measure
# ---------------------------------------------------------------------------
def _pattern_for(skill_name):
    words = SKILL_KEYWORDS.get(skill_name) or [re.escape(skill_name.lower())]
    return re.compile(r"\b(?:" + "|".join(words) + r")\b", re.IGNORECASE)


def skill_mentions(postings, skill_names):
    """{skill name: number of postings that mention it at least once}.

    Counted once per posting, not once per occurrence: an ad that says
    "Python" nine times is still one employer asking for Python.
    """
    counts = {}
    for name in skill_names:
        pattern = _pattern_for(name)
        counts[name] = sum(1 for post in postings if pattern.search(post["_text"]))
    return counts


# ---------------------------------------------------------------------------
# Step 3 - triangulate with internal data
# ---------------------------------------------------------------------------
def market_report(query):
    """Job-market demand joined with Beacon's own skill gaps, ranked.

    Internal side: for each skill, the average gap (required minus
    proficiency) across candidates whose target role matches `query`. If no
    candidate targets that role, every candidate is used and the response
    says so, rather than silently returning empty gaps.

    priority = demand_pct x max(avg_gap, 0) / 100
    A skill scores high only when employers ask for it AND our candidates are
    behind on it. Either one alone is not worth a week of preparation.
    """
    postings = fetch_postings(query)

    role_filter = Q(assessments__candidate__target_role__icontains=query)
    cohort_is_role = Skill.objects.filter(role_filter).exists()
    assessment_filter = role_filter if cohort_is_role else Q()

    skills = Skill.objects.annotate(
        learners=Count("assessments", filter=assessment_filter, distinct=True),
        avg_proficiency=Avg("assessments__proficiency_score", filter=assessment_filter),
        avg_required=Avg("assessments__required_level", filter=assessment_filter),
    ).order_by("name")

    mentions = skill_mentions(postings, [s.name for s in skills])
    total = len(postings)

    rows = []
    for skill in skills:
        demand_pct = round(100 * mentions[skill.name] / total, 1) if total else 0.0
        gap = (
            round(float(skill.avg_required) - float(skill.avg_proficiency), 1)
            if skill.learners
            else None
        )
        rows.append({
            "skill": skill.name,
            "category": skill.get_category_display(),
            "postings_mentioning": mentions[skill.name],
            "demand_pct": demand_pct,
            "learners": skill.learners,
            "avg_gap": gap,
            "priority": round(demand_pct * max(gap or 0, 0) / 100, 2),
        })

    rows.sort(key=lambda r: (-r["priority"], -r["demand_pct"], r["skill"]))

    return {
        "query": query,
        "source": {
            "name": "Jobicy",
            "url": JOBICY_HOME,
            "note": "Remote job postings, fetched live and not stored.",
        },
        "postings_analyzed": total,
        "cohort": {
            "matched_target_role": cohort_is_role,
            "description": (
                f"Candidates whose target role contains '{query}'"
                if cohort_is_role
                else f"No candidate targets '{query}', so all candidates are used"
            ),
        },
        "skills": rows,
        "sample_postings": [
            {k: v for k, v in post.items() if not k.startswith("_")}
            for post in postings[:8]
        ],
    }
