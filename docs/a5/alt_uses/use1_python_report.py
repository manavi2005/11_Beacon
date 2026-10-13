"""Alternative use 1: a Python script that turns Beacon's public API into a
category-level coaching report.

    python use1_python_report.py
    python use1_python_report.py --api http://127.0.0.1:8000/api/skills/summary/

API accessed:  GET https://simonhwang1998.pythonanywhere.com/api/skills/summary/
               (public, no login, JSON array, one row per skill)
Data used:     category, learners, avg_proficiency, avg_required, avg_gap
Result:        per-category totals and averages the API does not provide
               itself, weighted by how many candidates were assessed, plus the
               single skill each category should focus on first.

Who would use this: a career-centre advisor planning next term's workshops,
who wants "which area are students weakest in?" rather than 12 skill rows.
"""

import argparse
import sys
from collections import defaultdict

import requests

DEFAULT_API = "https://simonhwang1998.pythonanywhere.com/api/skills/summary/"


def fetch(api_url):
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        sys.exit(f"Expected a JSON array from {api_url}, got {type(rows).__name__}")
    return rows


def summarise(rows):
    """Aggregate skill rows into one row per category.

    Averages are weighted by learners: a skill five candidates were assessed
    on should count five times as much as a skill one candidate tried.
    """
    groups = defaultdict(list)
    for row in rows:
        if row["learners"]:
            groups[row["category"]].append(row)

    summary = []
    for category, skills in groups.items():
        learners = sum(s["learners"] for s in skills)
        weighted_gap = sum(s["avg_gap"] * s["learners"] for s in skills) / learners
        weighted_prof = sum(s["avg_proficiency"] * s["learners"] for s in skills) / learners
        focus = max(skills, key=lambda s: s["avg_gap"])
        summary.append({
            "category": category,
            "skills": len(skills),
            "assessments": learners,
            "avg_proficiency": weighted_prof,
            "avg_gap": weighted_gap,
            "focus_skill": focus["skill"],
            "focus_gap": focus["avg_gap"],
        })
    summary.sort(key=lambda r: r["avg_gap"], reverse=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default=DEFAULT_API, help="public API URL")
    args = parser.parse_args()

    rows = fetch(args.api)
    assessed = [r for r in rows if r["learners"]]
    print(f"API: {args.api}")
    print(f"Fetched {len(rows)} skills, {len(assessed)} with at least one assessment.\n")

    header = (f"{'Category':<18}{'Skills':>7}{'Assessed':>10}"
              f"{'Avg prof.':>11}{'Avg gap':>9}   Focus first")
    print(header)
    print("-" * 84)
    for r in summarise(rows):
        print(f"{r['category']:<18}{r['skills']:>7}{r['assessments']:>10}"
              f"{r['avg_proficiency']:>11.1f}{r['avg_gap']:>9.1f}   "
              f"{r['focus_skill']} (gap {r['focus_gap']:.1f})")

    total = sum(r["learners"] for r in assessed)
    overall = sum(r["avg_gap"] * r["learners"] for r in assessed) / total
    widest = max(assessed, key=lambda r: r["avg_gap"])
    print(f"\nAcross all {total} assessments, candidates sit {overall:.1f} points "
          f"below what their target roles require.")
    print(f"Single biggest gap: {widest['skill']} ({widest['avg_gap']:.1f} points).")


if __name__ == "__main__":
    main()
