from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .analytics import percentile, sample_data, summarize


class DashboardTests(TestCase):
    def test_access_boundary(self):
        url = reverse("dashboard:index")
        self.assertEqual(url, "/admin/dashboard/")
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user("staff", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 403)
        user.is_superuser = True
        user.save()
        response = self.client.get(url)
        self.assertContains(response, "Simulated data")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_filters_and_invalid_parameters(self):
        user = get_user_model().objects.create_superuser("admin", password="test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:index"), {"days": "7", "provider": "Groq"})
        self.assertEqual(len(response.context["data"]["daily"]), 7)
        self.assertEqual(response.context["provider"], "Groq")
        response = self.client.get(reverse("dashboard:index"), {"days": "bad", "provider": "bad"})
        self.assertEqual(response.context["days"], 30)
        self.assertEqual(response.context["provider"], "all")

    def test_aggregations(self):
        self.assertEqual(percentile([10, 20, 30, 40], .5), 25)
        today = date(2026, 11, 15)
        rows = sample_data(today)
        self.assertEqual(rows, sample_data(today))
        data = summarize(rows, today, 30)
        self.assertEqual(sum(f["count"] for f in data["features"]), len(rows))
        self.assertAlmostEqual(sum(f["token_share"] for f in data["features"]), 100, delta=.3)
        self.assertAlmostEqual(data["projected_cost"], 10*sum(r["cost"] for r in rows))
        empty = summarize([], today, 7)
        self.assertEqual(empty["count"], 0)
        self.assertIsNone(empty["correlation"])
