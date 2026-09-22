"""Smoke tests for the preparation app.

These are not an assignment requirement. They exist because the four graded
views in Section 2 are the deliverable, and a test that loads each one is the
cheapest way to notice if a later change breaks one of them.

Run with:  python manage.py test preparation
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CandidateProfile, PlanTask, PreparationPlan, Skill
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
