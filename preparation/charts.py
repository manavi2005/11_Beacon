"""Server-side chart rendering for Beacon.

Assignment 3, Section 4. Every chart here is drawn from a live ORM query and
returned as a PNG by a view, so nothing is precomputed and no image file is
ever written to disk.

Two decisions in this module are worth reading before changing anything.

1. The Agg backend, set before any other matplotlib import.

   Matplotlib defaults to an interactive backend that expects a window server.
   On a machine with a display that quietly works; on a deployed server there
   is no display, and the import either fails outright or tries to start a GUI
   event loop inside the request. Agg is the pure-software renderer: it draws
   into a memory buffer and has no window at all, which is exactly what a web
   process wants.

2. The object-oriented Figure API, not pyplot.

   pyplot keeps every figure it creates in a global registry so an interactive
   session can find them again. That registry is the classic Django memory
   leak: each request calls plt.figure(), the figure is never closed, and the
   process grows until it is restarted. Constructing Figure() directly skips
   the registry entirely, so a figure is ordinary garbage the moment the last
   reference to it goes away. It also avoids a shared global being mutated by
   two requests at once, which is a real risk under any threaded server.

   Nothing in here calls plt.* and nothing needs plt.close().
"""

import matplotlib

matplotlib.use("Agg")  # must come before pyplot/Figure is used anywhere

from io import BytesIO

from django.db.models import Avg, Count, Q
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from .models import PlanTask, PreparationPlan, Skill

# Site palette, so the charts belong to the same page as everything else.
NAVY = "#13294b"
NAVY_LIGHT = "#5a7099"
ORANGE = "#e84a27"
ORANGE_LIGHT = "#f4a48f"
GRID = "#e1e5ec"
INK = "#1c1c1c"
INK_MUTED = "#5b6472"

# 2x so the PNG is not soft on a retina screen. Everything below is sized in
# inches because that is what matplotlib works in: 7.2in at 110dpi is a
# 792px-wide image.
DPI = 110


def render_png(figure):
    """Draw a Figure into an in-memory PNG and return the bytes.

    BytesIO is the whole point of this function. The alternative is
    figure.savefig("/tmp/chart.png") followed by reading the file back, which
    means a write and a read of real disk for something that exists only long
    enough to be put on the wire. BytesIO is an in-memory file object with the
    same interface, so savefig writes into RAM instead.

    The RAM side of that trade is worth being honest about. The buffer holds
    the entire encoded PNG at once, so a request briefly costs roughly the
    size of the image, tens of kilobytes for these charts. That is fine here
    and it would stop being fine for a very large image or a high request
    rate, where the answer is to render once and cache the bytes rather than
    to redraw per request. What matters is that the cost is bounded and
    released: the buffer is closed in the finally block, the figure is a local
    that goes out of scope, and neither is held in a module-level registry.
    """
    buffer = BytesIO()
    try:
        # bbox_inches="tight" trims the whitespace matplotlib leaves around
        # the axes, which matters when the image sits inside a page rather
        # than in its own window.
        FigureCanvasAgg(figure)
        figure.savefig(buffer, format="png", dpi=DPI, bbox_inches="tight")
        return buffer.getvalue()
    finally:
        buffer.close()


def _style_axes(ax, *, title, xlabel="", ylabel=""):
    """Shared chart furniture: title, axis labels, grid, spines."""
    ax.set_title(title, fontsize=12, fontweight="bold", color=NAVY, pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9.5, color=INK_MUTED, labelpad=8)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9.5, color=INK_MUTED, labelpad=8)

    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def _empty(ax, message):
    """What a chart shows when its query returned nothing.

    The chart equivalent of a {% empty %} branch. Without this an empty
    database renders a set of blank axes, which reads as a broken page rather
    than as "there is no data yet".
    """
    ax.text(
        0.5, 0.5, message,
        ha="center", va="center", transform=ax.transAxes,
        fontsize=10, color=INK_MUTED, style="italic",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)


# ---------------------------------------------------------------------------
# Chart 1: skills per category (vertical bar)
# ---------------------------------------------------------------------------
def skills_by_category_png():
    """How the skill catalog is distributed across categories.

    ORM: values("category") sets the GROUP BY, annotate(Count) is the
    aggregate over each group. One row per category, computed by the database.
    """
    rows = (
        Skill.objects.values("category")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    labels = [Skill.Category(r["category"]).label for r in rows]
    values = [r["total"] for r in rows]

    figure = Figure(figsize=(7.2, 3.6), facecolor="white")
    ax = figure.subplots()

    if not values:
        _empty(ax, "No skills in the catalog yet.")
        _style_axes(ax, title="Skills by category")
        return render_png(figure)

    bars = ax.bar(labels, values, color=NAVY, width=0.58, zorder=3)
    # The tallest bar is the story, so it gets the accent colour.
    bars[0].set_color(ORANGE)

    ax.set_ylim(0, max(values) * 1.18)
    ax.yaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)

    # Value on top of each bar, so the reader never has to measure against
    # the axis to get the number.
    for bar, value in zip(bars, values):
        ax.annotate(
            str(value),
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 3), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=9.5, fontweight="bold", color=NAVY,
        )

    _style_axes(
        ax,
        title="Skills by category",
        xlabel="Category",
        ylabel="Number of skills",
    )
    return render_png(figure)


