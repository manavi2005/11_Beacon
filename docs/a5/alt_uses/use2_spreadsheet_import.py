"""Alternative use 2: import Beacon's public API into Google Sheets or Excel.

Spreadsheets read CSV from a URL directly, so the public API also answers
?format=csv with the same rows as the JSON:

    https://simonhwang1998.pythonanywhere.com/api/skills/summary/?format=csv

Google Sheets - paste into cell A1 of an empty sheet:

    =IMPORTDATA("https://simonhwang1998.pythonanywhere.com/api/skills/summary/?format=csv")

  then, in an empty column, the per-category average gap:

    =QUERY(A:G, "select B, avg(F) where C > 0 group by B order by avg(F) desc label avg(F) 'Avg gap'", 1)

  and Insert > Chart on that result for a bar chart. Sheets re-fetches the
  URL periodically, so the sheet stays in step with the live database.

Excel - Data > Get Data > From Web, paste the same URL, Load.

This script is the test code for that use. It fetches the URL exactly as
IMPORTDATA does (plain CSV over HTTPS, no login), checks the header and row
count match the JSON form, prints the sheet as a spreadsheet would show it,
runs the same per-category average as the QUERY formula, and saves
beacon_skill_summary.csv for opening in Excel offline.

    python use2_spreadsheet_import.py
    python use2_spreadsheet_import.py --api http://127.0.0.1:8000/api/skills/summary/
"""

import argparse
import csv
import io
import sys
from collections import defaultdict

import requests

DEFAULT_API = "https://simonhwang1998.pythonanywhere.com/api/skills/summary/"
EXPECTED_HEADER = [
    "skill", "category", "learners", "avg_proficiency", "avg_required", "avg_gap", "tasks",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--out", default="beacon_skill_summary.csv")
    args = parser.parse_args()

    csv_url = args.api + "?format=csv"
    response = requests.get(csv_url, timeout=10)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("text/csv"):
        sys.exit(f"{csv_url} answered {content_type!r}, not CSV. "
                 "Is the deployed site up to date?")

    table = list(csv.reader(io.StringIO(response.text)))
    header, rows = table[0], table[1:]
    json_rows = requests.get(args.api, timeout=10).json()

    print(f"IMPORTDATA source: {csv_url}")
    print(f"Content-Type: {content_type}")
    print(f"Header matches the API's fields: {header == EXPECTED_HEADER}")
    print(f"Rows: {len(rows)} (JSON form has {len(json_rows)})\n")

    # How the sheet looks once imported: column letters across the top.
    widths = [max(len(r[i]) for r in table) for i in range(len(header))]
    letters = "".join(f"{chr(65 + i):<{w + 2}}" for i, w in enumerate(widths))
    print("    " + letters)
    for n, row in enumerate(table, start=1):
        print(f"{n:<4}" + "".join(f"{cell:<{w + 2}}" for cell, w in zip(row, widths)))

    # The QUERY formula from the docstring, done in Python.
    gaps = defaultdict(list)
    for skill, category, learners, _p, _r, gap, _t in rows:
        if int(learners) > 0:
            gaps[category].append(float(gap))
    print("\n=QUERY(... group by category ...) result:")
    for category, values in sorted(gaps.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        print(f"  {category:<18} avg gap {sum(values) / len(values):5.1f}")

    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        handle.write(response.text)
    print(f"\nSaved {args.out} for Excel (File > Open).")


if __name__ == "__main__":
    main()
