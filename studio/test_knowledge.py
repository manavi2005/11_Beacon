"""Ask Beacon: chunking, retrieval, guardrails and the page.

Runs with embeddings switched off (keyword retrieval), so it needs no torch
and no model download; the embedding path is measured by
`manage.py evaluate_ask`."""

import re
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from studio import ai, knowledge


@override_settings(ASK_EMBEDDINGS_ENABLED=False, LLM_ENABLED=False)
class KnowledgeTests(TestCase):
    def setUp(self):
        knowledge.reset()

    def tearDown(self):
        knowledge.reset()

    def test_chunks_keep_whole_sentences_and_stay_inside_one_section(self):
        guide = knowledge.load_guide()
        section_of = {p["id"]: p["section_id"] for p in guide}
        chunks = knowledge.chunk(guide)
        self.assertGreaterEqual(len(chunks), 15)
        for c in chunks:
            self.assertEqual(len({section_of[p] for p in c["paragraphs"]}), 1)
            self.assertTrue(c["text"].rstrip().endswith((".", "?", "!", '"', ")")), c["id"])
            self.assertLessEqual(len(c["text"].split()), knowledge.CHUNK_WORDS + 60)

    def test_keyword_retrieval_finds_the_readiness_explanation(self):
        found = knowledge.retrieve("How is the readiness percentage calculated?")
        self.assertEqual(found["mode"], "keyword")
        self.assertTrue(found["relevant"])
        self.assertTrue(any("B12" in c["paragraphs"] for c in found["chunks"]))

    def test_guardrails_on_the_question(self):
        for bad in ["", "   ", "?!", "x" * 400]:
            with self.assertRaises(knowledge.AskError):
                knowledge.clean_question(bad)

    def test_off_topic_question_is_declined_without_calling_the_model(self):
        with mock.patch.object(ai, "ask_text") as model:
            result = knowledge.ask("What's the weather like in Paris tomorrow?")
        model.assert_not_called()
        self.assertEqual(result["status"], "not_covered")

    def test_model_trouble_shows_the_passages_instead(self):
        with mock.patch.object(ai, "ask_text", side_effect=ai.Unavailable("timeout")):
            result = knowledge.ask("How is the readiness percentage calculated?")
        self.assertEqual(result["status"], "passages_only")
        self.assertEqual(len(result["retrieval"]["chunks"]), knowledge.TOP_K)

    def test_citations_to_passages_that_were_not_retrieved_are_removed(self):
        found = knowledge.retrieve("How is the readiness percentage calculated?")
        real = found["chunks"][0]["id"]
        reply = f"Readiness averages capped ratios [{real}] and is perfect [C99]."
        with mock.patch.object(ai, "ask_text", return_value=reply), \
                mock.patch.object(ai, "label", return_value="test model"):
            result = knowledge.ask("How is the readiness percentage calculated?")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["cited"], [real])
        self.assertEqual(result["removed_citations"], ["C99"])
        self.assertNotIn("C99", result["answer"])

    def test_empty_model_reply_falls_back_to_passages(self):
        with mock.patch.object(ai, "ask_text", return_value="  "):
            result = knowledge.ask("How is the readiness percentage calculated?")
        self.assertEqual(result["status"], "passages_only")


@override_settings(ASK_EMBEDDINGS_ENABLED=False, LLM_ENABLED=False)
class AskPageTests(TestCase):
    def setUp(self):
        knowledge.reset()
        User.objects.create_user("q", password="pw-12345")

    def test_needs_sign_in(self):
        self.assertEqual(self.client.get(reverse("studio:ask")).status_code, 302)

    def test_page_and_answer_flow(self):
        self.client.login(username="q", password="pw-12345")
        r = self.client.get(reverse("studio:ask"))
        self.assertContains(r, "How does Beacon")
        r = self.client.post(reverse("studio:ask"), {"question": "How is my readiness percentage calculated?"})
        self.assertContains(r, "Based on these parts of the guide")
        self.assertContains(r, "Passages only")  # LLM is off in tests
        r = self.client.post(reverse("studio:ask"), {"question": ""})
        self.assertContains(r, "Type a question")

    def test_answer_formatting_is_rendered_safely(self):
        self.client.login(username="q", password="pw-12345")
        reply = "A task is done when a **TaskAttempt** passes <script>alert(1)</script> [C10]."
        with mock.patch.object(ai, "ask_text", return_value=reply), \
                mock.patch.object(ai, "label", return_value="test model"), \
                mock.patch.object(knowledge, "_check_citations", side_effect=lambda a, c: (a, ["C10"], [])):
            r = self.client.post(reverse("studio:ask"), {"question": "How is my readiness percentage calculated?"})
        self.assertContains(r, "<strong>TaskAttempt</strong>")
        self.assertNotContains(r, "**TaskAttempt**")
        self.assertNotContains(r, "<script>alert(1)</script>")