# ---------------------------------------------------------------------------
# Chart 2: plan progress (stacked horizontal bar, with legend)
# ---------------------------------------------------------------------------
def plan_progress_png():
    """Completed against remaining tasks, one bar per preparation plan.

    ORM: two Counts on the same relation, one of them filtered with Q, so the
    database returns done and total together in a single query per row set.
    """
    plans = (
        PreparationPlan.objects.select_related("candidate__user")
        .annotate(
            total=Count("tasks", distinct=True),
            done=Count(
                "tasks",
                filter=Q(tasks__status=PlanTask.Status.DONE),
                distinct=True,
            ),
        )
        .order_by("target_date")
    )

    labels, done, remaining = [], [], []
    for plan in plans:
        labels.append(plan.title)
        done.append(plan.done)
        remaining.append(plan.total - plan.done)

    figure = Figure(figsize=(7.2, 3.9), facecolor="white")
    ax = figure.subplots()

    if not labels:
        _empty(ax, "No preparation plans yet.")
        _style_axes(ax, title="Plan progress")
        return render_png(figure)

    y = range(len(labels))
    ax.barh(list(y), done, height=0.58, color=ORANGE, label="Tasks done", zorder=3)
    ax.barh(
        list(y), remaining, height=0.58, left=done,
        color=NAVY_LIGHT, label="Still to do", zorder=3,
    )

    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()  # soonest deadline at the top
    ax.xaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)

    # Completed-out-of-total at the end of each bar.
    for index, (d, r) in enumerate(zip(done, remaining)):
        ax.annotate(
            f"{d}/{d + r}",
            xy=(d + r, index), xytext=(6, 0), textcoords="offset points",
            va="center", fontsize=9, color=INK_MUTED,
        )

    # Task counts are whole numbers, so the axis should not offer halves.
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    _style_axes(
        ax,
        title="Plan progress: tasks completed against tasks remaining",
        xlabel="Tasks",
    )
    # Below the axes rather than inside them. A legend placed in a corner
    # covers whichever bar happens to reach that corner, which is exactly
    # what happened here with the last plan in the list.
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2,
        frameon=False, fontsize=9,
    )
    return render_png(figure)


# ---------------------------------------------------------------------------
# Chart 3: skill gap (grouped horizontal bar, with legend)
# ---------------------------------------------------------------------------
def skill_gap_png(limit=8):
    """Average proficiency against average required level, per skill.

    ORM: two Avg aggregates over the assessments relation, filtered to skills
    that actually have assessments, ordered by the weakest first. This is the
    chart the roadmap screen is really asking for: where is the gap widest.
    """
    skills = (
        Skill.objects.annotate(
            average_score=Avg("assessments__proficiency_score"),
            average_required=Avg("assessments__required_level"),
            learners=Count("assessments", distinct=True),
        )
        .filter(learners__gt=0)
        .order_by("average_score")[:limit]
    )

    labels = [s.name for s in skills]
    scores = [float(s.average_score or 0) for s in skills]
    required = [float(s.average_required or 0) for s in skills]

    figure = Figure(figsize=(7.2, 4.2), facecolor="white")
    ax = figure.subplots()

    if not labels:
        _empty(ax, "No skill has been assessed yet, so there is no gap to show.")
        _style_axes(ax, title="Widest skill gaps")
        return render_png(figure)

    height = 0.38
    positions = list(range(len(labels)))
    lower = [p + height / 2 for p in positions]
    upper = [p - height / 2 for p in positions]

    ax.barh(upper, required, height=height, color=NAVY_LIGHT,
            label="Required for the target role", zorder=3)
    ax.barh(lower, scores, height=height, color=ORANGE,
            label="Current average proficiency", zorder=3)

    ax.set_yticks(positions)
    ax.set_yticklabels(labels, fontsize=9)
    # The queryset is ordered weakest first, and barh puts index 0 at the
    # bottom, so without this the chart contradicts its own title.
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.xaxis.grid(True, color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)

    _style_axes(
        ax,
        title=f"Widest skill gaps (weakest {len(labels)} skills)",
        xlabel="Score out of 100",
    )
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2,
        frameon=False, fontsize=9,
    )
    return render_png(figure)


# ---------------------------------------------------------------------------
# Chart 4: task status share (pie, with legend)
# ---------------------------------------------------------------------------
def task_status_png():
    """Share of every task by status.

    ORM: values("status") + Count, the same grouping pattern as chart 1. A pie
    is defensible here and nowhere else on this page: the four statuses are
    mutually exclusive parts of one whole, which is the only thing a pie
    reads well.
    """
    rows = (
        PlanTask.objects.values("status")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    labels = [PlanTask.Status(r["status"]).label for r in rows]
    values = [r["total"] for r in rows]

    figure = Figure(figsize=(5.4, 3.9), facecolor="white")
    ax = figure.subplots()

    if not values:
        _empty(ax, "No tasks yet.")
        ax.set_title("Task status", fontsize=12, fontweight="bold", color=NAVY)
        return render_png(figure)

    colours = [ORANGE, NAVY, NAVY_LIGHT, ORANGE_LIGHT][: len(values)]
    total = sum(values)

    wedges, _, autotexts = ax.pie(
        values,
        colors=colours,
        autopct=lambda pct: f"{pct:.0f}%" if pct >= 6 else "",
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 2},
        textprops={"fontsize": 9.5, "fontweight": "bold"},
    )
    for text in autotexts:
        text.set_color("white")

    ax.set_title("Task status", fontsize=12, fontweight="bold", color=NAVY, pad=12)
    ax.legend(
        wedges,
        [f"{label} ({value})" for label, value in zip(labels, values)],
        title=f"{total} tasks",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=9,
    )
    ax.set_aspect("equal")
    return render_png(figure)
