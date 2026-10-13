"""Doing a task on the platform, grading it, and updating the skill rating.

A plan task used to be "done" when a box was ticked, so readiness rested on
nothing but self-report. Now every task has a workspace, and progress comes
from evidence:

  QUIZ    technical skills with a question bank. Auto-graded, with the
          reason for each right answer shown afterwards.
  WRITE   everything else: write the STAR story, the pitch, or explain back
          what you read or practised. Graded by the AI coach against a
          rubric (preparation/coach.py); if the model is off, busy or
          returns junk, a transparent rules grader scores it instead.

Each attempt then moves the candidate's rating for that skill part of the
way toward the score they demonstrated (LEARNING_RATE), in either
direction, so a self-rating of 40 and a quiz score of 75 becomes 54, and an
over-confident 80 with a weak answer drifts down. The task counts as done
when an attempt reaches PASS_SCORE.
"""

import json
import re

from django.db import transaction
from django.utils import timezone

from . import coach
from .market import _pattern_for
from .models import PlanTask, SkillAssessment, TaskAttempt

PASS_SCORE = 60
LEARNING_RATE = 0.4

# Four questions per technical skill. Kept short and unambiguous: this is a
# check that the practice happened, not a certification.
QUIZ_BANK = {
    "SQL & relational modeling": [
        {"q": "Which JOIN keeps every row from the left table, even with no match on the right?",
         "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "SELF JOIN"], "answer": 1,
         "why": "LEFT JOIN keeps all left rows and fills unmatched right columns with NULL."},
        {"q": "You need the number of orders per customer. Which clause groups the rows?",
         "options": ["ORDER BY customer_id", "GROUP BY customer_id", "WHERE customer_id", "HAVING customer_id"], "answer": 1,
         "why": "GROUP BY makes one group per customer; COUNT(*) then counts each group."},
        {"q": "Which filters groups after aggregation, e.g. customers with more than 5 orders?",
         "options": ["WHERE", "HAVING", "LIMIT", "DISTINCT"], "answer": 1,
         "why": "WHERE filters rows before grouping; HAVING filters the groups after."},
        {"q": "What does ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY created_at DESC) let you do?",
         "options": ["Delete duplicate customers", "Pick each customer's most recent row",
                     "Sum each customer's orders", "Join two tables"], "answer": 1,
         "why": "Numbering rows newest-first within each customer, then keeping row 1, gives the latest order."},
    ],
    "Python fundamentals": [
        {"q": "What does [x * 2 for x in range(3)] evaluate to?",
         "options": ["[0, 2, 4]", "[2, 4, 6]", "[0, 1, 2]", "(0, 2, 4)"], "answer": 0,
         "why": "range(3) is 0, 1, 2; doubling each gives [0, 2, 4]."},
        {"q": "Which is the fastest way to check whether a value is among 1 million items?",
         "options": ["A list", "A set", "A string", "A tuple"], "answer": 1,
         "why": "Set membership is a hash lookup, about O(1); lists and tuples scan, O(n)."},
        {"q": "What is the main advantage of a generator over a list?",
         "options": ["It is sorted", "It produces items lazily, using little memory",
                     "It can be indexed", "It is immutable"], "answer": 1,
         "why": "Generators yield one item at a time instead of building the whole list in memory."},
        {"q": "def f(items=[]): items.append(1); return items  - what does calling f() twice return?",
         "options": ["[1]", "[1, 1]", "None", "An error"], "answer": 1,
         "why": "Default arguments are created once, so the same list is reused and grows."},
    ],
    "Data structures & algorithms": [
        {"q": "What is the time complexity of binary search on a sorted array?",
         "options": ["O(n)", "O(log n)", "O(n log n)", "O(1)"], "answer": 1,
         "why": "Each step halves the search range."},
        {"q": "Which structure gives O(1) average lookup by key?",
         "options": ["Linked list", "Hash map", "Binary heap", "Sorted array"], "answer": 1,
         "why": "A hash map jumps straight to a bucket computed from the key."},
        {"q": "Breadth-first search on a graph is naturally implemented with a...",
         "options": ["Stack", "Queue", "Heap", "Trie"], "answer": 1,
         "why": "BFS visits nodes in the order discovered: first in, first out."},
        {"q": "Two Sum (find two numbers adding to a target) can be solved in O(n) using...",
         "options": ["Nested loops", "A hash map of seen values", "Sorting only", "Recursion"], "answer": 1,
         "why": "For each number, check if target - number has been seen; store it otherwise."},
    ],
    "Version control with Git": [
        {"q": "Which command creates a new branch and switches to it?",
         "options": ["git branch -d name", "git switch -c name", "git merge name", "git fetch name"], "answer": 1,
         "why": "git switch -c (or git checkout -b) creates and switches in one step."},
        {"q": "What does git pull do?",
         "options": ["Uploads your commits", "Fetches remote changes and integrates them",
                     "Deletes a branch", "Stages all files"], "answer": 1,
         "why": "pull = fetch + merge (or rebase) into your current branch."},
        {"q": "Two people edited the same lines. Git stops the merge. What is this called?",
         "options": ["A detached HEAD", "A merge conflict", "A fast-forward", "A stash"], "answer": 1,
         "why": "A merge conflict needs a human to choose the final lines, then commit."},
        {"q": "Why work on a feature branch instead of main?",
         "options": ["It is faster to type", "main stays working while changes are reviewed",
                     "Branches cannot be merged", "Git requires it"], "answer": 1,
         "why": "Branches isolate work-in-progress; a pull request merges it back after review."},
    ],
    "System design basics": [
        {"q": "Your read-heavy API is slow. What usually helps first?",
         "options": ["A cache in front of the database", "Bigger log files",
                     "Removing indexes", "Fewer servers"], "answer": 0,
         "why": "Caching hot reads avoids repeating the same expensive database work."},
        {"q": "What does a load balancer do?",
         "options": ["Stores user sessions forever", "Spreads requests across several servers",
                     "Compresses images", "Backs up the database"], "answer": 1,
         "why": "It distributes traffic so no single server is overwhelmed and one can fail safely."},
        {"q": "Why put slow work (emails, reports) on a queue?",
         "options": ["Queues make it run faster", "The request can return immediately while workers process it",
                     "It removes the need for a database", "It encrypts the data"], "answer": 1,
         "why": "Asynchronous workers keep user-facing requests fast and absorb spikes."},
        {"q": "Sharding a database means...",
         "options": ["Copying it to every server", "Splitting rows across several databases by a key",
                     "Deleting old rows", "Adding more indexes"], "answer": 1,
         "why": "Each shard holds part of the data, so storage and load scale horizontally."},
    ],
}

