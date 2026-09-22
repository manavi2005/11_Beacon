"""Generate Beacon's ER diagram straight from the Django models.

Run from the project root:

    python docs/data_model/generate_er_diagram.py          # writes docs/data_model/er_diagram.dot
    dot -Tpdf docs/data_model/er_diagram.dot -o docs/data_model/er_diagram.pdf
    dot -Tpng docs/data_model/er_diagram.dot -o docs/data_model/er_diagram.png

The diagram is introspected rather than hand-drawn, so it can never drift out
of sync with models.py. Graphviz is only needed for the last two commands
(macOS: `brew install graphviz`).
"""

import os
import sys
from pathlib import Path

# This file lives at <project root>/docs/data_model/generate_er_diagram.py, so
# three .parent hops are needed to reach the root that holds manage.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "beacon_core.settings.development")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402

APP_LABEL = "preparation"
ILLINI_BLUE = "#13294B"
ILLINI_ORANGE = "#E84A27"

ARROW_STYLE = {
    "CASCADE": ("solid", ILLINI_ORANGE),
    "PROTECT": ("bold", ILLINI_BLUE),
    "SET_NULL": ("dashed", "#767676"),
}


def field_rows(model):
    rows = []
    for field in model._meta.get_fields():
        if field.auto_created and not field.concrete:
            continue  # reverse relations are drawn as edges, not rows
        if field.many_to_many and not field.concrete:
            continue
        name = field.name
        kind = field.get_internal_type().replace("Field", "")
        marker = ""
        if getattr(field, "primary_key", False):
            marker = "PK "
        elif field.is_relation:
            marker = "FK "
        rows.append(f"{marker}{name} : {kind}")
    return rows


def escape(text):
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


def build_dot():
    lines = [
        "digraph Beacon {",
        '  graph [rankdir=LR, splines=spline, overlap=false, nodesep=0.6, ranksep=1.1, '
        'fontname="Helvetica", label="Beacon - AI Personal Career Coach\\n'
        'ER diagram (app: preparation)  |  Team Career Coaches, Group 11", '
        "labelloc=t, fontsize=18];",
        '  node [shape=plaintext, fontname="Helvetica", fontsize=10];',
        '  edge [fontname="Helvetica", fontsize=9];',
    ]

    models = list(apps.get_app_config(APP_LABEL).get_models())
    models.append(apps.get_model("auth", "User"))

    for model in models:
        is_external = model._meta.app_label != APP_LABEL
        header_color = "#9AA7B8" if is_external else ILLINI_BLUE
        title = model.__name__ + (" (django.contrib.auth)" if is_external else "")
        rows = (
            ["PK id : Auto", "username : Char", "first_name : Char", "email : Email"]
            if is_external
            else field_rows(model)
        )
        cells = "".join(
            f'<TR><TD ALIGN="LEFT" PORT="{i}">{escape(r)}</TD></TR>'
            for i, r in enumerate(rows)
        )
        lines.append(
            f'  {model.__name__} [label=<<TABLE BORDER="0" CELLBORDER="1" '
            f'CELLSPACING="0" CELLPADDING="4">'
            f'<TR><TD BGCOLOR="{header_color}"><FONT COLOR="white"><B>'
            f"{escape(title)}</B></FONT></TD></TR>{cells}</TABLE>>];"
        )

    for model in apps.get_app_config(APP_LABEL).get_models():
        for field in model._meta.get_fields():
            if not (field.concrete and field.is_relation):
                continue
            target = field.related_model
            if field.many_to_many:
                lines.append(
                    f'  {model.__name__} -> {target.__name__} '
                    f'[label="{field.name} (M2M through SkillAssessment)", '
                    'style=dotted, color="#767676", arrowhead=veevee, arrowtail=veevee, '
                    "dir=both];"
                )
                continue
            on_delete = getattr(field.remote_field, "on_delete", None)
            behaviour = getattr(on_delete, "__name__", "CASCADE").upper()
            style, color = ARROW_STYLE.get(behaviour, ("solid", "#333333"))
            cardinality = "1 --- 1" if field.one_to_one else "1 --- N"
            lines.append(
                f'  {target.__name__} -> {model.__name__} '
                f'[label="{cardinality}\\n{field.name} ({behaviour})", '
                f'style={style}, color="{color}", arrowhead=crow];'
            )

    lines.append(
        '  legend [shape=plaintext, label=<<TABLE BORDER="0" CELLBORDER="1" '
        'CELLSPACING="0" CELLPADDING="4"><TR><TD BGCOLOR="#EEEEEE"><B>Legend'
        "</B></TD></TR>"
        f'<TR><TD ALIGN="LEFT"><FONT COLOR="{ILLINI_ORANGE}">solid</FONT>'
        " = on_delete CASCADE</TD></TR>"
        f'<TR><TD ALIGN="LEFT"><FONT COLOR="{ILLINI_BLUE}">bold</FONT>'
        " = on_delete PROTECT</TD></TR>"
        '<TR><TD ALIGN="LEFT">dashed = on_delete SET_NULL</TD></TR>'
        '<TR><TD ALIGN="LEFT">dotted = ManyToMany (through table)</TD></TR>'
        "</TABLE>>];"
    )
    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    out = PROJECT_ROOT / "docs" / "data_model" / "er_diagram.dot"
    out.write_text(build_dot())
    print(f"Wrote {out}")
    print("Render with: dot -Tpdf docs/data_model/er_diagram.dot -o docs/data_model/er_diagram.pdf")
