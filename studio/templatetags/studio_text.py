"""Render model text safely: escape everything, then allow **bold** and '-' bullets."""

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


def coach_html(text):
    html, items = [], []

    def flush():
        if items:
            html.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for raw in (text or "").strip().splitlines():
        line = escape(raw.strip())
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(r"^#+\s*", "", line)
        bullet = re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)", line)
        if bullet:
            items.append(bullet.group(1))
            continue
        flush()
        if line:
            html.append(f"<p>{line}</p>")
    flush()
    return mark_safe("".join(html))


register.filter("coach_html", coach_html)
