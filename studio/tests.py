"""Tests for the v2 loop. AI is off (settings.LLM_ENABLED=False) so every
path exercises the offline fallbacks and runs without network."""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from preparation.models import CandidateProfile, Skill

from . import blueprint, engine
from .models import Card, DayLog, InterviewSession, RoleBlueprint, SkillMemory


def post_json(client, url, data=None):
    return client.post(url, json.dumps(data or {}), content_type="application/json")


@override_settings(LLM_ENABLED=False)
class MemoryModelTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("m", password="x")
        self.profile = CandidateProfile.objects.create(user=user, target_role="Nurse")
        self.skill = Skill.objects.create(name="Patient triage")
        self.memory = SkillMemory.objects.create(candidate=self.profile, skill=self.skill,
                                                 strength=40, required=70)

    def test_good_answer_lengthens_the_gap_and_raises_strength(self):
        now = timezone.now()
        self.memory.record(90, now)
        self.assertGreater(self.memory.strength, 40)
        self.assertGreater(self.memory.stability, 1.5)
        self.assertEqual(self.memory.due_at, now + timedelta(days=self.memory.stability))

    def test_poor_answer_shortens_the_gap_and_counts_a_lapse(self):
        self.memory.record(20)
        self.assertLess(self.memory.strength, 40)
        self.assertEqual(self.memory.lapses, 1)
        self.assertLessEqual(self.memory.stability, 0.5)

    def test_choice_answers_count_for_less_than_written_ones(self):
        other = SkillMemory(candidate=self.profile, skill=self.skill, strength=40, required=70)
        self.memory.record(100, weight=0.6)
        other.record(100)
        self.assertLess(self.memory.strength, other.strength)

    def test_memory_fades_but_never_below_half(self):
        self.memory.last_practiced = timezone.now() - timedelta(days=365)
        self.assertLess(self.memory.retention(), 0.01)
        self.assertGreaterEqual(self.memory.effective(), self.memory.strength * 0.5)

    def test_due_exactly_when_retention_reaches_target(self):
        now = timezone.now()
        self.memory.record(80, now)
        at_due = self.memory.retention(self.memory.due_at)
        self.assertAlmostEqual(at_due, 0.85, places=3)


@override_settings(LLM_ENABLED=False)
class BlueprintTests(TestCase):
    def test_offline_blueprint_is_built_from_the_role_not_a_tech_preset(self):
        bp = blueprint.get_blueprint("Analytical chemist")
        names = [s["name"] for s in bp.skills]
        self.assertIn("Analytical chemist fundamentals", names)
        self.assertNotIn("Data structures & algorithms", names)
        self.assertTrue(any("STAR" in n for n in names))

    def test_blueprints_are_cached_per_role(self):
        a = blueprint.get_blueprint("ICU nurse")
        b = blueprint.get_blueprint("  ICU   nurse ")
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(RoleBlueprint.objects.count(), 1)

    def test_ai_reply_is_validated(self):
        data = blueprint._validate({"skills": [
            {"name": "Lesson planning", "category": "domain", "required": 999},
            {"name": "lesson planning", "category": "x"},
            {"name": "Classroom management", "category": "behavioral", "required": 70},
            {"name": "Differentiated instruction", "category": "technical", "required": "80"},
            {"name": "Parent communication", "category": "communication", "required": 65},
        ]}, "Teacher")
        names = [s["name"] for s in data["skills"]]
        self.assertEqual(names.count("Lesson planning"), 1)
        self.assertEqual(data["skills"][0]["required"], 95)
        self.assertIn("STAR-format storytelling", names)

    def test_suggestions_are_empty_without_ai(self):
        self.assertEqual(blueprint.suggest_roles("chemistry major"), [])


