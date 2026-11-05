import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from beacon_core import security
from preparation.models import CandidateProfile
from studio.models import Card, InterviewSession, SkillMemory

from . import actions
from .models import ErrorEvent, StaffAction, SupportTicket


def set_up_goal(client, role="Pastry chef"):
    bp = client.post(reverse("studio:start_blueprint"), json.dumps({"role": role}),
                     content_type="application/json").json()
    client.post(reverse("studio:start"), json.dumps(
        {"role": bp["title"], "blueprint": bp["slug"],
         "ratings": {s["name"]: 30 for s in bp["skills"]}}), content_type="application/json")


@override_settings(LLM_ENABLED=False)
class ConsoleAccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("coach", password="pw-12345", is_staff=True)
        self.member = User.objects.create_user("mia", password="pw-12345")

    def test_everyone_but_staff_gets_a_404(self):
        urls = [reverse("support:overview"), reverse("support:users"),
                reverse("support:user", args=[self.member.pk]), reverse("support:reports"),
                reverse("support:errors"), reverse("support:audit")]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.client.login(username="mia", password="pw-12345")
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        r = self.client.post(reverse("support:user_action", args=[self.member.pk]),
                             {"action": "make_due"})
        self.assertEqual(r.status_code, 404)

    def test_staff_can_see_every_page(self):
        self.client.login(username="mia", password="pw-12345")
        set_up_goal(self.client)
        self.client.logout()
        self.client.login(username="coach", password="pw-12345")
        for url in [reverse("support:overview"), reverse("support:users") + "?q=mia",
                    reverse("support:user", args=[self.member.pk]), reverse("support:reports"),
                    reverse("support:errors"), reverse("support:audit")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.get(reverse("support:user", args=[self.member.pk]))
        self.assertContains(r, "Pastry chef")
        self.assertContains(r, "Diagnosis")

    def test_search_finds_by_role(self):
        self.client.login(username="mia", password="pw-12345")
        set_up_goal(self.client, "Wildlife biologist")
        self.client.logout()
        self.client.login(username="coach", password="pw-12345")
        self.assertContains(self.client.get(reverse("support:users"), {"q": "wildlife"}), "mia")
        self.assertNotContains(self.client.get(reverse("support:users"), {"q": "zzz"}), "mia")

    def test_staff_without_a_goal_land_on_the_console(self):
        self.client.login(username="coach", password="pw-12345")
        self.assertRedirects(self.client.get("/"), reverse("support:overview"))


@override_settings(LLM_ENABLED=False)
class DiagnosisAndFixTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user("coach", password="pw-12345", is_staff=True)
        self.member = User.objects.create_user("mia", password="pw-12345")
        self.client.login(username="mia", password="pw-12345")
        set_up_goal(self.client)
        self.client.logout()
        self.client.login(username="coach", password="pw-12345")
        self.profile = CandidateProfile.objects.get(user=self.member)

    def tearDown(self):
        cache.clear()

    def titles(self):
        return [f["title"] for f in actions.diagnose(self.member)]

    def act(self, name, **extra):
        return self.client.post(reverse("support:user_action", args=[self.member.pk]),
                                {"action": name, **extra}, follow=True)

    def test_offline_blueprint_is_flagged(self):
        self.assertIn("Using the offline skill set", self.titles())

    def test_out_of_sync_skills_are_found_and_fixed(self):
        self.profile.memories.first().delete()
        self.assertIn("Skills out of sync", self.titles())
        self.act("resync_skills")
        self.assertNotIn("Skills out of sync", self.titles())

    def test_stuck_interview_is_found_and_closed(self):
        s = InterviewSession.objects.create(candidate=self.profile, role="x")
        InterviewSession.objects.filter(pk=s.pk).update(started_at=timezone.now() - timedelta(hours=5))
        self.assertTrue(any("never finished" in t for t in self.titles()))
        self.act("close_stuck_interviews")
        s.refresh_from_db()
        self.assertIsNotNone(s.finished_at)

    def test_locked_login_is_found_and_unlocked(self):
        for _ in range(security.LOGIN_FAILS_PER_ACCOUNT):
            security.hit("login-user", "mia", security.LOGIN_WINDOW)
        self.assertIn("Sign-in is temporarily locked", self.titles())
        self.act("unlock_login")
        self.assertNotIn("Sign-in is temporarily locked", self.titles())

    def test_suspend_signs_them_out_and_reactivate_restores(self):
        other = self.client_class()
        other.login(username="mia", password="pw-12345")
        self.assertEqual(other.get(reverse("studio:today")).status_code, 200)
        self.act("suspend")
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertEqual(other.get(reverse("studio:today")).status_code, 302)
        self.assertIn("Account is suspended", self.titles())
        self.act("reactivate")
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_cannot_suspend_yourself(self):
        r = self.client.post(reverse("support:user_action", args=[self.staff.pk]),
                             {"action": "suspend"}, follow=True)
        self.assertContains(r, "suspend your own account")
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_only_superusers_manage_staff(self):
        r = self.act("grant_staff")
        self.assertContains(r, "Only a superuser")
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_staff)

    def test_adjust_skill_updates_memory_and_assessment(self):
        m = self.profile.memories.select_related("skill").first()
        self.act("adjust_skill", memory_id=m.pk, strength="72", required="80")
        m.refresh_from_db()
        self.assertEqual((m.strength, m.required), (72, 80))
        a = self.profile.assessments.get(skill=m.skill)
        self.assertEqual((a.proficiency_score, a.required_level), (72, 80))

    def test_adjust_rejects_bad_values_and_other_peoples_skills(self):
        m = self.profile.memories.first()
        self.assertContains(self.act("adjust_skill", memory_id=m.pk, strength="500", required="80"),
                            "0-100")
        stranger = CandidateProfile.objects.create(user=User.objects.create_user("x"))
        theirs = SkillMemory.objects.create(candidate=stranger, skill=m.skill)
        self.assertContains(self.act("adjust_skill", memory_id=theirs.pk, strength="5", required="5"),
                            "on this account")

    def test_every_change_is_audited(self):
        self.act("make_due")
        self.act("rebuild_plan")
        logged = list(StaffAction.objects.filter(target=self.member).values_list("action", flat=True))
        self.assertEqual(sorted(logged), ["make_due", "rebuild_plan"])
        self.assertTrue(all(a.actor == self.staff for a in StaffAction.objects.all()))
        self.assertTrue(all(m.is_due() for m in self.profile.memories.all()))

    def test_unknown_action_is_refused(self):
        self.assertContains(self.act("drop_tables"), "Unknown action")
        self.assertFalse(StaffAction.objects.exists())

    def test_actions_are_post_only(self):
        r = self.client.get(reverse("support:user_action", args=[self.member.pk]) + "?action=suspend")
        self.assertEqual(r.status_code, 405)


