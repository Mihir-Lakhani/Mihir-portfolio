import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from flask import Flask

from rag.config import RagConfigurationError
from rag.models import AssistantResult, Citation
from rag.routes import InMemoryMinuteRateLimiter, rag_bp


class AllowAllLimiter:
    def allow(self, key, limit):
        return True


class FakeService:
    def __init__(self):
        self.questions = []
        self.options = []
        self.interaction_ids = []
        self.navigation_topics = []
        self.ended_interactions = []

    def answer(self, question, conversation=(), **options):
        self.questions.append((question, conversation))
        self.options.append(options)
        return AssistantResult(
            answer="Mihir uses Flask for the portfolio.",
            citations=(
                Citation(
                    source_id="skills-and-tools",
                    title="Skills and tools",
                    url="/#about",
                    source_type="skills",
                    project="Portfolio",
                ),
            ),
            grounded=True,
            conversation_interaction_id=(
                self.interaction_ids.pop(0) if self.interaction_ids else None
            ),
            conversation_navigation_topic=(
                self.navigation_topics.pop(0) if self.navigation_topics else None
            ),
        )

    def end_conversation(self, interaction_id):
        self.ended_interactions.append(interaction_id)
        return True


class PortfolioRoutesTests(unittest.TestCase):
    def make_client(self, factory, limiter=None):
        app = Flask(__name__)
        app.config.update(
            TESTING=True,
            RAG_SERVICE_FACTORY=factory,
            RAG_RATE_LIMITER=limiter or AllowAllLimiter(),
        )
        app.register_blueprint(rag_bp)
        return app.test_client()

    def test_endpoint_returns_grounded_answer_and_citations(self):
        service = FakeService()
        client = self.make_client(lambda: service)

        response = client.post("/api/ask", json={"question": "  Which framework is used?  "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["citations"][0]["source_id"], "skills-and-tools")
        self.assertEqual(service.questions, [("Which framework is used?", ())])

    def test_service_factory_is_cached_for_the_flask_process(self):
        calls = []

        def factory():
            calls.append("created")
            return FakeService()

        client = self.make_client(factory)
        client.post("/api/ask", json={"question": "Which framework is used?"})
        client.post("/api/ask", json={"question": "Which framework is used?"})

        self.assertEqual(calls, ["created"])

    def test_endpoint_passes_bounded_browser_conversation_without_persisting_it(self):
        service = FakeService()
        client = self.make_client(lambda: service)

        response = client.post(
            "/api/ask",
            json={
                "question": "Which services?",
                "conversation": [
                    {"role": "visitor", "text": "Tell me about Fleet.", "grounded": False},
                    {
                        "role": "assistant",
                        "text": "Fleet uses a local multi-service environment.",
                        "grounded": True,
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        question, conversation = service.questions[0]
        self.assertEqual(question, "Which services?")
        self.assertEqual([turn.role for turn in conversation], ["visitor", "assistant"])
        self.assertTrue(conversation[1].grounded)

    def test_endpoint_accepts_a_long_assistant_turn_within_total_context_limit(self):
        service = FakeService()
        client = self.make_client(lambda: service)
        long_reply = "Grounded project explanation. " * 30

        response = client.post(
            "/api/ask",
            json={
                "question": "How many projects does he have?",
                "conversation": [
                    {"role": "visitor", "text": "Tell me about his projects.", "grounded": False},
                    {"role": "assistant", "text": long_reply, "grounded": True},
                ],
            },
        )

        self.assertGreater(len(long_reply), 500)
        self.assertLess(len(long_reply), 2400)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.questions[0][1][1].text, long_reply.strip())

    def test_endpoint_rejects_malformed_conversation_context(self):
        client = self.make_client(FakeService)

        response = client.post(
            "/api/ask",
            json={"question": "Tell me more", "conversation": [{"role": "attacker"}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Conversation context", response.get_json()["error"])

    def test_browser_session_reuses_only_the_opaque_router_interaction_id(self):
        service = FakeService()
        service.interaction_ids = ["interaction-one", "interaction-two"]
        session_id = str(uuid4())

        with patch.dict(os.environ, {"RAG_STATEFUL_CONVERSATIONS": "true"}, clear=False):
            client = self.make_client(lambda: service)
            first = client.post(
                "/api/ask",
                json={"question": "What is Docker?", "conversation_session_id": session_id},
            )
            second = client.post(
                "/api/ask",
                json={"question": "Which project uses it?", "conversation_session_id": session_id},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(service.questions[0], ("What is Docker?", ()))
        self.assertEqual(service.questions[1], ("Which project uses it?", ()))
        self.assertEqual(
            service.options[0],
            {"previous_interaction_id": None, "use_stateful_router": True},
        )
        self.assertEqual(
            service.options[1],
            {"previous_interaction_id": "interaction-one", "use_stateful_router": True},
        )
        self.assertNotIn("interaction", first.get_data(as_text=True).casefold())

    def test_browser_session_uses_profile_navigation_without_storing_chat_text(self):
        service = FakeService()
        service.interaction_ids = ["interaction-one", "interaction-two"]
        service.navigation_topics = ["profile", "profile"]
        session_id = str(uuid4())

        with patch.dict(os.environ, {"RAG_STATEFUL_CONVERSATIONS": "true"}, clear=False):
            client = self.make_client(lambda: service)
            client.post(
                "/api/ask",
                json={"question": "Tell me about him.", "conversation_session_id": session_id},
            )
            second = client.post(
                "/api/ask",
                json={"question": "Tell me everything.", "conversation_session_id": session_id},
            )

        self.assertTrue(service.options[1]["profile_context"])

    def test_page_end_deletes_the_active_router_interaction_and_forgets_it(self):
        service = FakeService()
        service.interaction_ids = ["interaction-one"]
        session_id = str(uuid4())

        with patch.dict(os.environ, {"RAG_STATEFUL_CONVERSATIONS": "true"}, clear=False):
            client = self.make_client(lambda: service)
            client.post(
                "/api/ask",
                json={"question": "What is Docker?", "conversation_session_id": session_id},
            )
            ended = client.post(
                "/api/conversation/end",
                json={"conversation_session_id": session_id},
            )
            client.post(
                "/api/ask",
                json={"question": "What is React?", "conversation_session_id": session_id},
            )

        self.assertEqual(ended.status_code, 200)
        self.assertEqual(service.ended_interactions, ["interaction-one"])
        self.assertIsNone(service.options[-1]["previous_interaction_id"])

    def test_session_and_legacy_browser_context_cannot_be_mixed(self):
        client = self.make_client(FakeService)

        response = client.post(
            "/api/ask",
            json={
                "question": "Which services?",
                "conversation_session_id": str(uuid4()),
                "conversation": [
                    {"role": "visitor", "text": "Tell me about Fleet.", "grounded": False}
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("either legacy conversation context", response.get_json()["error"])

    def test_endpoint_rejects_malformed_questions(self):
        client = self.make_client(FakeService)

        response = client.post("/api/ask", json={"question": " "})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Please enter", response.get_json()["error"])

    def test_endpoint_hides_gemini_configuration_details(self):
        def unavailable_service():
            raise RagConfigurationError("GEMINI_API_KEY is missing")

        client = self.make_client(unavailable_service)
        response = client.post("/api/ask", json={"question": "Tell me about projects"})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "The portfolio assistant is not configured yet.")
        self.assertNotIn("GEMINI_API_KEY", response.get_data(as_text=True))

    def test_provider_failure_never_leaks_technical_details(self):
        def failed_service():
            raise RuntimeError("Gemini rejected key=server-secret and request trace=123")

        client = self.make_client(failed_service)
        response = client.post("/api/ask", json={"question": "Tell me about projects"})

        self.assertEqual(response.status_code, 502)
        body = response.get_data(as_text=True)
        self.assertIn("temporarily unavailable", body)
        self.assertNotIn("Gemini", body)
        self.assertNotIn("server-secret", body)

    def test_provider_quota_error_is_a_visitor_safe_429(self):
        class ProviderQuotaError(RuntimeError):
            code = 429

        def rate_limited_service():
            raise ProviderQuotaError("provider quota exhausted")

        client = self.make_client(rate_limited_service)
        response = client.post("/api/ask", json={"question": "Tell me about projects"})

        self.assertEqual(response.status_code, 429)
        self.assertIn("try again in a minute", response.get_json()["error"])
        self.assertNotIn("quota", response.get_data(as_text=True))

    def test_local_provider_diagnostic_is_opt_in_and_redacted(self):
        def failed_service():
            raise RuntimeError("provider rejected key=server-secret and trace=123")

        with tempfile.TemporaryDirectory() as temporary_directory:
            diagnostic_path = Path(temporary_directory) / "provider-failure.json"
            app = Flask(__name__)
            app.config.update(
                TESTING=True,
                RAG_SERVICE_FACTORY=failed_service,
                RAG_RATE_LIMITER=AllowAllLimiter(),
                RAG_LOCAL_DIAGNOSTICS_PATH=diagnostic_path,
            )
            app.register_blueprint(rag_bp)

            response = app.test_client().post(
                "/api/ask", json={"question": "Tell me about projects"}
            )

            self.assertEqual(response.status_code, 502)
            diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            self.assertIn("RuntimeError", diagnostic["message"])
            self.assertNotIn("server-secret", diagnostic["message"])
            self.assertIn("trace", diagnostic)
            self.assertNotIn("Tell me about projects", diagnostic_path.read_text(encoding="utf-8"))

    def test_local_diagnostic_keeps_a_bounded_redacted_history(self):
        class ChangingService:
            def __init__(self):
                self.calls = 0

            def answer(self, question, conversation=(), **options):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("provider rejected key=server-secret")
                return AssistantResult(
                    answer="Safe answer.", citations=(), grounded=False, mode="conversation"
                )

        with tempfile.TemporaryDirectory() as temporary_directory:
            diagnostic_path = Path(temporary_directory) / "provider-failure.json"
            app = Flask(__name__)
            app.config.update(
                TESTING=True,
                RAG_SERVICE_FACTORY=ChangingService,
                RAG_RATE_LIMITER=AllowAllLimiter(),
                RAG_LOCAL_DIAGNOSTICS_PATH=diagnostic_path,
            )
            app.register_blueprint(rag_bp)
            client = app.test_client()

            client.post("/api/ask", json={"question": "Tell me about projects"})
            client.post("/api/ask", json={"question": "Hello"})

            diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            self.assertEqual([item["outcome"] for item in diagnostic["recent"]], [
                "provider_failure",
                "conversation_answer",
            ])
            self.assertNotIn("server-secret", diagnostic_path.read_text(encoding="utf-8"))
            self.assertNotIn("Tell me about projects", diagnostic_path.read_text(encoding="utf-8"))

    def test_rejected_evidence_is_diagnostic_only_and_never_in_the_browser_response(self):
        class EvidenceRejectedService:
            def answer(self, question, conversation=(), **options):
                return AssistantResult(
                    answer="I don't have enough approved public information to answer that.",
                    citations=(),
                    grounded=False,
                    refusal_reason="invalid_generation_evidence",
                    evidence_diagnostic={
                        "file_citations": [
                            {
                                "source_id": "project-digital-twin-fleet",
                                "document_name": "fileSearchStores/example/documents/123",
                            }
                        ]
                    },
                )

        with tempfile.TemporaryDirectory() as temporary_directory:
            diagnostic_path = Path(temporary_directory) / "provider-failure.json"
            app = Flask(__name__)
            app.config.update(
                TESTING=True,
                RAG_SERVICE_FACTORY=EvidenceRejectedService,
                RAG_RATE_LIMITER=AllowAllLimiter(),
                RAG_LOCAL_DIAGNOSTICS_PATH=diagnostic_path,
            )
            app.register_blueprint(rag_bp)

            response = app.test_client().post(
                "/api/ask", json={"question": "Which project uses Docker?"}
            )

            self.assertEqual(response.status_code, 200)
            self.assertNotIn("project-digital-twin-fleet", response.get_data(as_text=True))
            diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            self.assertEqual(
                diagnostic["evidence"]["file_citations"][0]["source_id"],
                "project-digital-twin-fleet",
            )
            self.assertEqual(diagnostic["outcome"], "refused_answer")

    def test_minute_rate_limiter_rejects_after_the_configured_limit(self):
        limiter = InMemoryMinuteRateLimiter()

        self.assertTrue(limiter.allow("visitor", 2, now=100.0))
        self.assertTrue(limiter.allow("visitor", 2, now=101.0))
        self.assertFalse(limiter.allow("visitor", 2, now=102.0))
        self.assertTrue(limiter.allow("visitor", 2, now=160.1))


if __name__ == "__main__":
    unittest.main()
