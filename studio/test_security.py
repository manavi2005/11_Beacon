"""Abuse protection: login and signup limits, AI caps, headers, settings."""

import os
import re
import runpy
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from beacon_core import security


@override_settings(RATE_LIMITS_ENABLED=True)
class LoginLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user("ana", password="right-pass-123")
        self.url = reverse("preparation:login")

    def tearDown(self):
        cache.clear()

    def attempt(self, password, username="ana"):
        return self.client.post(self.url, {"username": username, "password": password})

    def test_account_locks_after_repeated_failures_even_for_the_right_password(self):
        for _ in range(security.LOGIN_FAILS_PER_ACCOUNT):
            self.assertEqual(self.attempt("wrong").status_code, 200)
        r = self.attempt("right-pass-123")
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, "wait 15 minutes", status_code=429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lock_is_per_account_and_case_insensitive(self):
        for _ in range(security.LOGIN_FAILS_PER_ACCOUNT):
            self.attempt("wrong", username="ANA")
        self.assertEqual(self.attempt("right-pass-123").status_code, 429)
        User.objects.create_user("ben", password="ben-pass-123")
        self.assertEqual(self.attempt("ben-pass-123", username="ben").status_code, 302)

    def test_successful_logins_never_count(self):
        for _ in range(security.LOGIN_FAILS_PER_ACCOUNT + 2):
            self.assertEqual(self.attempt("right-pass-123").status_code, 302)
            self.client.logout()

    def test_staff_can_unlock(self):
        for _ in range(security.LOGIN_FAILS_PER_ACCOUNT):
            self.attempt("wrong")
        security.unlock_login("ana")
        self.assertEqual(self.attempt("right-pass-123").status_code, 302)

    def test_admin_login_is_limited_too(self):
        url = reverse("admin:login")
        for _ in range(security.LOGIN_FAILS_PER_ACCOUNT):
            self.client.post(url, {"username": "ana", "password": "wrong"})
        self.assertEqual(self.client.post(url, {"username": "ana", "password": "x"}).status_code, 429)

    def test_signups_are_limited_per_address(self):
        url = reverse("preparation:signup")
        codes = []
        for i in range(security.SIGNUPS_PER_IP + 1):
            codes.append(self.client.post(url, {"username": f"bot{i}", "password1": "Zq8!xv-long-pass",
                                                "password2": "Zq8!xv-long-pass"}).status_code)
            self.client.logout()
        self.assertEqual(codes[-1], 429)
        self.assertEqual(User.objects.filter(username__startswith="bot").count(),
                         security.SIGNUPS_PER_IP)


class ClientIpTests(TestCase):
    def test_proxy_headers_are_ignored_unless_trusted(self):
        request = RequestFactory().get("/", HTTP_X_REAL_IP="6.6.6.6", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(security.client_ip(request), "10.0.0.1")
        with self.settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(security.client_ip(request), "6.6.6.6")

    def test_only_the_last_forwarded_hop_is_trusted(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 9.9.9.9")
        with self.settings(TRUST_PROXY_HEADERS=True):
            self.assertEqual(security.client_ip(request), "9.9.9.9")


@override_settings(LLM_ENABLED=False, RATE_LIMITS_ENABLED=True)
class AiCapTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_many_accounts_from_one_address_share_a_cap(self):
        from . import views
        with mock.patch.object(views, "AI_ACTIONS_PER_IP_PER_HOUR", 3):
            codes = []
            for i in range(4):
                User.objects.create_user(f"u{i}", password="pw-12345")
                self.client.login(username=f"u{i}", password="pw-12345")
                codes.append(self.client.post(reverse("studio:start_blueprint"), '{"role": "Baker"}',
                                              content_type="application/json").status_code)
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_site_wide_cap_answers_busy(self):
        from . import views
        User.objects.create_user("s", password="pw-12345")
        self.client.login(username="s", password="pw-12345")
        with mock.patch.object(views, "AI_ACTIONS_SITE_PER_HOUR", 1):
            post = lambda: self.client.post(reverse("studio:start_blueprint"), '{"role": "Baker"}',
                                            content_type="application/json")
            self.assertEqual(post().status_code, 200)
            self.assertEqual(post().status_code, 503)

    def test_public_api_is_limited_per_address(self):
        from preparation import views as v1
        with mock.patch.object(v1, "PUBLIC_API_PER_MINUTE", 2):
            codes = [self.client.get(reverse("preparation:api_skill_summary")).status_code
                     for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])


class HeaderTests(TestCase):
    def test_pages_carry_a_csp_whose_nonce_matches_the_inline_script(self):
        r = self.client.get("/")
        policy = r["Content-Security-Policy"]
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertNotIn("unsafe-eval", policy)
        nonce = re.search(r"'nonce-([^']+)'", policy).group(1)
        self.assertIn(f'nonce="{nonce}"', r.content.decode())
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("camera=()", r["Permissions-Policy"])

    def test_nonce_is_fresh_per_response(self):
        a = self.client.get("/")["Content-Security-Policy"]
        b = self.client.get("/")["Content-Security-Policy"]
        self.assertNotEqual(a, b)

    def test_no_inline_event_handlers_in_templates(self):
        from pathlib import Path
        from django.conf import settings
        offenders = [str(p) for p in Path(settings.BASE_DIR, "templates").rglob("*.html")
                     if re.search(r"\son(click|change|submit|load|input)=", p.read_text())]
        self.assertEqual(offenders, [])


class ProductionSettingsTests(TestCase):
    def load(self, key):
        with mock.patch.dict(os.environ, {"DJANGO_SECRET_KEY": key}):
            return runpy.run_module("beacon_core.settings.production")

    def test_refuses_to_start_with_a_weak_or_default_key(self):
        for key in ("", "short", "django-insecure-dev-only-key-replace-me-in-dotenv",
                    "replace-with-a-long-random-string-xxxxxxxxxxxxxxxxxxxxxx"):
            with self.assertRaises(ImproperlyConfigured):
                self.load(key)

    def test_strong_key_gives_hardened_settings(self):
        conf = self.load("k" * 30 + "Q7v-p2!s9x" * 3)
        self.assertFalse(conf["DEBUG"])
        self.assertTrue(conf["SESSION_COOKIE_SECURE"] and conf["CSRF_COOKIE_HTTPONLY"])
        self.assertGreaterEqual(conf["SECURE_HSTS_SECONDS"], 31536000)
        self.assertEqual(conf["CACHES"]["default"]["BACKEND"],
                         "django.core.cache.backends.db.DatabaseCache")
        self.assertTrue(conf["TRUST_PROXY_HEADERS"])