BEHAVIORAL = {"STAR-format storytelling", "Handling failure questions", "Negotiating an offer"}
STAR_WORDS = {
    "situation": r"\b(when|during|at (?:my|our)|last (?:year|summer|semester)|in (?:my|our)|the (?:project|team|company))\b",
    "task": r"\b(my (?:role|job|task|goal)|i (?:was|had) (?:to|responsible)|needed to|goal was)\b",
    "action": r"\b(i (?:built|led|wrote|designed|created|organized|decided|talked|analy[sz]ed|proposed|set up|cut|fixed|reached out))\b",
    "result": r"\b(result(?:ed)?|so that|which (?:led|meant)|increased|decreased|reduced|improved|saved|shipped|launched|\d+ ?%)\b",
}


def task_kind(task):
    if task.skill and task.skill.name in QUIZ_BANK:
        return TaskAttempt.Kind.QUIZ
    return TaskAttempt.Kind.WRITTEN


def written_prompt(task):
    """What to write, and a short rubric, for an explain-it-back task."""
    name = task.skill.name if task.skill else "this skill"
    if name in BEHAVIORAL:
        return {
            "prompt": f"Do the task: “{task.title}”. Then write one of your answers here, in STAR form.",
            "rubric": ["Situation: where and when", "Task: what you were responsible for",
                       "Action: what you did, specifically", "Result: what changed, with a number if you can"],
        }
    if task.title.lower().startswith(("read", "research", "critique")):
        return {
            "prompt": f"Do the task: “{task.title}”. Then explain back what you found, in your own words.",
            "rubric": ["The 2-3 most important things you learned", "Why each matters for the role",
                       "One thing you would do differently now"],
        }
    return {
        "prompt": f"Do the task: “{task.title}”. Then explain here what you did and what you learned.",
        "rubric": ["What you actually did (be specific)", f"How it shows {name}",
                   "What was hard, and what you would practise next"],
    }


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
def grade_quiz(task, picks):
    """picks: {question index -> option index}. Returns (score, feedback)."""
    questions = QUIZ_BANK[task.skill.name]
    results = []
    for i, q in enumerate(questions):
        chosen = picks.get(i)
        results.append({
            "q": q["q"], "chosen": chosen, "answer": q["answer"],
            "correct": chosen == q["answer"], "why": q["why"],
            "options": q["options"],
        })
    right = sum(r["correct"] for r in results)
    score = round(100 * right / len(questions))
    return score, {
        "summary": f"{right} of {len(questions)} correct.",
        "questions": results,
    }


