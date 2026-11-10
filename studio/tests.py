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

    def test_about_falls_back_to_the_persons_own_words_without_ai(self):
        from . import about
        result = about.read_background("I studied history and ran a volunteer program for 3 years.")
        self.assertIn("volunteer program", result["summary"])
        self.assertEqual(result["roles"], [])


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


@override_settings(LLM_ENABLED=False)
class TailoredSetupTests(TestCase):
    def setUp(self):
        User.objects.create_user("t", password="pw-12345")
        self.client.login(username="t", password="pw-12345")

    def test_setup_page_names_no_industry(self):
        body = self.client.get(reverse("studio:start")).content.decode().lower()
        for word in ("software", "engineer", "chemist", "nurse", "teacher", "designer", "pfizer"):
            self.assertNotIn(word, body)

    def test_about_accepts_text_and_a_resume_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.post(reverse("studio:start_about"), {"text": "I coach youth soccer and study kinesiology."})
        self.assertIn("kinesiology", r.json()["summary"])
        upload = SimpleUploadedFile("cv.txt", b"Barista for two years, now studying accounting.", "text/plain")
        r = self.client.post(reverse("studio:start_about"), {"resume": upload})
        self.assertIn("accounting", r.json()["summary"])
        self.assertEqual(self.client.post(reverse("studio:start_about"), {}).status_code, 400)

    def test_background_is_kept_for_tailoring(self):
        bp = post_json(self.client, reverse("studio:start_blueprint"), {"role": "Physiotherapist"}).json()
        post_json(self.client, reverse("studio:start"), {
            "role": bp["title"], "blueprint": bp["slug"], "ratings": {},
            "background": "Former athlete, kinesiology degree.", "experience_level": "SWTCH"})
        profile = CandidateProfile.objects.get(user__username="t")
        self.assertEqual(profile.experience_level, "SWTCH")
        from .about import tailor_line
        self.assertIn("kinesiology", tailor_line(profile))
        self.assertIn("Changing careers", tailor_line(profile))

    def test_weekly_plan_has_tasks_for_any_skill(self):
        bp = post_json(self.client, reverse("studio:start_blueprint"), {"role": "Sommelier"}).json()
        post_json(self.client, reverse("studio:start"), {
            "role": bp["title"], "blueprint": bp["slug"], "ratings": {s["name"]: 10 for s in bp["skills"]}})
        plan = CandidateProfile.objects.get(user__username="t").plans.get(status="ACTIVE")
        self.assertTrue(plan.tasks.exists())
        self.assertTrue(any("sommelier" in t.title.lower() for t in plan.tasks.all()))


