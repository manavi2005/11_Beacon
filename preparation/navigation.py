"""The site navigation, defined once as data.

base.html used to hand-write a dozen links named after how each page was
built ("Skills (HttpResponse FBV)", "Plans (base CBV)"). That was useful for
grading Assignment 2 and confusing for anyone using the product. Now the
menu is this list, rendered by one loop in base.html:

  * every entry is a URL *name*, reversed at request time, so no path is
    ever written by hand and a renamed route fails loudly, not silently;
  * groups become dropdown menus;
  * the entry for the current page, and its group, are marked active;
  * "staff_only" entries (and groups) only appear for coaches (staff), and
    "student_only" groups only for everyone else - see visibility.py.

To add a page to the menu, add a line here. Nothing else changes.
"""

from django.urls import NoReverseMatch, reverse

NAV = [
    {"label": "My plan", "name": "preparation:my_plan"},
    {"label": "Dashboard", "name": "preparation:dashboard"},
    # Coaching is the cohort view: everyone's profiles and search. Students
    # see their own plan, tasks and profile through My plan instead.
    {"label": "Coaching", "staff_only": True, "children": [
        {"label": "Candidates", "name": "preparation:candidate_list",
         "hint": "Everyone, with scores"},
        {"label": "Find a candidate", "name": "preparation:candidate_search",
         "hint": "Search by name, role or company"},
        {"label": "Plans", "name": "preparation:plan_board",
         "hint": "Every preparation plan"},
        {"label": "Tasks", "name": "preparation:task_list",
         "hint": "Every task, week by week"},
        {"label": "New task", "name": "preparation:task_create",
         "hint": "Add a task to a plan"},
    ]},
    {"label": "My work", "student_only": True, "children": [
        {"label": "My tasks", "name": "preparation:task_list",
         "hint": "Every task in your plan"},
        {"label": "My plans", "name": "preparation:plan_board",
         "hint": "Current and past plans"},
        {"label": "Retake the diagnosis", "name": "preparation:onboarding",
         "hint": "Rebuild your plan"},
    ]},
    {"label": "Skills", "children": [
        {"label": "Skill catalog", "name": "preparation:skill_catalog_render",
         "hint": "Every skill Beacon measures"},
        {"label": "Search skills", "name": "preparation:skill_search",
         "hint": "Filter by name and category"},
        {"label": "Job market", "name": "preparation:market",
         "hint": "What employers ask for, live"},
    ]},
    {"label": "Insights", "children": [
        {"label": "Overview", "name": "preparation:insights",
         "hint": "Totals and grouped summaries"},
        {"label": "Charts", "name": "preparation:charts",
         "hint": "Skills, plans and gaps, drawn"},
        {"label": "Interactive charts", "name": "preparation:vega_lite",
         "hint": "Vega-Lite, live from the API"},
        {"label": "Reports & exports", "name": "preparation:reports",
         "hint": "Download CSV or JSON"},
    ]},
]

# The account menu on the right of the bar.
ACCOUNT_MENU = [
    {"label": "My plan", "name": "preparation:my_plan"},
    {"label": "Retake the diagnosis", "name": "preparation:onboarding"},
    {"label": "Admin", "name": "admin:index", "staff_only": True},
]

# Pages that belong to an entry without being the entry's own URL, so the
# menu still shows where you are. View name -> the entry's URL name.
ALSO_ACTIVE_FOR = {
    "preparation:candidate_detail": "preparation:candidate_list",
    "preparation:plan_detail": "preparation:plan_board",
    "preparation:task_detail": "preparation:task_list",
    "preparation:skill_detail": "preparation:skill_catalog_render",
    "preparation:skill_catalog_manual": "preparation:skill_catalog_render",
    "preparation:onboarding": "preparation:my_plan",
}


def _entry(item, current, user):
    if item.get("staff_only") and not user.is_staff:
        return None
    try:
        url = reverse(item["name"])
    except NoReverseMatch:
        # A route that needs arguments, or was removed, cannot be a menu link.
        return None
    return {
        "label": item["label"],
        "url": url,
        "hint": item.get("hint", ""),
        "active": current == item["name"],
    }


def build(request):
    """The menu for this request: resolved URLs and active flags."""
    user = request.user
    match = getattr(request, "resolver_match", None)
    current = match.view_name if match else ""
    current = ALSO_ACTIVE_FOR.get(current, current)

    items = []
    for item in NAV:
        if item.get("staff_only") and not user.is_staff:
            continue
        if item.get("student_only") and user.is_staff:
            continue
        if "children" in item:
            children = [c for c in (_entry(ch, current, user) for ch in item["children"]) if c]
            if children:
                items.append({
                    "label": item["label"],
                    "children": children,
                    "active": any(c["active"] for c in children),
                })
        else:
            entry = _entry(item, current, user)
            if entry:
                items.append(entry)

    account = [e for e in (_entry(i, current, user) for i in ACCOUNT_MENU) if e]
    return {"items": items, "account": account}


def navigation(request):
    """Context processor: {{ nav.items }} and {{ nav.account }} on every page.

    Signed-out visitors get nothing; base.html shows Log in / Sign up instead.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"nav": None}
    return {"nav": build(request)}
