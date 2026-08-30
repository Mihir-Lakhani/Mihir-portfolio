import json
import unittest

from rag.config import RagSettings
from rag.conversation import (
    GeminiConversationRouter,
    generic_concept_project_follow_up,
    is_explicit_education_question,
    is_profile_overview_question,
    is_self_contained_portfolio_question,
    local_conversation_reply,
    profile_expansion_follow_up,
    question_depends_on_conversation,
)
from rag.models import ConversationTurn


class Object:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeInteractions:
    def __init__(self, output_text, interaction_id="interaction-new"):
        self.output_text = output_text
        self.interaction_id = interaction_id
        self.kwargs = None
        self.deleted = []

    def create(self, **kwargs):
        self.kwargs = kwargs
        output_text = self.output_text
        if isinstance(output_text, str):
            try:
                payload = json.loads(output_text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                payload.setdefault("retrieval_scope", "relevant")
                output_text = json.dumps(payload)
        return Object(output_text=output_text, id=self.interaction_id)

    def delete(self, interaction_id, **kwargs):
        self.deleted.append((interaction_id, kwargs))


class FakeClient:
    def __init__(self, output_text):
        self.interactions = FakeInteractions(output_text)


def settings() -> RagSettings:
    return RagSettings(
        gemini_api_key="test-key",
        file_search_store_id="fileSearchStores/test-store",
        model="gemini-test",
        max_results=5,
        max_question_characters=500,
        max_answer_tokens=350,
        rate_limit_per_minute=20,
    )


class GeminiConversationRouterTests(unittest.TestCase):
    def test_profile_questions_are_self_contained_without_becoming_project_catalogues(self):
        self.assertTrue(is_profile_overview_question("Tell me about him."))
        self.assertTrue(is_profile_overview_question("Tell me everything about Mihir."))
        self.assertTrue(is_profile_overview_question("Tell me about him as a person."))
        self.assertTrue(is_profile_overview_question("What are his hobbies?"))
        self.assertTrue(is_self_contained_portfolio_question("Tell me more about Mihir."))

    def test_bare_everything_continues_a_profile_thread_without_widening_sources(self):
        query = profile_expansion_follow_up(
            "Tell me everything.",
            (
                ConversationTurn("visitor", "Tell me about him.", False),
                ConversationTurn("assistant", "A profile overview.", True),
            ),
        )

        self.assertEqual(query, "Mihir Lakhani profile.")

    def test_bare_everything_uses_an_expiring_profile_navigation_category(self):
        self.assertEqual(
            profile_expansion_follow_up(
                "Tell me everything.", (), has_profile_context=True
            ),
            "Mihir Lakhani profile.",
        )

    def test_bare_everything_does_not_hijack_a_project_thread(self):
        query = profile_expansion_follow_up(
            "Tell me everything.",
            (
                ConversationTurn("visitor", "Tell me about the Fleet project.", False),
                ConversationTurn("assistant", "A project overview.", True),
            ),
        )

        self.assertIsNone(query)

    def test_education_requires_an_explicit_academic_question(self):
        self.assertTrue(is_explicit_education_question("What is Mihir's CGPA?"))
        self.assertTrue(is_explicit_education_question("Where did Mihir study?"))
        self.assertFalse(is_explicit_education_question("Tell me more."))

    def test_follow_up_returns_a_standalone_file_search_query(self):
        client = FakeClient(
            json.dumps(
                {
                    "mode": "follow_up",
                    "standalone_query": "Which Docker Compose services does the Fleet project declare?",
                    "reply": "",
                    "reason": "context_dependent_portfolio_question",
                    "topic_source_titles": ["Fleet Smart Vehicle Digital Twin Prototype"],
                }
            )
        )
        route = GeminiConversationRouter(
            client,
            settings(),
            trusted_source_titles=("Fleet Smart Vehicle Digital Twin Prototype",),
        ).route(
            "Which services?",
            (
                ConversationTurn("visitor", "Tell me about the Fleet project.", False),
                ConversationTurn("assistant", "It uses Docker Compose.", True),
            ),
        )

        self.assertEqual(route.mode, "follow_up")
        self.assertIn("Fleet", route.standalone_query)
        self.assertEqual(route.reason, "context_dependent_portfolio_question")
        self.assertEqual(route.topic_source_titles, ("Fleet Smart Vehicle Digital Twin Prototype",))
        request = client.interactions.kwargs
        self.assertEqual(request["response_format"]["mime_type"], "application/json")
        self.assertNotIn("file_search", request)
        context = json.loads(request["input"])["recent_conversation"]
        self.assertEqual(len(context), 2)
        self.assertEqual(
            json.loads(request["input"])["trusted_source_titles"],
            ["Fleet Smart Vehicle Digital Twin Prototype"],
        )

    def test_generic_greeting_returns_a_short_conversation_reply(self):
        client = FakeClient(
            '{"mode":"conversation","standalone_query":"","reply":"Hello! What would you like to explore?","reason":"generic_conversation","topic_source_titles":[]}'
        )

        route = GeminiConversationRouter(client, settings()).route("Hello", ())

        self.assertEqual(route.mode, "conversation")
        self.assertEqual(route.reply, "Hello! What would you like to explore?")
        self.assertEqual(route.reason, "generic_conversation")

    def test_private_request_is_refused_without_a_provider_call(self):
        client = FakeClient("not used")

        route = GeminiConversationRouter(client, settings()).route("What is Mihir's phone number?", ())

        self.assertEqual(route.mode, "refuse")
        self.assertIsNone(client.interactions.kwargs)

    def test_gmail_request_is_refused_without_a_provider_call(self):
        client = FakeClient("not used")

        route = GeminiConversationRouter(client, settings()).route("What is Mihir's Gmail?", ())

        self.assertEqual(route.mode, "refuse")
        self.assertIsNone(client.interactions.kwargs)

    def test_context_reference_is_recognized_for_retrieval_rewrite(self):
        self.assertTrue(question_depends_on_conversation("Does any of his projects use this?"))
        self.assertTrue(question_depends_on_conversation("Any other project?"))
        self.assertFalse(question_depends_on_conversation("Tell me about his skills."))
        self.assertFalse(question_depends_on_conversation("Which project uses Docker?"))

    def test_clear_portfolio_questions_and_exact_greetings_can_skip_the_router(self):
        self.assertTrue(is_self_contained_portfolio_question("Tell me about his skills."))
        self.assertTrue(is_self_contained_portfolio_question("Give me the Fleet architecture."))
        self.assertTrue(is_self_contained_portfolio_question("What is Mihir's CGPA?"))
        self.assertTrue(
            is_self_contained_portfolio_question("Tell me about the Source-Cited RAG Assistant.")
        )
        self.assertFalse(is_self_contained_portfolio_question("Which project uses it?"))
        self.assertEqual(
            local_conversation_reply("heyyy"),
            "Hello! How can I help you explore Mihir's portfolio today?",
        )
        self.assertIsNone(local_conversation_reply("What is React?"))

    def test_generic_concept_can_anchor_a_project_follow_up(self):
        query = generic_concept_project_follow_up(
            "Which project is related to that?",
            (
                ConversationTurn("visitor", "What is networking?", False),
                ConversationTurn("assistant", "A generic networking explanation.", False),
            ),
        )

        self.assertEqual(query, "Which of Mihir's projects is related to networking?")

    def test_older_generic_topic_is_not_revived_after_a_newer_project_answer(self):
        query = generic_concept_project_follow_up(
            "Which project is related to that?",
            (
                ConversationTurn("visitor", "What is networking?", False),
                ConversationTurn("assistant", "A generic networking explanation.", False),
                ConversationTurn("visitor", "Tell me about Fleet.", False),
                ConversationTurn("assistant", "Fleet uses Docker.", True),
            ),
        )

        self.assertIsNone(query)

    def test_invalid_structured_output_fails_closed(self):
        client = FakeClient(
            '{"mode":"conversation","standalone_query":"","reply":"","reason":"generic_conversation","topic_source_titles":[]}'
        )

        with self.assertRaises(ValueError):
            GeminiConversationRouter(client, settings()).route("Hello", ())

    def test_unrecognized_source_title_is_not_trusted_as_a_hint(self):
        client = FakeClient(
            json.dumps(
                {
                    "mode": "grounded",
                    "standalone_query": "Which project uses Docker?",
                    "reply": "",
                    "reason": "direct_portfolio_question",
                    "topic_source_titles": [
                        "Fleet Smart Vehicle Digital Twin Prototype",
                        "Invented private notes",
                    ],
                }
            )
        )

        route = GeminiConversationRouter(
            client,
            settings(),
            trusted_source_titles=("Fleet Smart Vehicle Digital Twin Prototype",),
        ).route("Which project uses Docker?", ())

        self.assertEqual(route.topic_source_titles, ("Fleet Smart Vehicle Digital Twin Prototype",))

    def test_stateful_route_passes_previous_interaction_and_can_be_deleted(self):
        client = FakeClient(
            json.dumps(
                {
                    "mode": "follow_up",
                    "standalone_query": "Which projects use Docker?",
                    "reply": "",
                    "reason": "context_dependent_portfolio_question",
                    "topic_source_titles": [],
                }
            )
        )
        router = GeminiConversationRouter(client, settings())

        route = router.route(
            "Which project uses it?",
            (),
            previous_interaction_id="interaction-previous",
            store=True,
        )

        self.assertEqual(route.interaction_id, "interaction-new")
        self.assertTrue(client.interactions.kwargs["store"])
        self.assertEqual(
            client.interactions.kwargs["previous_interaction_id"], "interaction-previous"
        )
        self.assertTrue(router.delete_interaction(route.interaction_id))
        self.assertEqual(client.interactions.deleted[0][0], "interaction-new")

    def test_previous_interaction_forces_temporary_storage(self):
        client = FakeClient(
            json.dumps(
                {
                    "mode": "grounded",
                    "standalone_query": "Which project uses Docker?",
                    "reply": "",
                    "reason": "direct_portfolio_question",
                    "topic_source_titles": [],
                }
            )
        )

        GeminiConversationRouter(client, settings()).route(
            "Which project uses Docker?",
            (),
            previous_interaction_id="interaction-previous",
            store=False,
        )

        self.assertTrue(client.interactions.kwargs["store"])


if __name__ == "__main__":
    unittest.main()