class ErrorPageTests(TestCase):
    def test_404_uses_the_product_design(self):
        r = self.client.get("/definitely-not-a-page/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "out of the light", status_code=404)


class CircuitBreakerTests(TestCase):
    def test_unreachable_provider_switches_ai_off_for_a_while(self):
        from unittest import mock
        from django.core.cache import cache
        from preparation import coach
        from . import ai
        cache.delete(ai.DOWN_KEY)
        with override_settings(LLM_ENABLED=True, LLM_API_KEY="k", LLM_BASE_URL="https://x.test", LLM_MODEL="m"), \
                mock.patch.object(coach, "_chat", side_effect=coach.CoachError("The AI coach could not be reached.")):
            self.assertTrue(ai.enabled())
            with self.assertRaises(ai.Unavailable):
                ai.ask_json("s", "u")
            self.assertFalse(ai.enabled())
        cache.delete(ai.DOWN_KEY)

    def test_bad_json_does_not_trip_the_breaker(self):
        from unittest import mock
        from django.core.cache import cache
        from preparation import coach
        from . import ai
        cache.delete(ai.DOWN_KEY)
        with override_settings(LLM_ENABLED=True, LLM_API_KEY="k", LLM_BASE_URL="https://x.test", LLM_MODEL="m"), \
                mock.patch.object(coach, "_chat", return_value="not json"):
            with self.assertRaises(ai.Unavailable):
                ai.ask_json("s", "u")
            self.assertTrue(ai.enabled())


@override_settings(LLM_ENABLED=False)
class AiBudgetTests(TestCase):
    def test_ai_actions_are_capped_per_hour(self):
        from django.core.cache import cache
        from . import views
        cache.clear()
        User.objects.create_user("b", password="pw-12345")
        self.client.login(username="b", password="pw-12345")
        with self.settings():
            original = views.AI_ACTIONS_PER_HOUR
            views.AI_ACTIONS_PER_HOUR = 2
            try:
                codes = [post_json(self.client, reverse("studio:start_blueprint"), {"role": "Baker"}).status_code
                         for _ in range(3)]
            finally:
                views.AI_ACTIONS_PER_HOUR = original
        self.assertEqual(codes, [200, 200, 429])
        cache.clear()


@override_settings(LLM_ENABLED=False)
class HealthTests(TestCase):
    def test_health_reports_database_and_ai_without_login(self):
        data = self.client.get(reverse("studio:healthz")).json()
        self.assertEqual(data, {"ok": True, "database": True, "ai": "off"})


@override_settings(LLM_ENABLED=False)
class StageAndMarketTests(TestCase):
    def test_blueprints_are_per_career_stage(self):
        intern = blueprint.get_blueprint("Accountant", "STU")
        senior = blueprint.get_blueprint("Accountant", "MID")
        self.assertNotEqual(intern.pk, senior.pk)
        self.assertEqual(intern.stage, "STU")

    def test_levels_are_named_against_the_persons_own_bar(self):
        from .models import level_name
        self.assertEqual(level_name(60, 60), "Interview-ready")   # an intern at their bar
        self.assertEqual(level_name(60, 90), "Building")
        self.assertEqual(level_name(10, 90), "Starting out")

    def test_market_postings_feed_the_prompt_and_are_recorded(self):
        from unittest import mock
        from preparation import market
        from . import ai
        postings = [{"title": f"{t} Accountant", "_text": "cpa track, netsuite, month-end close"}
                    for t in ("Staff", "Junior", "Tax")]
        postings.append({"title": "React Developer", "_text": "react typescript docker"})
        captured = {}

        def fake_ask(system, user, **kw):
            captured["prompt"] = user
            return {"title": "Accountant", "summary": "s", "trending": ["NetSuite", "Month-end close"],
                    "interview_style": {"summary": "x", "rounds": [{"name": "Technical", "what": "Journal entries"}]},
                    "skills": [{"name": f"Skill {i}", "category": "domain", "required": 70} for i in range(5)]}

        with mock.patch.object(ai, "enabled", return_value=True), \
                mock.patch.object(ai, "ask_json", side_effect=fake_ask), \
                mock.patch.object(market, "fetch_postings", return_value=("jobicy", postings)):
            bp = blueprint.get_blueprint("Accountant", "NEW")
        self.assertIn("netsuite", captured["prompt"])
        self.assertNotIn("typescript", captured["prompt"])     # unrelated posting dropped
        self.assertIn("New graduate", captured["prompt"])
        self.assertEqual(bp.market["trending"], ["NetSuite", "Month-end close"])
        self.assertEqual(bp.interview_style["rounds"][0]["name"], "Technical")


@override_settings(LLM_ENABLED=False)
class DeletingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("d", password="pw-12345")
        self.client.login(username="d", password="pw-12345")
        bp = post_json(self.client, reverse("studio:start_blueprint"), {"role": "Librarian"}).json()
        post_json(self.client, reverse("studio:start"),
                  {"role": bp["title"], "blueprint": bp["slug"], "ratings": {s["name"]: 20 for s in bp["skills"]}})
        self.profile = CandidateProfile.objects.get(user=self.user)
        self.other = User.objects.create_user("o", password="pw-12345")

    def test_plans_can_be_deleted_and_rebuilt(self):
        plan = self.profile.plans.get()
        r = self.client.get(reverse("studio:you"))
        self.assertContains(r, plan.title)
        self.client.post(reverse("studio:delete_plan", args=[plan.pk]))
        self.assertFalse(self.profile.plans.exists())
        self.assertEqual(self.client.get(reverse("preparation:my_plan")).status_code, 200)
        self.client.post(reverse("studio:new_plan"))
        self.assertTrue(self.profile.plans.exists())

    def test_interviews_and_practice_can_be_deleted_but_progress_stays(self):
        session = InterviewSession.objects.create(candidate=self.profile, role="Librarian")
        memory = self.profile.memories.first()
        Card.objects.create(candidate=self.profile, skill=memory.skill, kind=Card.Kind.SHORT, prompt="Q")
        r = self.client.post(reverse("studio:delete_interview", args=[session.pk]),
                             {"next": "https://evil.example/"})
        self.assertRedirects(r, reverse("studio:you"))          # off-site next ignored
        self.assertFalse(InterviewSession.objects.exists())
        self.client.post(reverse("studio:clear_practice"))
        self.assertFalse(Card.objects.exists())
        self.assertTrue(self.profile.memories.exists())

    def test_nobody_can_delete_someone_elses_things(self):
        plan = self.profile.plans.get()
        session = InterviewSession.objects.create(candidate=self.profile, role="Librarian")
        self.client.login(username="o", password="pw-12345")
        self.assertEqual(self.client.post(reverse("studio:delete_plan", args=[plan.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("studio:delete_interview", args=[session.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("studio:delete_plan", args=[plan.pk])).status_code, 405)
        self.assertTrue(self.profile.plans.exists())


@override_settings(LLM_ENABLED=False)
class RankingTests(TestCase):
    """The scoring function behind today's session."""

    def setUp(self):
        user = User.objects.create_user("r", password="x")
        self.profile = CandidateProfile.objects.create(user=user, target_role="Nurse",
                                                       experience_level="STU")
        self.now = timezone.now()

    def memory(self, name, **fields):
        skill = Skill.objects.create(name=name)
        defaults = {"strength": 50, "required": 70, "due_at": self.now + timedelta(days=3)}
        defaults.update(fields)
        return SkillMemory.objects.create(candidate=self.profile, skill=skill, **defaults)

    def test_bayesian_average_keeps_sparse_skills_near_the_prior(self):
        # Three perfect answers barely move it; three hundred do.
        self.assertLess(engine.shrunk_mean(3, 100) - engine.COHORT_PRIOR, 10)
        self.assertGreater(engine.shrunk_mean(300, 100), 95)
        self.assertEqual(engine.shrunk_mean(0, 0), engine.COHORT_PRIOR)

    def test_wider_gap_ranks_higher_all_else_equal(self):
        small = self.memory("Charting", strength=65)
        wide = self.memory("Medication safety", strength=20)
        ranked = engine.rank([small, wide], now=self.now)
        self.assertEqual(ranked[0], wide)
        self.assertEqual(wide.why_today, "Widest gap to your bar")

    def test_fading_skill_outranks_a_fresh_one(self):
        fading = self.memory("Triage", strength=60, reps=4, stability=2,
                             last_practiced=self.now - timedelta(days=20))
        fresh = self.memory("Handover", strength=60, reps=4, stability=30,
                            last_practiced=self.now - timedelta(days=1))
        ranked = engine.rank([fresh, fading], now=self.now)
        self.assertEqual(ranked[0], fading)
        self.assertIn("Fading", fading.why_today)

    def test_market_demand_breaks_a_tie(self):
        a = self.memory("Wound care")
        b = self.memory("Epic charting")
        ranked = engine.rank([a, b], now=self.now, trending=["Epic EHR"])
        self.assertEqual(ranked[0], b)

    def test_practised_hours_ago_is_pushed_down(self):
        just_now = self.memory("IV insertion", strength=30, reps=1,
                               last_practiced=self.now - timedelta(hours=1))
        other = self.memory("Patient education", strength=40, reps=1,
                            last_practiced=self.now - timedelta(days=3))
        self.assertEqual(engine.rank([just_now, other], now=self.now)[0], other)

    def test_cohort_signal_needs_volume_before_it_counts(self):
        hard = self.memory("Sepsis recognition")
        easy = self.memory("Vital signs")
        peer = CandidateProfile.objects.create(user=User.objects.create_user("p"),
                                               experience_level="STU")
        for _ in range(2):  # two bad answers: too few to matter
            Card.objects.create(candidate=peer, skill=hard.skill, kind="SHORT", prompt="q",
                                score=10, answered_at=self.now)
        _, parts = engine.score(hard, now=self.now,
                                cohort=engine.cohort_stats([hard.skill_id], "STU"))
        self.assertLess(parts["cohort"], 0.02)
        for _ in range(60):
            Card.objects.create(candidate=peer, skill=hard.skill, kind="SHORT", prompt="q",
                                score=10, answered_at=self.now)
        cohort = engine.cohort_stats([hard.skill_id, easy.skill_id], "STU")
        ranked = engine.rank([easy, hard], now=self.now, stage="STU")
        self.assertEqual(ranked[0], hard)
        self.assertGreater(cohort[hard.skill_id][0], 50)

    def test_cohort_is_per_career_stage(self):
        m = self.memory("Delegation")
        senior = CandidateProfile.objects.create(user=User.objects.create_user("s"),
                                                 experience_level="MID")
        Card.objects.create(candidate=senior, skill=m.skill, kind="SHORT", prompt="q",
                            score=5, answered_at=self.now)
        self.assertEqual(engine.cohort_stats([m.skill_id], "STU"), {})

    def test_due_skills_still_come_first(self):
        due = self.memory("Infection control", strength=69, due_at=self.now - timedelta(hours=1))
        not_due = self.memory("Care planning", strength=10)
        plan = engine.queue([not_due, due], now=self.now)
        self.assertEqual(plan[0], due)


@override_settings(LLM_ENABLED=True, LLM_API_KEY="", LLM_BASE_URL="https://x.test", LLM_MODEL="m",
                   LLM_KEYLESS_BASE_URL="https://keyless.test")
class SpeedTests(TestCase):
    """A slow or rate-limited free provider must never hold a practice session hostage."""

    def setUp(self):
        from django.core.cache import cache
        from . import ai
        cache.delete(ai.SLOW_KEY)
        cache.delete(ai.DOWN_KEY)

    tearDown = setUp

    def test_budget_caps_retries_on_a_busy_free_tier(self):
        import time
        from unittest import mock
        from preparation import coach
        busy = mock.Mock(status_code=429)
        with mock.patch.object(coach.requests, "post", return_value=busy) as post, \
                mock.patch.object(coach.time, "sleep") as sleep:
            with self.assertRaises(coach.CoachBusy):
                coach._chat([{"role": "user", "content": "q"}], patient=True, budget=12)
        # Without a budget it would wait 6 s and 10 s and try three times;
        # with 12 s it may wait once at most and never starts a doomed retry.
        self.assertLessEqual(post.call_count, 2)
        self.assertLessEqual(sum(c.args[0] for c in sleep.call_args_list), 6)

    def test_each_attempt_timeout_fits_inside_the_budget(self):
        from unittest import mock
        from preparation import coach
        with mock.patch.object(coach.requests, "post", side_effect=coach.requests.Timeout) as post:
            with self.assertRaises(coach.CoachError):
                coach._chat([{"role": "user", "content": "q"}], timeout=60, budget=20)
        self.assertLessEqual(post.call_args.kwargs["timeout"], 20)

    def test_a_timeout_puts_interactive_features_in_slow_mode(self):
        from unittest import mock
        from preparation import coach
        from . import ai
        with mock.patch.object(coach, "_chat", side_effect=coach.CoachError("The AI coach took too long to answer.")):
            with self.assertRaises(ai.Unavailable):
                ai.ask_json("s", "u", interactive=True)
        self.assertTrue(ai.slow())
        self.assertTrue(ai.enabled())  # slow, not down: setup and reports still use the model
        with mock.patch.object(coach, "_chat") as chat:
            with self.assertRaises(ai.Unavailable):
                ai.ask_json("s", "u", interactive=True)
            chat.assert_not_called()  # instant fallback, no second wait
            chat.return_value = '{"ok": 1}'
            self.assertEqual(ai.ask_json("s", "u"), {"ok": 1})  # non-interactive still tries

    def test_practice_card_is_instant_in_slow_mode(self):
        import time
        from unittest import mock
        from django.core.cache import cache
        from preparation import coach
        from . import ai
        User.objects.create_user("fast", password="pw-12345")
        self.client.login(username="fast", password="pw-12345")
        with override_settings(LLM_ENABLED=False):
            bp = post_json(self.client, reverse("studio:start_blueprint"), {"role": "Pastry chef"}).json()
            post_json(self.client, reverse("studio:start"), {"role": bp["title"], "blueprint": bp["slug"],
                                                              "ratings": {s["name"]: 30 for s in bp["skills"]}})
        self.client.get(reverse("studio:session"))
        cache.set(ai.SLOW_KEY, "took too long", ai.SLOW_SECONDS)
        with mock.patch.object(coach, "_chat") as chat:
            t = time.monotonic()
            r = post_json(self.client, reverse("studio:session_next"))
            self.assertLess(time.monotonic() - t, 2)
            chat.assert_not_called()
        self.assertEqual(r.status_code, 200)
        self.assertIn("card", r.json())
