"""Smoke tests for the preparation app.

These are not an assignment requirement. They exist because the four graded
views in Section 2 are the deliverable, and a test that loads each one is the
cheapest way to notice if a later change breaks one of them.

Run with:  python manage.py test preparation
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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

    # --- GET search -----------------------------------------------------
    def test_get_search_filters_by_name(self):
        r = self.client.get(reverse("preparation:skill_search"), {"q": "SQL"})
        self.assertContains(r, "SQL and relational modeling")
        self.assertNotContains(r, "Resume and elevator pitch")

    def test_get_search_is_shareable_as_a_url(self):
        """Same querystring, same results: that is the point of using GET."""
        url = reverse("preparation:skill_search") + "?q=SQL"
        first = self.client.get(url).content.decode()
        second = self.client.get(url).content.decode()
        self.assertEqual(first, second)

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