@override_settings(LLM_ENABLED=False)
class ReportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = User.objects.create_user("mia", password="pw-12345")
        self.staff = User.objects.create_user("coach", password="pw-12345", is_staff=True)

    def tearDown(self):
        cache.clear()

    def test_report_round_trip(self):
        self.client.login(username="mia", password="pw-12345")
        self.client.post(reverse("report_problem"), {"category": "AI", "message": "Questions repeat."})
        ticket = SupportTicket.objects.get()
        self.assertEqual((ticket.user, ticket.category), (self.member, "AI"))
        self.client.logout()

        self.client.login(username="coach", password="pw-12345")
        self.assertContains(self.client.get(reverse("support:overview")), "Questions repeat.")
        self.client.post(reverse("support:resolve_report", args=[ticket.pk]),
                         {"note": "Fixed, thanks for telling us!"})
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "DONE")
        self.client.logout()

        self.client.login(username="mia", password="pw-12345")
        self.assertContains(self.client.get(reverse("studio:you")), "Fixed, thanks for telling us!")

    def test_reports_need_sign_in_and_a_message(self):
        self.client.post(reverse("report_problem"), {"message": "hi"})
        self.assertFalse(SupportTicket.objects.exists())
        self.client.login(username="mia", password="pw-12345")
        self.client.post(reverse("report_problem"), {"message": "   "})
        self.assertFalse(SupportTicket.objects.exists())

    def test_reports_are_limited_per_day(self):
        self.client.login(username="mia", password="pw-12345")
        from . import views
        for _ in range(views.REPORTS_PER_DAY + 3):
            self.client.post(reverse("report_problem"), {"message": "again"})
        self.assertEqual(SupportTicket.objects.count(), views.REPORTS_PER_DAY)

    def test_only_staff_resolve(self):
        t = SupportTicket.objects.create(user=self.member, message="x")
        self.client.login(username="mia", password="pw-12345")
        self.assertEqual(self.client.post(reverse("support:resolve_report", args=[t.pk])).status_code, 404)


class ErrorRecordingTests(TestCase):
    def test_unhandled_errors_are_recorded_without_request_contents(self):
        from django.test import RequestFactory
        from .middleware import RecordErrorsMiddleware
        request = RequestFactory().post("/today/?token=secret", {"answer": "private"})
        request.user = User.objects.create_user("e")
        RecordErrorsMiddleware(lambda r: None).process_exception(request, ValueError("boom"))
        event = ErrorEvent.objects.get()
        self.assertEqual((event.kind, event.path, event.user), ("ValueError", "/today/", request.user))
        self.assertNotIn("secret", event.path + event.message)
        self.assertNotIn("private", event.message)