@override_settings(LLM_ENABLED=False)
class JourneyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("chem", password="pw-12345")
        self.client.login(username="chem", password="pw-12345")

    def setup_profile(self, role="Analytical chemist", date=None):
        bp = post_json(self.client, reverse("studio:start_blueprint"), {"role": role}).json()
        ratings = {s["name"]: 30 for s in bp["skills"]}
        r = post_json(self.client, reverse("studio:start"),
                      {"role": bp["title"], "blueprint": bp["slug"], "ratings": ratings,
                       "date": date or ""})
        self.assertEqual(r.status_code, 200)
        return CandidateProfile.objects.get(user=self.user)

    def test_home_routes_by_state(self):
        self.client.logout()
        self.assertContains(self.client.get("/"), "for any career")
        self.client.login(username="chem", password="pw-12345")
        self.assertRedirects(self.client.get("/"), reverse("studio:start"))
        self.setup_profile()
        self.assertRedirects(self.client.get("/"), reverse("studio:today"))

    def test_setup_builds_profile_skills_memories_and_plan(self):
        profile = self.setup_profile(date=str(timezone.localdate() + timedelta(days=21)))
        self.assertEqual(profile.target_role, "Analytical chemist")
        self.assertEqual(profile.assessments.count(), profile.memories.count())
        self.assertGreaterEqual(profile.memories.count(), 6)
        self.assertTrue(profile.plans.exists())
        r = self.client.get(reverse("studio:today"))
        self.assertContains(r, "Analytical chemist")
        self.assertContains(r, "Forecast")

    def test_changing_goal_replaces_the_skill_bar(self):
        self.setup_profile("Analytical chemist")
        profile = self.setup_profile("High-school teacher")
        names = set(profile.memories.values_list("skill__name", flat=True))
        self.assertIn("High-school teacher fundamentals", names)
        self.assertNotIn("Analytical chemist fundamentals", names)

    def test_session_generates_grades_and_logs(self):
        profile = self.setup_profile()
        self.assertEqual(self.client.get(reverse("studio:session")).status_code, 200)
        data = post_json(self.client, reverse("studio:session_next")).json()
        card = data["card"]
        self.assertTrue(card["prompt"])
        answer = ("In my lab I validated an HPLC method. I set the acceptance criteria with QA first, "
                  "ran precision and accuracy studies, documented every decision, and the method "
                  "passed audit, which cut release testing time by a week.")
        r = post_json(self.client, reverse("studio:card_answer", args=[card["id"]]), {"answer": answer})
        result = r.json()
        self.assertGreater(result["score"], 10)
        self.assertGreater(result["xp"], 0)
        self.assertEqual(result["feedback"]["graded_by"], "rules")
        log = DayLog.objects.get(candidate=profile, date=timezone.localdate())
        self.assertEqual(log.cards_done, 1)
        # Answering twice is refused.
        again = post_json(self.client, reverse("studio:card_answer", args=[card["id"]]), {"answer": answer})
        self.assertEqual(again.status_code, 400)

    def test_session_ends_with_a_summary(self):
        self.setup_profile()
        self.client.get(reverse("studio:session"))
        while True:
            data = post_json(self.client, reverse("studio:session_next")).json()
            if data.get("done"):
                break
            post_json(self.client, reverse("studio:card_answer", args=[data["card"]["id"]]),
                      {"answer": "I would explain it clearly with one concrete example from my lab work."})
        self.assertGreaterEqual(data["summary"]["cards"], 1)
        self.assertEqual(data["summary"]["streak"], 1)

    def test_rough_day_means_a_short_review_only_session(self):
        profile = self.setup_profile()
        for m in profile.memories.all()[:3]:
            m.record(80, timezone.now() - timedelta(days=30))
            m.save()
        post_json(self.client, reverse("studio:set_mood"), {"mood": "ROUGH"})
        plan = engine.queue(list(profile.memories.all()), "ROUGH")
        self.assertLessEqual(len(plan), 2)
        self.assertTrue(all(m.reps for m in plan))

    def test_cannot_answer_someone_elses_card(self):
        profile = self.setup_profile()
        card = Card.objects.create(candidate=profile, skill=profile.memories.first().skill,
                                   kind=Card.Kind.SHORT, prompt="Q", payload={"key_points": ["x"]})
        User.objects.create_user("other", password="pw-12345")
        self.client.login(username="other", password="pw-12345")
        r = post_json(self.client, reverse("studio:card_answer", args=[card.pk]), {"answer": "hi"})
        self.assertEqual(r.status_code, 404)

    def test_interview_runs_offline_and_reports(self):
        self.setup_profile()
        start = post_json(self.client, reverse("studio:interview_start"), {"questions": 2}).json()
        self.assertIn("Analytical chemist", start["say"])
        long_answer = ("At my lab internship our GC-MS results drifted, so I traced it to a column "
                       "problem, replaced it, re-ran the standards and documented it. As a result we "
                       "met the deadline and I learned to check system suitability first. ") * 2
        for _ in range(6):
            data = post_json(self.client, reverse("studio:interview_reply", args=[start["id"]]),
                             {"answer": long_answer}).json()
            if data.get("done"):
                break
        self.assertTrue(data.get("done"))
        r = post_json(self.client, reverse("studio:interview_finish", args=[start["id"]]))
        session = InterviewSession.objects.get(pk=start["id"])
        self.assertIsNotNone(session.score)
        self.assertContains(self.client.get(r.json()["url"]), "STAR breakdown")

    def test_progress_and_privacy_pages(self):
        self.setup_profile()
        self.assertContains(self.client.get(reverse("studio:progress")), "Every skill")
        export = self.client.get(reverse("studio:export_data"))
        self.assertEqual(json.loads(export.content)["goal"]["role"], "Analytical chemist")
        self.client.post(reverse("studio:reset_progress"), {"confirm": "nope"})
        self.assertTrue(CandidateProfile.objects.filter(user=self.user).exists())
        self.client.post(reverse("studio:reset_progress"), {"confirm": "DELETE"})
        self.assertFalse(CandidateProfile.objects.filter(user=self.user).exists())


class StreakTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("s", password="x")
        self.profile = CandidateProfile.objects.create(user=user, target_role="Designer")
        self.today = timezone.localdate()

    def active(self, *days_ago):
        for d in days_ago:
            DayLog.objects.create(candidate=self.profile, date=self.today - timedelta(days=d), cards_done=1)

    def test_one_rest_day_does_not_break_a_streak(self):
        self.active(0, 1, 3, 4)
        self.assertEqual(engine.streak(self.profile, self.today)["days"], 4)

    def test_two_missed_days_do(self):
        self.active(0, 1, 4, 5)
        self.assertEqual(engine.streak(self.profile, self.today)["days"], 2)

    def test_not_practising_yet_today_keeps_yesterdays_streak(self):
        self.active(1, 2)
        result = engine.streak(self.profile, self.today)
        self.assertEqual(result["days"], 2)
        self.assertFalse(result["done_today"])


@override_settings(LLM_ENABLED=False)
class CoachAndReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("r", password="pw-12345", email="r@example.com",
                                             first_name="Riya")
        self.client.login(username="r", password="pw-12345")
        self.profile = CandidateProfile.objects.create(user=self.user, target_role="Pharmacist")
        self.skill = Skill.objects.create(name="Drug interactions")
        self.memory = SkillMemory.objects.create(candidate=self.profile, skill=self.skill,
                                                 strength=50, required=75)

    def test_coach_replies_offline_and_keeps_history_in_session_only(self):
        r = post_json(self.client, reverse("studio:coach_send"), {"message": "What should I do?"})
        self.assertIn("Drug interactions", r.json()["reply"])
        self.assertEqual(len(self.client.session["studio_chat"]), 2)
        self.assertContains(self.client.get(reverse("studio:coach")), "What should I do?")
        self.client.post(reverse("studio:coach_clear"))
        self.assertNotIn("studio_chat", self.client.session)

    def test_coach_formatter_escapes_html(self):
        from .templatetags.studio_text import coach_html
        html = coach_html("<script>x</script>\n**Bold** move\n- a\n- b")
        self.assertNotIn("<script>", html)
        self.assertIn("<strong>Bold</strong>", html)
        self.assertIn("<ul><li>a</li><li>b</li></ul>", html)

    def test_reminders_are_opt_in_daily_and_skip_active_days(self):
        from django.core import mail
        from .models import Preferences
        from .reminders import send_due
        self.memory.record(80, timezone.now() - timedelta(days=20))
        self.memory.save()
        self.assertEqual(send_due(), 0)                      # not opted in
        self.client.post(reverse("studio:you"), {"email_reminders": "on"})
        self.assertTrue(Preferences.objects.get(candidate=self.profile).email_reminders)
        self.assertEqual(send_due(), 1)
        self.assertIn("Drug interactions", mail.outbox[0].body)
        self.assertEqual(send_due(), 0)                      # once a day
        DayLog.objects.create(candidate=self.profile, date=timezone.localdate() + timedelta(days=1),
                              cards_done=2)
        self.assertEqual(send_due(timezone.localdate() + timedelta(days=1)), 0)
