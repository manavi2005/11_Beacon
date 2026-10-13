"""Smoke tests for the preparation app.

These are not an assignment requirement. They exist because the four graded
views in Section 2 are the deliverable, and a test that loads each one is the
cheapest way to notice if a later change breaks one of them.

Run with:  python manage.py test preparation
"""

import csv
import io
import json
import re
from datetime import datetime
from unittest import mock

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import exports
from .models import (
    CandidateProfile,
    PlanTask,
    PreparationPlan,
    Skill,
    SkillAssessment,
)
from django.contrib.auth.models import User


class GradedViewsTests(TestCase):
    """Each of the four Section 2 views answers, and uses the right template."""

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(
            name="SQL and relational modeling",
            category=Skill.Category.TECHNICAL,
            description="Interview-relevant competency.",
        )
        user = User.objects.create_user("acandidate", password="test-only-pw")
        cls.candidate = CandidateProfile.objects.create(
            user=user,
            target_role="Data Analyst",
            preparation_timeline_weeks=4,
        )
        cls.plan = PreparationPlan.objects.create(
            candidate=cls.candidate,
            title="Data Analyst sprint",
            focus_role="Data Analyst",
            target_date=timezone.localdate() + timezone.timedelta(weeks=4),
        )
        cls.task = PlanTask.objects.create(
            plan=cls.plan,
            skill=cls.skill,
            title="Write 5 JOIN queries",
            week_number=1,
        )

    def setUp(self):
        # Create and log in a test user for template tests
        self.user = User.objects.create_user("templateuser", password="test-only-pw")
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="templateuser", password="test-only-pw"))
    def test_fbv_httpresponse_renders_skill_list(self):
        """View 1: FBV built by hand out of loader.get_template + HttpResponse."""
        response = self.client.get(reverse("preparation:skill_catalog_manual"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.skill.name)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_fbv_render_renders_the_same_template(self):
        """View 2: the render() shortcut, reusing View 1's template."""
        response = self.client.get(reverse("preparation:skill_catalog_render"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "preparation/skill_list.html")
        self.assertContains(response, self.skill.name)

    def test_cbv_base_view_lists_plans(self):
        """View 3: a bare django.views.View that queries and renders in get()."""
        response = self.client.get(reverse("preparation:plan_board"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "preparation/plan_list.html")
        self.assertContains(response, self.plan.title)

    def test_cbv_generic_listview_lists_tasks(self):
        """View 4: generic ListView, with context_object_name honoured."""
        response = self.client.get(reverse("preparation:task_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "preparation/task_list.html")
        self.assertIn("tasks", response.context)
        self.assertContains(response, self.task.title)


class TemplateBehaviourTests(TestCase):
    """Section 3: inheritance, the {% empty %} branch, and no leaked comments."""

    def setUp(self):
        # Create and log in a test user for template tests
        self.user = User.objects.create_user("templateuser", password="test-only-pw")
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="templateuser", password="test-only-pw"))
    def test_every_page_extends_base_and_shows_the_nav(self):
        response = self.client.get(reverse("preparation:skill_catalog_render"))
        self.assertContains(response, "Team Career Coaches (Group 11)")
        self.assertContains(response, "Tasks (generic CBV)")

    def test_empty_branch_fires_when_the_filter_matches_nothing(self):
        Skill.objects.create(name="Python fundamentals", category=Skill.Category.TECHNICAL)
        response = self.client.get(reverse("preparation:skill_catalog_render"), {"q": "zzzz"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No skills match")
        self.assertNotContains(response, "Python fundamentals")

    def test_empty_catalog_gets_the_other_empty_message(self):
        """No filter and no rows should tell the reader how to load demo data."""
        response = self.client.get(reverse("preparation:skill_catalog_render"))
        self.assertContains(response, "The skill catalog is empty")

    def test_template_comments_are_not_rendered(self):
        """Regression guard.

        base.html once used a multi-line {# ... #} note. That form is
        single-line only, so Django printed it as page text on every page.
        """
        response = self.client.get(reverse("preparation:skill_catalog_render"))
        self.assertNotContains(response, "Site-wide skeleton")
        self.assertNotContains(response, "{#")


class UrlsAndNavigationTests(TestCase):
    """Assignment 3, Section 1: home page, navigation, PK detail pages."""

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(
            name="SQL and relational modeling",
            category=Skill.Category.TECHNICAL,
        )
        user = User.objects.create_user(
            "bpatel", first_name="Bharat", last_name="Patel",
            email="bpatel@example.edu", password="test-only-pw",
        )
        cls.candidate = CandidateProfile.objects.create(
            user=user, target_role="Data Analyst", preparation_timeline_weeks=4,
        )
        cls.plan = PreparationPlan.objects.create(
            candidate=cls.candidate, title="Data Analyst sprint",
            focus_role="Data Analyst",
            target_date=timezone.localdate() + timezone.timedelta(weeks=4),
        )
        cls.task = PlanTask.objects.create(
            plan=cls.plan, skill=cls.skill,
            title="Write 5 JOIN queries", week_number=1,
        )

    def setUp(self):
        # Log in before each test
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="bpatel", password="test-only-pw"))
    def test_root_url_is_not_a_404(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_nav_has_at_least_three_reversed_links(self):
        """Nav links must come from {% url %}, so a bad route name would fail
        to render rather than silently produce a dead link."""
        body = self.client.get("/").content.decode()
        # Match the opening tag loosely: the nav carries a class attribute
        # since the stylesheet moved into static/, and the test should not
        # break every time that markup is restyled.
        nav = body.split("<nav")[1].split("</nav>")[0]
        hrefs = [h for h in nav.split('href="')[1:]]
        self.assertGreaterEqual(len(hrefs), 3)
        for expected in ("/candidates/", "/search/skills/", "/insights/"):
            self.assertIn(expected, nav)

    def test_get_absolute_url_returns_a_working_pk_url(self):
        for obj in (self.skill, self.candidate, self.plan, self.task):
            with self.subTest(model=type(obj).__name__):
                url = obj.get_absolute_url()
                self.assertIn(str(obj.pk), url)
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_list_page_links_to_detail_page(self):
        """The end-to-end flow: list -> link -> detail."""
        body = self.client.get(reverse("preparation:candidate_list")).content.decode()
        self.assertIn(self.candidate.get_absolute_url(), body)
        response = self.client.get(self.candidate.get_absolute_url())
        self.assertContains(response, "Data Analyst")

    def test_unknown_pk_is_404_not_500(self):
        for url in ("/skills/9999/", "/candidates/9999/", "/plans/9999/", "/tasks/9999/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)


class OrmQueryTests(TestCase):
    """Assignment 3, Section 2: search, relationship spanning, aggregation."""

    @classmethod
    def setUpTestData(cls):
        cls.sql = Skill.objects.create(
            name="SQL and relational modeling", category=Skill.Category.TECHNICAL)
        cls.pitch = Skill.objects.create(
            name="Resume and elevator pitch", category=Skill.Category.COMMUNICATION)
        user = User.objects.create_user(
            "ekim", first_name="Eunji", last_name="Kim",
            email="ekim@example.edu", password="test-only-pw")
        cls.candidate = CandidateProfile.objects.create(
            user=user, target_role="Data Analyst", preparation_timeline_weeks=4)
        SkillAssessment.objects.create(
            candidate=cls.candidate, skill=cls.sql,
            proficiency_score=40, required_level=80)

    def setUp(self):
        # Log in before each test
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="ekim", password="test-only-pw"))
    # --- GET search -----------------------------------------------------
    def test_get_search_filters_by_name(self):
        r = self.client.get(reverse("preparation:skill_search"), {"q": "SQL"})
        self.assertContains(r, "SQL and relational modeling")
        self.assertNotContains(r, "Resume and elevator pitch")

    def test_get_search_is_shareable_as_a_url(self):
        url = reverse("preparation:skill_search") + "?q=Python"

        first_response = self.client.get(url)
        second_response = self.client.get(url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        first_html = first_response.content.decode()
        second_html = second_response.content.decode()

        # Remove CSRF tokens before comparing the rendered pages.
        first_html = re.sub(
            r'(<input[^>]*name="csrfmiddlewaretoken"[^>]*value=")[^"]*(")',
            r'\1CSRF_TOKEN\2',
            first_html,
        )
        second_html = re.sub(
            r'(<input[^>]*name="csrfmiddlewaretoken"[^>]*value=")[^"]*(")',
            r'\1CSRF_TOKEN\2',
            second_html,
        )

        self.assertEqual(first_html, second_html)

    def test_get_search_spans_relationships(self):
        """skill -> assessments -> candidate -> target_role, via __."""
        r = self.client.get(reverse("preparation:skill_search"), {"role": "Data Analyst"})
        self.assertContains(r, "SQL and relational modeling")
        self.assertNotContains(r, "Resume and elevator pitch")

    def test_get_search_empty_state(self):
        r = self.client.get(reverse("preparation:skill_search"), {"q": "zzzznomatch"})
        self.assertContains(r, "No skills match")

    def test_unknown_category_does_not_crash(self):
        """Regression guard.

        The category code comes straight from the query string. Passing it to
        Skill.Category() raised ValueError, so a hand-edited URL returned a
        500 instead of an empty result.
        """
        for bad in ("BOGUS", "tech", "' OR 1=1--"):
            with self.subTest(category=bad):
                r = self.client.get(reverse("preparation:skill_search"),
                                    {"category": bad})
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, "is not one of the skill categories")

    def test_valid_category_still_filters(self):
        r = self.client.get(reverse("preparation:skill_search"),
                            {"category": Skill.Category.TECHNICAL})
        self.assertContains(r, "SQL and relational modeling")
        self.assertNotContains(r, "Resume and elevator pitch")

    # --- POST search ----------------------------------------------------
    def test_post_search_finds_candidate_across_relationship(self):
        """CandidateProfile -> User via user__, one form field, several fields
        searched."""
        r = self.client.post(reverse("preparation:candidate_search"), {"term": "Eunji"})
        self.assertContains(r, "Eunji")

    def test_post_search_keeps_the_term_out_of_the_url(self):
        r = self.client.post(reverse("preparation:candidate_search"), {"term": "Eunji"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Eunji", r.request["QUERY_STRING"])

    def test_post_search_empty_state(self):
        r = self.client.post(reverse("preparation:candidate_search"), {"term": "zzzznomatch"})
        self.assertContains(r, "No candidate")

    def test_post_search_blank_term_lists_nobody(self):
        """A blank submission must not dump every candidate onto the page."""
        r = self.client.post(reverse("preparation:candidate_search"), {"term": "   "})
        self.assertContains(r, "No search term was entered")
        self.assertNotContains(r, "Eunji")

    def test_get_on_post_search_shows_form_without_results(self):
        r = self.client.get(reverse("preparation:candidate_search"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "<form")

    # --- aggregation ----------------------------------------------------
    def test_insights_totals_and_grouping(self):
        r = self.client.get(reverse("preparation:insights"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["totals"]["skills"], Skill.objects.count())
        self.assertEqual(r.context["totals"]["candidates"], CandidateProfile.objects.count())
        groups = {g["label"]: g["skill_count"] for g in r.context["by_category"]}
        self.assertEqual(sum(groups.values()), Skill.objects.count())

    def test_candidate_list_annotations_match_reality(self):
        r = self.client.get(reverse("preparation:candidate_list"))
        for row in r.context["candidates"]:
            with self.subTest(candidate=str(row)):
                self.assertEqual(row.assessment_count, row.assessments.count())
                self.assertEqual(row.plan_count, row.plans.count())


class StaticFilesTests(TestCase):
    """Assignment 3, Section 3: static configuration and CSS delivery."""

    def setUp(self):
        # Create and log in a test user for static files tests
        self.user = User.objects.create_user("staticuser", password="test-only-pw")
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="staticuser", password="test-only-pw"))
    def test_static_dir_is_on_the_search_path(self):
        from django.conf import settings
        from pathlib import Path
        self.assertIn(Path(settings.BASE_DIR) / "static", settings.STATICFILES_DIRS)

    def test_stylesheet_is_findable_by_the_staticfiles_finders(self):
        """finders.find() is what {% static %} resolves through, so this
        proves the file is reachable, not just that it exists on disk."""
        from django.contrib.staticfiles import finders
        self.assertIsNotNone(finders.find("css/beacon.css"))
        self.assertIsNotNone(finders.find("img/beacon-logo.svg"))

    def test_base_template_links_the_stylesheet_via_static(self):
        body = self.client.get("/").content.decode()
        self.assertIn('href="/static/css/beacon.css"', body)
        self.assertIn('rel="stylesheet"', body)

    def test_no_inline_style_block_remains(self):
        """The CSS moved to static/. An inline <style> block coming back would
        mean a page is carrying its own copy again."""
        for url in ("/", "/candidates/", "/insights/", "/search/skills/"):
            with self.subTest(url=url):
                self.assertNotIn("<style>", self.client.get(url).content.decode())

    def test_logo_is_served_and_is_an_svg(self):
        from django.contrib.staticfiles import finders
        path = finders.find("img/beacon-logo.svg")
        with open(path, encoding="utf-8") as fh:
            self.assertIn("<svg", fh.read(400))

    def test_every_page_carries_the_stylesheet(self):
        for url in ("/", "/skills/", "/candidates/", "/tasks/", "/insights/"):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "css/beacon.css")


class ChartTests(TestCase):
    """Assignment 3, Section 4: ORM-backed Matplotlib charts served as PNG."""

    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

    @classmethod
    def setUpTestData(cls):
        cls.sql = Skill.objects.create(
            name="SQL and relational modeling", category=Skill.Category.TECHNICAL)
        cls.pitch = Skill.objects.create(
            name="Resume and elevator pitch", category=Skill.Category.COMMUNICATION)
        user = User.objects.create_user(
            "dokafor", first_name="Daniel", last_name="Okafor",
            email="dokafor@example.edu", password="test-only-pw")
        cls.candidate = CandidateProfile.objects.create(
            user=user, target_role="Data Analyst", preparation_timeline_weeks=4)
        SkillAssessment.objects.create(
            candidate=cls.candidate, skill=cls.sql,
            proficiency_score=40, required_level=80)
        cls.plan = PreparationPlan.objects.create(
            candidate=cls.candidate, title="Data Analyst sprint",
            focus_role="Data Analyst",
            target_date=timezone.localdate() + timezone.timedelta(weeks=4))
        PlanTask.objects.create(
            plan=cls.plan, skill=cls.sql, title="Write 5 JOIN queries",
            week_number=1, status=PlanTask.Status.DONE)
        PlanTask.objects.create(
            plan=cls.plan, skill=cls.sql, title="Window functions drill",
            week_number=2)

    def setUp(self):
        # Log in before each test
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="dokafor", password="test-only-pw"))
    CHART_ROUTES = [
        "preparation:chart_skills_by_category",
        "preparation:chart_plan_progress",
        "preparation:chart_skill_gap",
        "preparation:chart_task_status",
    ]

    # --- image endpoint -------------------------------------------------
    def test_every_chart_endpoint_returns_a_real_png(self):
        """Not just a 200: the bytes must actually start with the PNG magic
        number, so an HTML error page cannot pass as an image."""
        for name in self.CHART_ROUTES:
            with self.subTest(route=name):
                r = self.client.get(reverse(name))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r["Content-Type"], "image/png")
                self.assertTrue(r.content.startswith(self.PNG_MAGIC))
                self.assertGreater(len(r.content), 1000)

    def test_content_length_matches_the_body(self):
        r = self.client.get(reverse("preparation:chart_skills_by_category"))
        self.assertEqual(int(r["Content-Length"]), len(r.content))

    def test_chart_urls_end_in_png(self):
        """The endpoint is addressable as an image, as the brief asks."""
        for name in self.CHART_ROUTES:
            with self.subTest(route=name):
                self.assertTrue(reverse(name).endswith(".png"))

    # --- ORM aggregation ------------------------------------------------
    def test_chart_data_follows_the_database(self):
        """Add a row, and the rendered chart changes. That is the difference
        between a live chart and a checked-in image."""
        before = self.client.get(reverse("preparation:chart_skills_by_category")).content
        Skill.objects.create(name="Python fundamentals",
                             category=Skill.Category.TECHNICAL)
        after = self.client.get(reverse("preparation:chart_skills_by_category")).content
        self.assertNotEqual(before, after)

    def test_page_aggregates_match_the_orm(self):
        r = self.client.get(reverse("preparation:charts"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["task_total"], PlanTask.objects.count())
        self.assertEqual(r.context["plan_total"], PreparationPlan.objects.count())
        self.assertEqual(
            sum(row["total"] for row in r.context["category_rows"]),
            Skill.objects.count(),
        )
        self.assertEqual(
            sum(row["total"] for row in r.context["status_rows"]),
            PlanTask.objects.count(),
        )

    # --- template integration -------------------------------------------
    def test_page_shows_every_chart_with_alt_text_and_a_caption(self):
        body = self.client.get(reverse("preparation:charts")).content.decode()
        for name in self.CHART_ROUTES:
            with self.subTest(route=name):
                self.assertIn(f'src="{reverse(name)}"', body)
        self.assertEqual(body.count("<figcaption>"), 4)

        # Scoped to the chart figures. The masthead logo also carries an alt
        # attribute, deliberately empty: it is decorative, because the BEACON
        # wordmark next to it already says the same thing, and a screen reader
        # announcing "Beacon logo Beacon" would be worse than silence.
        import re
        figures = re.findall(r'<figure class="chart">(.*?)</figure>', body, re.S)
        self.assertEqual(len(figures), 4)
        for figure in figures:
            alt = re.search(r'<img[^>]*\salt="([^"]*)"', figure, re.S)
            self.assertIsNotNone(alt, "a chart image is missing alt text")
            # Alt text should describe the data, not just repeat the title.
            self.assertGreater(len(" ".join(alt.group(1).split())), 40)

    # --- empty database -------------------------------------------------
    def test_charts_still_render_with_no_data(self):
        """An empty database must produce a chart saying so, not a traceback."""
        PlanTask.objects.all().delete()
        SkillAssessment.objects.all().delete()
        PreparationPlan.objects.all().delete()
        Skill.objects.all().delete()
        for name in self.CHART_ROUTES:
            with self.subTest(route=name):
                r = self.client.get(reverse(name))
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.content.startswith(self.PNG_MAGIC))

    # --- memory behaviour -----------------------------------------------
    def test_rendering_does_not_accumulate_figures(self):
        """The pyplot figure registry is the classic leak in this pattern.

        charts.py builds Figure() objects directly and never touches pyplot,
        so repeated requests must leave the registry empty. If someone
        switches to plt.figure() without plt.close(), this count climbs and
        the test fails.
        """
        import matplotlib.pyplot as plt
        plt.close("all")
        for _ in range(12):
            for name in self.CHART_ROUTES:
                self.client.get(reverse(name))
        self.assertEqual(
            plt.get_fignums(), [],
            "figures are accumulating: something is using pyplot without closing",
        )

    def test_renderer_uses_the_headless_backend(self):
        """Agg has no window system. Any interactive backend would fail on a
        server without a display."""
        import matplotlib
        self.assertEqual(matplotlib.get_backend().lower(), "agg")


# ===========================================================================
# ASSIGNMENT 4
# ===========================================================================
def _a4_fixture(cls):
    """Two skills, two candidates with different roles, three assessments."""
    cls.python = Skill.objects.create(
        name="Python fundamentals", category=Skill.Category.TECHNICAL
    )
    cls.sql = Skill.objects.create(
        name="SQL & relational modeling", category=Skill.Category.TECHNICAL
    )
    cls.pitch = Skill.objects.create(
        name="Resume & elevator pitch", category=Skill.Category.COMMUNICATION
    )
    analyst = CandidateProfile.objects.create(
        user=User.objects.create_user(
            "eunji", first_name="Eunji", email="eunji@example.edu",
            password="test-only-pw",
        ),
        target_role="Data Analyst", preparation_timeline_weeks=4,
    )
    trader = CandidateProfile.objects.create(
        user=User.objects.create_user("tquant", password="test-only-pw"),
        target_role="Quantitative Trader", preparation_timeline_weeks=6,
    )
    SkillAssessment.objects.create(
        candidate=analyst, skill=cls.sql, proficiency_score=40, required_level=80
    )
    SkillAssessment.objects.create(
        candidate=analyst, skill=cls.python, proficiency_score=75, required_level=70
    )
    SkillAssessment.objects.create(
        candidate=trader, skill=cls.python, proficiency_score=30, required_level=90
    )


class InternalApiTests(TestCase):
    """Part 1.1: GET-only, JSON-only, chart-ready rows from the models."""

    @classmethod
    def setUpTestData(cls):
        _a4_fixture(cls)

    def setUp(self):
        # Log in before each test
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="tquant", password="test-only-pw"))
    def test_skill_summary_is_a_flat_list_aggregated_per_skill(self):
        r = self.client.get(reverse("preparation:api_skill_summary"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        rows = {row["skill"]: row for row in r.json()}
        self.assertEqual(set(rows), {"Python fundamentals", "SQL & relational modeling",
                                     "Resume & elevator pitch"})
        python = rows["Python fundamentals"]
        self.assertEqual(python["learners"], 2)
        self.assertEqual(python["avg_proficiency"], 52.5)
        self.assertEqual(python["avg_required"], 80.0)
        self.assertEqual(python["avg_gap"], 27.5)
        # Unassessed skills stay listed, with nulls rather than fake zeros.
        self.assertEqual(rows["Resume & elevator pitch"]["learners"], 0)
        self.assertIsNone(rows["Resume & elevator pitch"]["avg_gap"])

    def test_assessments_are_anonymous(self):
        r = self.client.get(reverse("preparation:api_assessments"))
        rows = r.json()
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            set(rows[0]),
            {"skill", "category", "experience", "proficiency", "required", "gap",
             "assessed_on"},
        )
        body = r.content.decode()
        for personal in ("Eunji", "eunji", "example.edu"):
            self.assertNotIn(personal, body)

    def test_public_api_allows_cross_origin_reads(self):
        """The Vega-Lite editor fetches from another origin."""
        r = self.client.get(reverse("preparation:api_skill_summary"))
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")

    def test_preflight_allows_public_site_to_read_localhost(self):
        """Chrome asks before vega.github.io may read from 127.0.0.1."""
        r = self.client.options(
            reverse("preparation:api_skill_summary"),
            headers={"Origin": "https://vega.github.io",
                     "Access-Control-Request-Private-Network": "true"},
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "*")
        self.assertEqual(r["Access-Control-Allow-Private-Network"], "true")
        self.assertNotIn("PUT", r["Access-Control-Allow-Methods"])

    def test_apis_are_get_only(self):
        for name in ("api_skill_summary", "api_assessments"):
            self.assertEqual(self.client.post(reverse(f"preparation:{name}")).status_code, 405)


class VegaLiteTests(TestCase):
    """Part 1.2: specs use data.url, the page embeds them, PNGs render."""

    @classmethod
    def setUpTestData(cls):
        _a4_fixture(cls)

    def setUp(self):
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="tquant", password="test-only-pw"))
    def test_specs_load_data_by_url_and_never_inline(self):
        from . import vega

        for number, info in vega.CHARTS.items():
            with self.subTest(chart=number):
                spec = vega.load_spec(number)
                self.assertIn("vega-lite/v6", spec["$schema"])
                self.assertEqual(spec["data"], {"url": reverse(info["api_name"])})
                self.assertNotIn('"values"', json.dumps(spec))

    def test_one_bar_chart_and_one_scatter(self):
        from . import vega

        self.assertEqual(vega.load_spec(1)["mark"]["type"], "bar")
        marks = [layer["mark"]["type"] for layer in vega.load_spec(2)["layer"]]
        self.assertIn("point", marks)

    def test_spec_endpoint_returns_absolute_data_url(self):
        r = self.client.get(reverse("preparation:vega_lite_spec", args=[1]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["url"], "http://testserver/api/skills/summary/")

    def test_png_endpoints_return_images(self):
        for number in (1, 2):
            with self.subTest(chart=number):
                r = self.client.get(reverse("preparation:vega_lite_png", args=[number]))
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r["Content-Type"], "image/png")
                self.assertTrue(r.content.startswith(b"\x89PNG"))

    def test_unknown_chart_is_404(self):
        self.assertEqual(
            self.client.get(reverse("preparation:vega_lite_png", args=[9])).status_code, 404
        )

    def test_page_embeds_both_charts(self):
        r = self.client.get(reverse("preparation:vega_lite"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "vega-embed@")
        for number in (1, 2):
            self.assertContains(r, f'id="vega-chart-{number}"')
            self.assertContains(r, f"/vega-lite/chart{number}.json")
        self.assertContains(r, reverse("preparation:vega_lite"))  # in the nav


def _jobicy_response(jobs, status=200):
    response = mock.Mock(status_code=status)
    response.json.return_value = {"jobs": jobs}
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    else:
        response.raise_for_status.return_value = None
    return response


FAKE_JOBS = [
    {"jobTitle": "Data Analyst", "companyName": "Acme", "url": "https://jobicy.com/jobs/1",
     "jobExcerpt": "SQL every day", "jobDescription": "<p>PostgreSQL and Python</p>",
     "pubDate": "2026-09-30 10:00:00"},
    {"jobTitle": "BI Analyst", "companyName": "Globex", "url": "https://jobicy.com/jobs/2",
     "jobExcerpt": "Dashboards", "jobDescription": "<p>Strong <b>SQL</b>. Digital tools.</p>",
     "pubDate": "2026-09-29 10:00:00"},
]


class MarketDemandTests(TestCase):
    """Part 2: requests.get to Jobicy, combined with internal gaps, as JSON.

    requests.get is always mocked: a test suite must not depend on, or add
    load to, someone else's server.
    """

    @classmethod
    def setUpTestData(cls):
        _a4_fixture(cls)

    def setUp(self):
        cache.clear()
        # /market/ became login-protected in A5. The JSON endpoint beneath it
        # stays open on purpose, but the page itself is part of the site, so
        # these tests sign in like any other visitor would.
        self.assertTrue(
            self.client.login(username="tquant", password="test-only-pw")
        )

    def _get(self, q="data analyst"):
        return self.client.get(reverse("preparation:api_market_demand"), {"q": q})

    @mock.patch("preparation.market.requests.get")
    def test_calls_jobicy_with_params_and_timeout(self, get):
        get.return_value = _jobicy_response(FAKE_JOBS)
        self._get("data analyst")
        _, kwargs = get.call_args
        self.assertEqual(kwargs["params"]["tag"], "data analyst")
        self.assertEqual(kwargs["timeout"], 5)
        get.return_value.raise_for_status.assert_called_once()

    @mock.patch("preparation.market.requests.get")
    def test_triangulates_demand_with_the_role_cohort(self, get):
        get.return_value = _jobicy_response(FAKE_JOBS)
        r = self._get("data analyst")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["postings_analyzed"], 2)
        self.assertTrue(data["cohort"]["matched_target_role"])
        rows = {row["skill"]: row for row in data["skills"]}

        sql = rows["SQL & relational modeling"]
        self.assertEqual(sql["postings_mentioning"], 2)
        self.assertEqual(sql["demand_pct"], 100.0)
        self.assertEqual(sql["avg_gap"], 40.0)       # analyst only: 80 - 40
        self.assertEqual(sql["priority"], 40.0)

        python = rows["Python fundamentals"]
        self.assertEqual(python["postings_mentioning"], 1)
        self.assertEqual(python["avg_gap"], -5.0)    # trader's 30/90 is excluded
        self.assertEqual(python["priority"], 0.0)    # ahead already, so no priority

        self.assertEqual(data["skills"][0]["skill"], "SQL & relational modeling")

    @mock.patch("preparation.market.requests.get")
    def test_unmatched_role_falls_back_to_all_candidates_and_says_so(self, get):
        get.return_value = _jobicy_response(FAKE_JOBS)
        data = self._get("astronaut").json()
        self.assertFalse(data["cohort"]["matched_target_role"])
        python = {row["skill"]: row for row in data["skills"]}["Python fundamentals"]
        self.assertEqual(python["avg_gap"], 27.5)

    @mock.patch("preparation.market.requests.get")
    def test_nothing_is_stored_and_raw_text_is_not_leaked(self, get):
        get.return_value = _jobicy_response(FAKE_JOBS)
        before = Skill.objects.count(), SkillAssessment.objects.count()
        data = self._get().json()
        self.assertEqual((Skill.objects.count(), SkillAssessment.objects.count()), before)
        self.assertNotIn("_text", data["sample_postings"][0])
        self.assertEqual(data["sample_postings"][0]["url"], "https://jobicy.com/jobs/1")

    @mock.patch("preparation.market.requests.get")
    def test_repeat_queries_are_served_from_cache(self, get):
        get.return_value = _jobicy_response(FAKE_JOBS)
        self._get("data analyst")
        self._get("Data Analyst")
        self.assertEqual(get.call_count, 1)

    def test_missing_query_is_400(self):
        r = self.client.get(reverse("preparation:api_market_demand"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())

    @mock.patch("preparation.market.requests.get")
    def test_upstream_failures_become_clean_json_errors(self, get):
        cases = [
            (requests.Timeout(), 504),
            (requests.ConnectionError(), 502),
        ]
        for exc, status in cases:
            with self.subTest(exc=type(exc).__name__):
                cache.clear()
                get.side_effect = exc
                r = self._get()
                self.assertEqual(r.status_code, status)
                self.assertEqual(r["Content-Type"], "application/json")
                self.assertIn("error", r.json())

    @mock.patch("preparation.market.requests.get")
    def test_http_error_status_is_502(self, get):
        get.return_value = _jobicy_response([], status=503)
        r = self._get()
        self.assertEqual(r.status_code, 502)
        self.assertIn("503", r.json()["error"])

    @mock.patch("preparation.market.requests.get")
    def test_non_json_body_is_502(self, get):
        response = _jobicy_response([])
        response.json.side_effect = ValueError("not json")
        get.return_value = response
        self.assertEqual(self._get().status_code, 502)

    @mock.patch("preparation.market.requests.get")
    def test_page_renders_report_and_credits_jobicy(self, get):
        get.return_value = _jobicy_response(FAKE_JOBS)
        r = self.client.get(reverse("preparation:market"), {"q": "data analyst"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "SQL &amp; relational modeling")
        self.assertContains(r, 'href="https://jobicy.com/jobs/1"')
        self.assertContains(r, "https://jobicy.com")

    @mock.patch("preparation.market.requests.get")
    def test_page_shows_a_message_when_jobicy_is_down(self, get):
        get.side_effect = requests.Timeout()
        r = self.client.get(reverse("preparation:market"), {"q": "data analyst"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Could not load job postings")

    def test_page_without_query_does_not_call_jobicy(self):
        with mock.patch("preparation.market.requests.get") as get:
            r = self.client.get(reverse("preparation:market"))
        self.assertEqual(r.status_code, 200)
        get.assert_not_called()


class ExportAndReportTests(TestCase):
    """Assignment 4, Part 3: CSV export, JSON export, and the reports page."""

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(
            name="SQL and relational modeling", category=Skill.Category.TECHNICAL)
        user = User.objects.create_user(
            "bpatel", first_name="Bharat", last_name="Patel",
            email="bpatel@example.edu", password="test-only-pw")
        cls.candidate = CandidateProfile.objects.create(
            user=user, target_role="Data Analyst",
            experience_level=CandidateProfile.ExperienceLevel.NEW_GRAD,
            preparation_timeline_weeks=4)
        SkillAssessment.objects.create(
            candidate=cls.candidate, skill=cls.skill,
            proficiency_score=40, required_level=80)
        cls.plan = PreparationPlan.objects.create(
            candidate=cls.candidate, title="Data Analyst sprint",
            focus_role="Data Analyst",
            target_date=timezone.localdate() + timezone.timedelta(weeks=4))
        PlanTask.objects.create(plan=cls.plan, skill=cls.skill,
                                title="Write 5 JOIN queries", week_number=1,
                                status=PlanTask.Status.DONE)
        PlanTask.objects.create(plan=cls.plan, skill=cls.skill,
                                title="Window functions drill", week_number=2)

    def setUp(self):
        # Log in before each test
        # assertTrue, not a bare call: Client.login() returns False on a bad
        # username and the test then runs anonymous. Against a public route
        # that still passes, which is how five of these were silently broken.
        self.assertTrue(self.client.login(username="bpatel", password="test-only-pw"))
    CSV_URL = "preparation:export_candidates_csv"
    JSON_URL = "preparation:export_candidates_json"
    FILENAME = re.compile(r'filename="candidates_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.(csv|json)"')

    # --- CSV ------------------------------------------------------------
    def test_csv_is_served_as_a_download(self):
        r = self.client.get(reverse(self.CSV_URL))
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        self.assertTrue(r["Content-Disposition"].startswith("attachment;"))

    def test_csv_filename_is_timestamped(self):
        r = self.client.get(reverse(self.CSV_URL))
        self.assertRegex(r["Content-Disposition"], self.FILENAME)

    def test_csv_first_row_is_headers_then_one_row_per_record(self):
        r = self.client.get(reverse(self.CSV_URL))
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8"))))
        self.assertEqual(rows[0], [label for _, label in exports.EXPORT_COLUMNS])
        self.assertEqual(len(rows) - 1, CandidateProfile.objects.count())

    def test_csv_rows_are_ordered_deterministically(self):
        """Meta.ordering on this model is -updated_at, so an unordered export
        would reshuffle whenever a profile is touched. Two downloads of
        unchanged data must be byte-identical apart from the timestamp."""
        first = self.client.get(reverse(self.CSV_URL)).content
        second = self.client.get(reverse(self.CSV_URL)).content
        self.assertEqual(first, second)

    def test_csv_writes_empty_cells_not_the_string_none(self):
        r = self.client.get(reverse(self.CSV_URL))
        self.assertNotIn(",None,", r.content.decode())

    # --- JSON -----------------------------------------------------------
    def test_json_is_served_as_a_download(self):
        r = self.client.get(reverse(self.JSON_URL))
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/json", r["Content-Type"])
        self.assertTrue(r["Content-Disposition"].startswith("attachment;"))
        self.assertRegex(r["Content-Disposition"], self.FILENAME)

    def test_json_carries_the_required_metadata(self):
        payload = json.loads(self.client.get(reverse(self.JSON_URL)).content)
        self.assertEqual(
            set(payload), {"generated_at", "record_count", "candidates"})
        self.assertEqual(payload["record_count"], len(payload["candidates"]))
        self.assertEqual(payload["record_count"], CandidateProfile.objects.count())
        # generated_at must be a parseable ISO timestamp, not free text.
        datetime.fromisoformat(payload["generated_at"])

    def test_json_is_pretty_printed(self):
        """json_dumps_params={"indent": 2}: a download a human opens should
        not be one long line."""
        body = self.client.get(reverse(self.JSON_URL)).content.decode()
        self.assertIn('\n  "record_count"', body)

    # --- the invariant that matters -------------------------------------
    def test_csv_and_json_describe_the_same_records(self):
        """Both are built from exports.candidate_rows(). If someone later
        gives one of them its own query, the two downloads drift apart
        silently; this is what catches that."""
        csv_rows = list(csv.reader(io.StringIO(
            self.client.get(reverse(self.CSV_URL)).content.decode("utf-8"))))
        payload = json.loads(self.client.get(reverse(self.JSON_URL)).content)
        self.assertEqual(len(csv_rows) - 1, payload["record_count"])
        self.assertEqual(
            [row[0] for row in csv_rows[1:]],
            [str(rec["id"]) for rec in payload["candidates"]],
        )
        self.assertEqual(len(csv_rows[0]), len(payload["candidates"][0]))

    # --- reports page ---------------------------------------------------
    def test_reports_page_renders_with_totals_and_groupings(self):
        r = self.client.get(reverse("preparation:reports"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["totals"]["candidates"], CandidateProfile.objects.count())
        self.assertEqual(r.context["totals"]["tasks"], PlanTask.objects.count())
        # at least two grouped summaries, as the brief requires
        self.assertTrue(r.context["by_experience"])
        self.assertTrue(r.context["by_role"])
        self.assertTrue(r.context["by_plan"])

    def test_grouped_summaries_add_up_to_the_totals(self):
        r = self.client.get(reverse("preparation:reports"))
        self.assertEqual(
            sum(row["candidates"] for row in r.context["by_experience"]),
            r.context["totals"]["candidates"])
        self.assertEqual(
            sum(row["tasks_total"] for row in r.context["by_plan"]),
            r.context["totals"]["tasks"])

    def test_reports_page_links_both_downloads(self):
        body = self.client.get(reverse("preparation:reports")).content.decode()
        self.assertIn(reverse(self.CSV_URL), body)
        self.assertIn(reverse(self.JSON_URL), body)
        self.assertIn("Download CSV", body)
        self.assertIn("Download JSON", body)

    def test_reports_page_is_reachable_from_the_nav(self):
        body = self.client.get("/").content.decode()
        self.assertIn(reverse("preparation:reports"), body)

    # --- empty database -------------------------------------------------
    def test_everything_survives_an_empty_database(self):
        """The {% empty %} branches and a header-only CSV, rather than a 500."""
        PlanTask.objects.all().delete()
        PreparationPlan.objects.all().delete()
        SkillAssessment.objects.all().delete()
        CandidateProfile.objects.all().delete()

        page = self.client.get(reverse("preparation:reports"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "No candidates yet")

        csv_resp = self.client.get(reverse(self.CSV_URL))
        rows = list(csv.reader(io.StringIO(csv_resp.content.decode("utf-8"))))
        self.assertEqual(len(rows), 1, "only the header row should remain")

        payload = json.loads(self.client.get(reverse(self.JSON_URL)).content)
        self.assertEqual(payload["record_count"], 0)
        self.assertEqual(payload["candidates"], [])


class AuthenticationTests(TestCase):
    """Assignment 5, Part 1: login, signup, logout, and what they protect.

    Part 1 shipped without tests of its own. These cover the behaviour the
    brief asks for, and the two things that are easy to get wrong and silent
    when you do: the redirect settings, and an open redirect on ?next=.
    """

    PASSWORD = "Str0ngPass!2026"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("areader", password=cls.PASSWORD)

    # --- 1.1 login and signup pages -------------------------------------
    def test_login_page_renders_a_form(self):
        r = self.client.get(reverse("preparation:login"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "registration/login.html")
        self.assertContains(r, "csrfmiddlewaretoken")
        self.assertContains(r, 'name="username"')
        self.assertContains(r, 'name="password"')

    def test_signup_page_renders_a_form(self):
        r = self.client.get(reverse("preparation:signup"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "registration/signup.html")
        self.assertContains(r, "csrfmiddlewaretoken")

    def test_login_with_good_credentials(self):
        r = self.client.post(reverse("preparation:login"),
                             {"username": "areader", "password": self.PASSWORD})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_login_with_bad_credentials_re_renders_with_an_error(self):
        r = self.client.post(reverse("preparation:login"),
                             {"username": "areader", "password": "wrong"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["form"].is_valid())
        # Still anonymous.
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_signup_creates_the_account_and_signs_them_in(self):
        r = self.client.post(reverse("preparation:signup"),
                             {"username": "brandnew",
                              "password1": self.PASSWORD,
                              "password2": self.PASSWORD})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="brandnew").exists())
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_signup_applies_the_password_validators(self):
        """AUTH_PASSWORD_VALIDATORS from base.py should reject '12345'."""
        r = self.client.post(reverse("preparation:signup"),
                             {"username": "weakling",
                              "password1": "12345", "password2": "12345"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="weakling").exists())

    # --- 1.2 logout ------------------------------------------------------
    def test_logout_requires_post(self):
        """GET logout is reachable by any <img src>, so Django 5 refuses it."""
        self.client.login(username="areader", password=self.PASSWORD)
        self.assertEqual(self.client.get(reverse("preparation:logout")).status_code, 405)
        # still signed in
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_logout_via_post_ends_the_session(self):
        self.assertTrue(self.client.login(username="areader", password=self.PASSWORD))
        r = self.client.post(reverse("preparation:logout"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 302)

    # --- 1.3 the three settings -----------------------------------------
    def test_the_three_auth_settings_are_configured(self):
        """In base.py, not production.py: defined only in production,
        development falls back to Django's /accounts/profile/ default."""
        from django.conf import settings
        self.assertEqual(resolve_url(settings.LOGIN_URL), reverse("preparation:login"))
        self.assertEqual(resolve_url(settings.LOGIN_REDIRECT_URL),
                         reverse("preparation:dashboard"))
        self.assertEqual(resolve_url(settings.LOGOUT_REDIRECT_URL),
                         reverse("preparation:login"))

    def test_login_redirect_target_actually_exists(self):
        from django.conf import settings
        self.client.login(username="areader", password=self.PASSWORD)
        self.assertEqual(
            self.client.get(resolve_url(settings.LOGIN_REDIRECT_URL)).status_code, 200)

    def test_login_honours_next_then_lands_on_the_configured_page(self):
        r = self.client.post(reverse("preparation:login"),
                             {"username": "areader", "password": self.PASSWORD,
                              "next": reverse("preparation:reports")})
        self.assertRedirects(r, reverse("preparation:reports"))

    def test_next_cannot_be_used_as_an_open_redirect(self):
        """?next=https://evil.example.com must not send the user off-site.

        Without url_has_allowed_host_and_scheme our own login form becomes a
        credible-looking redirector for phishing.
        """
        r = self.client.post(reverse("preparation:login"),
                             {"username": "areader", "password": self.PASSWORD,
                              "next": "https://evil.example.com/steal"})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("evil.example.com", r["Location"])

    # --- 1.4 protected sections and APIs ---------------------------------
    PROTECTED_PAGES = ["/", "/skills/", "/candidates/", "/tasks/", "/insights/",
                       "/charts/", "/vega-lite/", "/market/", "/reports/",
                       "/reports/candidates.csv", "/reports/candidates.json",
                       "/api/skills/"]

    def test_anonymous_users_are_sent_to_login(self):
        for url in self.PROTECTED_PAGES:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302, f"{url} is not protected")
                self.assertIn(reverse("preparation:login"), r["Location"])

    def test_signed_in_users_can_reach_every_protected_page(self):
        self.assertTrue(self.client.login(username="areader", password=self.PASSWORD))
        for url in self.PROTECTED_PAGES:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_protected_json_api_answers_401_not_a_redirect(self):
        """A JSON client cannot do anything with a 302 to an HTML page."""
        r = self.client.get(reverse("preparation:api_whoami"))
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertIn("error", json.loads(r.content))

    def test_protected_json_api_answers_when_signed_in(self):
        self.assertTrue(self.client.login(username="areader", password=self.PASSWORD))
        r = self.client.get(reverse("preparation:api_whoami"))
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.content)
        self.assertTrue(body["authenticated"])
        self.assertEqual(body["username"], "areader")

    def test_login_and_signup_stay_reachable_while_anonymous(self):
        """Protecting everything else must not lock people out of the door."""
        for name in ("preparation:login", "preparation:signup"):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    # --- 1.5 navigation ---------------------------------------------------
    def test_nav_hides_protected_links_before_login(self):
        body = self.client.get(reverse("preparation:login")).content.decode()
        nav = body.split("<nav")[1].split("</nav>")[0]
        for hidden in (reverse("preparation:reports"), reverse("preparation:insights"),
                       reverse("preparation:charts")):
            self.assertNotIn(hidden, nav)
        self.assertIn(reverse("preparation:login"), nav)
        self.assertIn(reverse("preparation:signup"), nav)

    def test_nav_shows_protected_links_after_login(self):
        self.assertTrue(self.client.login(username="areader", password=self.PASSWORD))
        nav = self.client.get("/").content.decode().split("<nav")[1].split("</nav>")[0]
        for shown in (reverse("preparation:reports"), reverse("preparation:insights"),
                      reverse("preparation:charts")):
            self.assertIn(shown, nav)
        self.assertIn("Log Out", nav)
        self.assertNotIn(reverse("preparation:signup"), nav)

    def test_logout_control_is_a_post_form_not_a_link(self):
        """It has to be a form, because the view is POST-only. This is why
        the nav needs a button styled to match the links beside it."""
        self.assertTrue(self.client.login(username="areader", password=self.PASSWORD))
        nav = self.client.get("/").content.decode().split("<nav")[1].split("</nav>")[0]
        self.assertIn(f'action="{reverse("preparation:logout")}"', nav)
        self.assertIn('method="post"', nav)
        self.assertIn("csrfmiddlewaretoken", nav)


@override_settings(
    SOCIALACCOUNT_PROVIDERS={
        "google": {
            "APP": {"client_id": "test-client-id", "secret": "test-secret", "key": ""},
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {"access_type": "online"},
            "VERIFIED_EMAIL": True,
        }
    }
)
class GoogleOAuthConfiguredTests(TestCase):
    """Assignment 5, Part 2: Google OAuth, with credentials present.

    Fake credentials via override_settings. The real ones live in .env and
    are absent in CI, so without this the button would never render here and
    these tests would pass by testing nothing.

    Nothing contacts Google: we assert on the redirect we build and send, not
    on what Google would answer.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("oauthy", password="Str0ngPass!2026")

    def test_button_appears_on_both_pages(self):
        for route in ("preparation:login", "preparation:signup"):
            with self.subTest(page=route):
                r = self.client.get(reverse(route))
                self.assertContains(r, "Continue with Google")
                self.assertContains(r, reverse("google_login"))

    def test_button_posts_with_a_csrf_token(self):
        """A GET-startable login flow can be triggered by any page that makes
        the browser fetch a URL."""
        body = self.client.get(reverse("preparation:login")).content.decode()
        form = body.split('class="oauth__form"')[1].split("</form>")[0]
        self.assertIn("csrfmiddlewaretoken", form)
        self.assertIn('method="post"', body.split('class="oauth"')[1].split("</form>")[0])

    def test_google_login_redirects_to_google_with_the_right_parameters(self):
        """The actual OAuth handshake: we send the user to Google's consent
        screen with our client id and a callback on our own domain."""
        r = self.client.post(reverse("google_login"))
        self.assertEqual(r.status_code, 302)
        target = r["Location"]
        self.assertTrue(target.startswith("https://accounts.google.com/"), target)

        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(target).query)
        self.assertEqual(params["client_id"], ["test-client-id"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertIn("profile", params["scope"][0])
        self.assertIn("email", params["scope"][0])
        self.assertTrue(
            params["redirect_uri"][0].endswith("/accounts/google/login/callback/"),
            params["redirect_uri"][0],
        )

    def test_the_secret_never_reaches_the_browser(self):
        """The client id is public by design; the secret must never be."""
        for route in ("preparation:login", "preparation:signup"):
            with self.subTest(page=route):
                body = self.client.get(reverse(route)).content.decode()
                self.assertNotIn("test-secret", body)
        self.assertNotIn("test-secret", self.client.post(reverse("google_login"))["Location"])

    def test_callback_route_exists(self):
        """The URI registered with Google has to resolve, or every login
        comes back to a 404 after the user has already consented."""
        self.assertEqual(reverse("google_callback"), "/accounts/google/login/callback/")

    def test_username_password_login_still_works(self):
        """Adding allauth's backend must not displace ModelBackend, or every
        account from Part 1, including the superuser, stops working."""
        self.assertTrue(self.client.login(username="oauthy", password="Str0ngPass!2026"))
        self.assertEqual(self.client.get("/").status_code, 200)


class GoogleOAuthNotConfiguredTests(TestCase):
    """The same site on a machine with no Google credentials.

    This is CI, and any teammate who has not set up .env. The site has to
    stay fully usable.
    """

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {"APP": {"client_id": "", "secret": "", "key": ""}}
        }
    )
    def test_button_is_hidden_when_credentials_are_absent(self):
        """Better no button than one that sends the user to an error page."""
        for route in ("preparation:login", "preparation:signup"):
            with self.subTest(page=route):
                r = self.client.get(reverse(route))
                self.assertEqual(r.status_code, 200)
                self.assertNotContains(r, "Continue with Google")

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {"APP": {"client_id": "id-but-no-secret", "secret": "", "key": ""}}
        }
    )
    def test_half_configured_counts_as_not_configured(self):
        """An id with no secret fails at the token exchange, which is a much
        more confusing failure than the button being absent."""
        r = self.client.get(reverse("preparation:login"))
        self.assertNotContains(r, "Continue with Google")

    def test_login_page_still_renders_without_credentials(self):
        r = self.client.get(reverse("preparation:login"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'name="username"')


class SiteDomainCommandTests(TestCase):
    """set_site_domain: the deploy step that points allauth at the real host."""

    def test_sets_the_domain(self):
        from django.contrib.sites.models import Site
        call_command("set_site_domain", "beacon.pythonanywhere.com", stdout=io.StringIO())
        self.assertEqual(Site.objects.get(pk=settings.SITE_ID).domain,
                         "beacon.pythonanywhere.com")

    def test_rejects_a_full_url(self):
        """Passing a URL fails later as a broken callback, so fail now."""
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("set_site_domain", "https://example.com/", stdout=io.StringIO())


class OAuthDependencyTests(TestCase):
    """The Google callback decodes a JWT, and that import is a separate extra.

    Regression guard. requirements.txt originally pinned plain
    django-allauth, which installs fine and serves the login page fine: the
    button renders, and the redirect to Google is correct. The missing
    dependency only surfaces when Google redirects BACK, because
    allauth.socialaccount.internal.jwtkit imports jwt lazily to verify the
    id_token. Production hit ModuleNotFoundError: No module named 'jwt' at
    exactly that point.

    The lesson for the rest of the suite: the other OAuth tests assert on the
    request we send and never contact Google, which is right, but it left the
    return half of the handshake completely uncovered. This test covers the
    one part of it that does not need a network call.
    """

    def test_pyjwt_is_installed(self):
        try:
            import jwt  # noqa: F401
        except ImportError:  # pragma: no cover
            self.fail(
                "PyJWT is missing. allauth needs it to verify Google's "
                "id_token. Install django-allauth[socialaccount], not plain "
                "django-allauth."
            )

    def test_allauth_can_resolve_its_jwt_helper(self):
        """allauth defers the jwt import, so a plain `import jwt` passing is
        not quite proof. This touches the attribute allauth itself reaches
        for in the callback."""
        from allauth.socialaccount.internal import jwtkit

        self.assertTrue(hasattr(jwtkit, "verify_and_decode"))
        self.assertIsNotNone(jwtkit.jwt.PyJWTError)

    def test_requirements_pins_the_socialaccount_extra(self):
        """Installing the right thing on a fresh machine depends on this
        line, and nothing else in the suite reads it."""
        import pathlib

        text = pathlib.Path("requirements.txt").read_text()
        self.assertIn("django-allauth[socialaccount]", text)


# ===========================================================================
# ASSIGNMENT 5, PART 3 - one public API, every other API protected
# ===========================================================================
class PublicVsProtectedApiTests(TestCase):
    """Exactly one JSON API answers without a login: /api/skills/summary/."""

    PROTECTED_APIS = [
        "/api/assessments/",
        "/api/market-demand/?q=analyst",
        "/vega-lite/chart1.json",
        "/vega-lite/chart2.json",
        "/api/whoami/",
    ]

    @classmethod
    def setUpTestData(cls):
        _a4_fixture(cls)

    def test_public_api_needs_no_login(self):
        r = self.client.get(reverse("preparation:api_skill_summary"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertIsInstance(r.json(), list)

    def test_public_api_is_aggregates_only(self):
        """Nothing in it identifies a person."""
        body = self.client.get(reverse("preparation:api_skill_summary")).content.decode()
        for personal in ("eunji", "tquant", "example.edu", "Eunji"):
            self.assertNotIn(personal, body)
        row = self.client.get(reverse("preparation:api_skill_summary")).json()[0]
        self.assertEqual(
            set(row),
            {"skill", "category", "learners", "avg_proficiency", "avg_required",
             "avg_gap", "tasks"},
        )

    def test_public_api_csv_form_matches_the_json(self):
        r = self.client.get(reverse("preparation:api_skill_summary"), {"format": "csv"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        lines = r.content.decode().strip().splitlines()
        self.assertEqual(
            lines[0], "skill,category,learners,avg_proficiency,avg_required,avg_gap,tasks"
        )
        json_rows = self.client.get(reverse("preparation:api_skill_summary")).json()
        self.assertEqual(len(lines) - 1, len(json_rows))

    def test_every_other_api_answers_401_json_when_signed_out(self):
        for url in self.PROTECTED_APIS:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 401, f"{url} is not protected")
                self.assertEqual(r["Content-Type"], "application/json")
                self.assertIn("error", r.json())

    def test_protected_apis_send_no_cors_header(self):
        """Only the public API invites other sites to read it."""
        r = self.client.get("/api/assessments/")
        self.assertNotIn("Access-Control-Allow-Origin", r)

    @mock.patch("preparation.market.requests.get")
    def test_protected_apis_answer_once_signed_in(self, get):
        get.return_value = _jobicy_response(FAKE_JOBS)
        self.assertTrue(self.client.login(username="tquant", password="test-only-pw"))
        for url in self.PROTECTED_APIS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_chart_png_needs_a_login(self):
        r = self.client.get(reverse("preparation:vega_lite_png", args=[2]))
        self.assertEqual(r.status_code, 302)