def _rules_grade_written(task, text):
    words = len(text.split())
    skill = task.skill.name if task.skill else ""
    strengths, improve = [], []
    score = 20 if words < 40 else 40 if words < 80 else 55
    if words < 80:
        improve.append(f"Write more: {words} words is thin. Aim for 80-200.")
    else:
        strengths.append("Enough detail to judge.")
    if skill in BEHAVIORAL:
        for part, pattern in STAR_WORDS.items():
            if re.search(pattern, text, re.I):
                score += 10
                strengths.append(f"Has a clear {part.title()}.")
            else:
                improve.append(f"Add the {part.title()}.")
    elif skill and _pattern_for(skill).search(text):
        score += 25
        strengths.append(f"Talks concretely about {skill}.")
    else:
        improve.append(f"Tie it explicitly to {skill or 'the skill'}.")
    if re.search(r"\d", text):
        score += 5
        strengths.append("Uses specifics (numbers).")
    return min(score, 95), {
        "summary": "Scored by Beacon's rules: length, structure and specifics. "
                   "The AI coach gives richer feedback when it is available.",
        "strengths": strengths, "improve": improve,
    }


WRITTEN_GRADER = (
    "You grade a candidate's written practice for a job interview. Reply with "
    "only a JSON object: "
    '"score" (integer 0-100; 60 means interview-ready for an entry-level role), '
    '"summary" (one sentence), "strengths" (list of up to 3 short points), '
    '"improve" (list of up to 3 short, specific fixes). '
    "Be fair but honest; do not inflate. Judge only the text given."
)


def _ai_grade_written(task, text):
    brief = written_prompt(task)
    content = coach._chat(
        [
            {"role": "system", "content": WRITTEN_GRADER},
            {"role": "user", "content": json.dumps({
                "skill": task.skill.name if task.skill else None,
                "task": task.title,
                "rubric": brief["rubric"],
                "answer": text[:4000],
            })},
        ],
        json_mode=True, max_tokens=400, patient=True,
    )
    match = re.search(r"\{.*\}", content or "", re.S)
    if not match:
        raise coach.CoachError("The AI grade was not JSON.")
    data = json.loads(match.group(0))
    score = int(data.get("score"))
    if not 0 <= score <= 100:
        raise coach.CoachError("The AI grade was out of range.")
    as_list = lambda v: [str(x)[:200] for x in v][:3] if isinstance(v, list) else []
    return score, {
        "summary": str(data.get("summary", ""))[:300],
        "strengths": as_list(data.get("strengths")),
        "improve": as_list(data.get("improve")),
    }


def grade_written(task, text):
    """(score, feedback, graded_by). AI first, rules if it cannot answer."""
    if coach.llm_enabled():
        try:
            score, feedback = _ai_grade_written(task, text)
            return score, feedback, TaskAttempt.GradedBy.AI
        except (coach.CoachError, ValueError, TypeError) as exc:
            score, feedback = _rules_grade_written(task, text)
            feedback["note"] = f"{exc} Scored by Beacon's rules instead."
            return score, feedback, TaskAttempt.GradedBy.RULES
    score, feedback = _rules_grade_written(task, text)
    return score, feedback, TaskAttempt.GradedBy.RULES


# ---------------------------------------------------------------------------
# Recording an attempt
# ---------------------------------------------------------------------------
def updated_rating(before, score):
    return max(0, min(100, round(before + LEARNING_RATE * (score - before))))


@transaction.atomic
def record_attempt(task, *, kind, response, score, feedback, graded_by):
    """Save the attempt, move the skill rating, and complete the task on a pass."""
    profile = task.plan.candidate
    before = after = None
    if task.skill_id:
        assessment, _ = SkillAssessment.objects.get_or_create(
            candidate=profile, skill=task.skill,
            defaults={"proficiency_score": 0, "required_level": 65},
        )
        before = assessment.proficiency_score
        after = updated_rating(before, score)
        assessment.proficiency_score = after
        assessment.assessed_on = timezone.localdate()
        assessment.save(update_fields=["proficiency_score", "assessed_on"])

    passed = score >= PASS_SCORE
    if passed and task.status != PlanTask.Status.DONE:
        task.status, task.completed_on = PlanTask.Status.DONE, timezone.localdate()
    elif not passed and task.status == PlanTask.Status.TODO:
        task.status = PlanTask.Status.IN_PROGRESS
    task.save(update_fields=["status", "completed_on"])

    return TaskAttempt.objects.create(
        task=task, kind=kind, response=response, score=score, passed=passed,
        feedback=feedback, graded_by=graded_by, rating_before=before, rating_after=after,
    )
