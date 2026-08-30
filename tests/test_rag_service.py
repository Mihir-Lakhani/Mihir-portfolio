import unittest
from pathlib import Path
from types import SimpleNamespace

from rag.config import RagSettings
from rag.generator import INSUFFICIENT_EVIDENCE_ANSWER
from rag.ingestion import GeminiDocumentRecord
from rag.models import (
    ApprovedDiagram,
    Citation,
    ConversationRoute,
    ConversationTurn,
    FileSearchCitation,
    GeneratedAnswer,
    GeneratedClaim,
    GeneratedSection,
    LocalChunkCitation,
)
from rag.service import PortfolioAssistantService
from rag.sources import SourceRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


class RecordingGenerator:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.options = []

    def answer(self, question, **options):
        self.calls.append(question)
        self.options.append(options)
        return self.response


class RecordingRouter:
    def __init__(self, route):
        self._result = route
        self.calls = []
        self.deleted_interactions = []

    def route(self, question, conversation, **options):
        self.calls.append((question, conversation, options))
        return self._result

    def delete_interaction(self, interaction_id):
        self.deleted_interactions.append(interaction_id)
        return True


class RecordingConversationResponder:
    def __init__(self, interaction_id="interaction-final"):
        self.interaction_id = interaction_id
        self.calls = []

    def reply(self, question, suggested_reply, **options):
        self.calls.append((question, suggested_reply, options))
        return SimpleNamespace(reply=suggested_reply, interaction_id=self.interaction_id)


class PortfolioAssistantServiceTests(unittest.TestCase):
    def setUp(self):
        self.registry = SourceRegistry.from_file(PROJECT_ROOT / "knowledge" / "sources.json")
        self.document_name = "fileSearchStores/test-store/documents/digital-twin"
        self.document_hash = "fleet-hash"
        self.approved_documents = {
            "project-digital-twin-fleet": GeminiDocumentRecord(
                document_name=self.document_name,
                sha256=self.document_hash,
                display_name="digital_twin_fleet.md",
            )
        }

    def valid_response(self) -> GeneratedAnswer:
        claim = "The Digital Twin Fleet Smart Vehicle project uses Docker and Kubernetes."
        return GeneratedAnswer(
            answerable=True,
            claims=(GeneratedClaim(text=claim, start_index=20, end_index=20 + len(claim)),),
            file_citations=(
                FileSearchCitation(
                    source_id="project-digital-twin-fleet",
                    content_sha256=self.document_hash,
                    document_name=self.document_name,
                    start_index=20,
                    end_index=20 + len(claim),
                ),
            ),
        )

    def test_successful_grounded_answer_uses_trusted_manifest_citation(self):
        generator = RecordingGenerator(self.valid_response())
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents
        )

        result = service.answer("Which project uses Docker?")

        self.assertTrue(result.grounded)
        self.assertEqual(
            result.answer,
            "The Digital Twin Fleet Smart Vehicle project uses Docker and Kubernetes.",
        )
        self.assertEqual([citation.source_id for citation in result.citations], ["project-digital-twin-fleet"])
        self.assertEqual(
            result.citations[0].url,
            "https://github.com/Mihir-Lakhani/fleet-digital-twin-eclipse-ditto",
        )
        self.assertEqual(generator.calls, ["Which project uses Docker?"])

    def test_local_chunk_evidence_and_cited_diagram_are_verified(self):
        response = GeneratedAnswer(
            answerable=True,
            claims=(
                GeneratedClaim(
                    text="The Fleet project uses Docker Compose.",
                    start_index=None,
                    end_index=None,
                    evidence_ids=("chunk-fleet",),
                ),
            ),
            local_chunk_citations=(
                LocalChunkCitation("chunk-fleet", "project-digital-twin-fleet", self.document_hash),
            ),
            diagram_id="diagram-fleet",
        )
        diagram = ApprovedDiagram(
            diagram_id="diagram-fleet",
            source_id="project-digital-twin-fleet",
            content_sha256=self.document_hash,
            title="End-to-end architecture",
            mermaid="flowchart LR\nA --> B",
        )
        service = PortfolioAssistantService(
            settings(),
            self.registry,
            RecordingGenerator(response),
            self.approved_documents,
            approved_local_chunks={
                "chunk-fleet": LocalChunkCitation(
                    "chunk-fleet", "project-digital-twin-fleet", self.document_hash
                )
            },
            approved_diagrams={"diagram-fleet": diagram},
        )

        result = service.answer("Show the Fleet architecture flowchart")

        self.assertTrue(result.grounded)
        self.assertEqual(result.citations[0].source_id, "project-digital-twin-fleet")
        self.assertEqual(result.diagram, diagram)

    def test_diagram_only_fallback_is_grounded_by_approved_diagram_records(self):
        diagrams = (
            ApprovedDiagram(
                "diagram-fleet",
                "project-digital-twin-fleet",
                self.document_hash,
                "End-to-end architecture",
                "flowchart LR\nA --> B",
            ),
            ApprovedDiagram(
                "diagram-browser",
                "project-digital-twin-fleet",
                self.document_hash,
                "Browser-to-API flow",
                "sequenceDiagram\nA->>B: Request",
            ),
        )
        response = GeneratedAnswer(
            answerable=True,
            claims=(
                GeneratedClaim(
                    "Here are the approved Fleet diagrams.",
                    None,
                    None,
                    tuple(diagram.diagram_id for diagram in diagrams),
                ),
            ),
            diagram_ids=tuple(diagram.diagram_id for diagram in diagrams),
        )
        service = PortfolioAssistantService(
            settings(),
            self.registry,
            RecordingGenerator(response),
            self.approved_documents,
            approved_diagrams={diagram.diagram_id: diagram for diagram in diagrams},
        )

        result = service.answer("Give me all diagrams for the Fleet project")

        self.assertTrue(result.grounded)
        self.assertEqual(len(result.diagrams), 2)
        self.assertEqual(result.citations[0].source_id, "project-digital-twin-fleet")
        self.assertEqual(len(result.to_dict()["diagrams"]), 2)

    def test_explicit_diagram_request_passes_additive_scope_to_generator(self):
        generator = RecordingGenerator(self.valid_response())
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents
        )

        service.answer("mermaid diagram for fleet")

        self.assertEqual(generator.options[0]["diagram_scope"], "single")
        self.assertNotIn("response_profile", generator.options[0])

    def test_explicit_everything_request_passes_deep_dive_profile(self):
        generator = RecordingGenerator(self.valid_response())
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents
        )

        service.answer("Tell me everything about the Fleet project")

        self.assertEqual(generator.options[0]["response_profile"], "deep_dive")

    def test_stateful_profile_category_keeps_a_bare_expansion_on_profile_evidence(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(mode="grounded", standalone_query="List all projects.")
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer(
            "Tell me everything.",
            previous_interaction_id="interaction-profile",
            use_stateful_router=True,
            profile_context=True,
        )

        self.assertEqual(router.calls, [])
        self.assertEqual(generator.calls, ["Mihir Lakhani profile."])
        self.assertEqual(generator.options[0]["response_profile"], "profile_deep_dive")
        self.assertNotIn("diagram_scope", generator.options[0])

    def test_validated_deep_dive_sections_are_preserved_for_the_browser(self):
        response = GeneratedAnswer(
            answerable=True,
            claims=(),
            sections=(
                GeneratedSection(
                    "Purpose",
                    "The Fleet prototype explores vehicle twin records.",
                    ("chunk-fleet",),
                ),
                GeneratedSection(
                    "Architecture",
                    "Its browser path uses an API before persistence.",
                    ("chunk-fleet",),
                ),
            ),
            local_chunk_citations=(
                LocalChunkCitation("chunk-fleet", "project-digital-twin-fleet", self.document_hash),
            ),
        )
        service = PortfolioAssistantService(
            settings(),
            self.registry,
            RecordingGenerator(response),
            self.approved_documents,
            approved_local_chunks={
                "chunk-fleet": LocalChunkCitation(
                    "chunk-fleet", "project-digital-twin-fleet", self.document_hash
                )
            },
        )

        result = service.answer("Tell me everything about the Fleet project")

        self.assertTrue(result.grounded)
        self.assertEqual([section.title for section in result.sections], ["Purpose", "Architecture"])
        self.assertIn("\n\nArchitecture\n", result.answer)
        self.assertEqual(result.to_dict()["sections"][0]["title"], "Purpose")

    def test_deep_dive_section_with_forged_evidence_is_refused(self):
        response = GeneratedAnswer(
            answerable=True,
            claims=(),
            sections=(GeneratedSection("Architecture", "Unsupported detail.", ("forged",)),),
        )
        service = PortfolioAssistantService(
            settings(), self.registry, RecordingGenerator(response), self.approved_documents
        )

        result = service.answer("Tell me everything about the Fleet project")

        self.assertFalse(result.grounded)
        self.assertEqual(result.citations, ())

    def test_forged_local_chunk_reference_is_refused(self):
        response = GeneratedAnswer(
            answerable=True,
            claims=(GeneratedClaim("Unsupported", None, None, ("chunk-fleet",)),),
            local_chunk_citations=(
                LocalChunkCitation("chunk-fleet", "project-digital-twin-fleet", "attacker-hash"),
            ),
        )
        service = PortfolioAssistantService(
            settings(),
            self.registry,
            RecordingGenerator(response),
            self.approved_documents,
            approved_local_chunks={
                "chunk-fleet": LocalChunkCitation(
                    "chunk-fleet", "project-digital-twin-fleet", self.document_hash
                )
            },
        )

        result = service.answer("Which project uses Docker?")

        self.assertFalse(result.grounded)
        self.assertEqual(result.citations, ())

    def test_follow_up_is_rewritten_by_router_before_grounded_generation(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="follow_up",
                standalone_query="Which Docker Compose services does the Fleet project declare?",
            )
        )
        service = PortfolioAssistantService(
            settings(),
            self.registry,
            generator,
            self.approved_documents,
            router=router,
            conversation_responder=RecordingConversationResponder(),
        )

        result = service.answer(
            "Which services?",
            (
                ConversationTurn("visitor", "Tell me about Fleet.", False),
                ConversationTurn("assistant", "Fleet uses Docker Compose.", True),
            ),
        )

        self.assertTrue(result.grounded)
        self.assertEqual(result.mode, "follow_up")
        self.assertEqual(
            generator.calls, ["Which Docker Compose services does the Fleet project declare?"]
        )
        self.assertEqual(router.calls[0][0], "Which services?")

    def test_self_contained_portfolio_question_keeps_its_original_retrieval_terms(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="grounded",
                standalone_query="Tell me about Mihir's work.",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer("Which project uses Docker?")

        self.assertEqual(generator.calls, ["Which project uses Docker?"])

    def test_direct_all_projects_request_uses_the_complete_catalogue_scope(self):
        generator = RecordingGenerator(self.valid_response())
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents
        )

        service.answer("Tell me about all of Mihir's projects.")

        self.assertEqual(generator.options[0]["retrieval_scope"], "all_projects")

    def test_stateful_profile_question_bypasses_an_overbroad_router_scope(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="grounded",
                standalone_query="List every project.",
                retrieval_scope="all_projects",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer("Tell me everything about Mihir.", use_stateful_router=True)

        self.assertEqual(router.calls, [])
        self.assertEqual(generator.calls, ["Tell me everything about Mihir."])
        self.assertEqual(generator.options[0]["retrieval_scope"], "relevant")

    def test_bare_profile_expansion_bypasses_the_router_and_uses_profile_deep_dive(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="grounded",
                standalone_query="List every project and education detail.",
                retrieval_scope="all_projects",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer(
            "Tell me everything.",
            conversation=(
                ConversationTurn("visitor", "Tell me about him.", False),
                ConversationTurn("assistant", "A profile overview.", True),
            ),
            use_stateful_router=True,
        )

        self.assertEqual(router.calls, [])
        self.assertEqual(generator.calls, ["Mihir Lakhani profile."])
        self.assertEqual(generator.options[0]["retrieval_scope"], "relevant")
        self.assertEqual(generator.options[0]["response_profile"], "profile_deep_dive")

    def test_router_cannot_promote_a_vague_follow_up_to_education(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="follow_up",
                standalone_query="Tell me more about Mihir's education and CGPA.",
                reason="context_dependent_portfolio_question",
                retrieval_scope="relevant",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer("Tell me more.", use_stateful_router=True)

        self.assertEqual(
            generator.calls,
            ["Tell me more about Mihir Lakhani's public professional profile."],
        )

    def test_profile_follow_up_uses_the_detailed_evidence_path(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="grounded",
                standalone_query=(
                    "Tell me more about Mihir Lakhani's background, research internship, "
                    "learning journey, skills, and career direction."
                ),
                topic_source_titles=("Mihir Lakhani profile",),
                retrieval_scope="relevant",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer("Tell me more.", use_stateful_router=True)

        self.assertEqual(generator.options[0]["response_profile"], "profile_deep_dive")

    def test_router_cannot_expand_an_ambiguous_follow_up_to_all_projects(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="follow_up",
                standalone_query="Tell me more about Mihir.",
                reason="context_dependent_portfolio_question",
                retrieval_scope="all_projects",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer("Could you expand on that?", use_stateful_router=True)

        self.assertEqual(generator.options[0]["retrieval_scope"], "relevant")

    def test_source_selector_rejects_valid_evidence_outside_the_selected_scope(self):
        service = PortfolioAssistantService(
            settings(),
            self.registry,
            RecordingGenerator(self.valid_response()),
            self.approved_documents,
            source_selector=lambda question: ("portfolio-background",),
        )

        result = service.answer("Tell me about Mihir.")

        self.assertFalse(result.grounded)
        self.assertEqual(result.refusal_reason, "invalid_generation_evidence")
        self.assertEqual(result.citations, ())

    def test_context_reference_uses_router_query_even_if_router_labels_it_grounded(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="grounded",
                standalone_query="Which of Mihir's projects uses Docker?",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer(
            "Does any of his projects use this?",
            (
                ConversationTurn("visitor", "Tell me about Docker.", False),
                ConversationTurn("assistant", "Docker packages applications in containers.", False),
            ),
        )

        self.assertEqual(generator.calls, ["Which of Mihir's projects uses Docker?"])

    def test_general_conversation_does_not_call_the_grounded_generator(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="conversation",
                reply="Hello! What would you like to explore?",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        result = service.answer("What is a vector database?")

        self.assertFalse(result.grounded)
        self.assertEqual(result.mode, "conversation")
        self.assertEqual(result.answer, "Hello! What would you like to explore?")
        self.assertEqual(generator.calls, [])

    def test_exact_greeting_uses_no_router_or_grounded_generator(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(ConversationRoute(mode="grounded", standalone_query="unused"))
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        result = service.answer("heyyy")

        self.assertEqual(result.mode, "conversation")
        self.assertEqual(router.calls, [])
        self.assertEqual(generator.calls, [])

    def test_stateful_greeting_starts_a_router_interaction(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="conversation",
                reply="Hello! What would you like to explore?",
                interaction_id="interaction-greeting",
            )
        )
        service = PortfolioAssistantService(
            settings(),
            self.registry,
            generator,
            self.approved_documents,
            router=router,
            conversation_responder=RecordingConversationResponder(),
        )

        result = service.answer("heyy", use_stateful_router=True)

        self.assertEqual(result.mode, "conversation")
        self.assertEqual(result.conversation_interaction_id, "interaction-final")
        self.assertEqual(
            router.calls,
            [("heyy", (), {"previous_interaction_id": None, "store": False})],
        )
        self.assertEqual(generator.calls, [])

    def test_clear_portfolio_question_skips_router_and_goes_to_file_search(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(ConversationRoute(mode="conversation", reply="unused"))
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer("Tell me about Mihir's skills.")

        self.assertEqual(router.calls, [])
        self.assertEqual(generator.calls, ["Tell me about Mihir's skills."])

    def test_contextual_question_still_uses_the_router(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="follow_up",
                standalone_query="Which other Mihir projects use Docker?",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer(
            "Any other project?",
            (ConversationTurn("assistant", "Fleet uses Docker.", True),),
        )

        self.assertEqual(len(router.calls), 1)
        self.assertEqual(generator.calls, ["Which other Mihir projects use Docker?"])

    def test_stateful_router_uses_the_prior_interaction_without_browser_turns(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(
            ConversationRoute(
                mode="follow_up",
                standalone_query="Which project uses Docker?",
                interaction_id="interaction-current",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        result = service.answer(
            "Which project uses it?",
            previous_interaction_id="interaction-previous",
            use_stateful_router=True,
        )

        self.assertEqual(generator.calls, ["Which project uses Docker?"])
        self.assertEqual(router.calls[0][1], ())
        self.assertEqual(
            router.calls[0][2],
            {"previous_interaction_id": "interaction-previous", "store": True},
        )
        self.assertEqual(router.deleted_interactions, ["interaction-current"])
        self.assertEqual(
            generator.options[0],
            {
                "previous_interaction_id": "interaction-previous",
                "store": True,
                "retrieval_scope": "relevant",
            },
        )
        self.assertIsNone(result.conversation_interaction_id)

    def test_generation_failure_discards_the_uncommitted_router_interaction(self):
        class FailingGenerator:
            def answer(self, question, **options):
                raise RuntimeError("File Search timed out")

        router = RecordingRouter(
            ConversationRoute(
                mode="grounded",
                standalone_query="Which project uses Docker?",
                interaction_id="interaction-uncommitted",
            )
        )
        service = PortfolioAssistantService(
            settings(), self.registry, FailingGenerator(), self.approved_documents, router=router
        )

        with self.assertRaisesRegex(RuntimeError, "File Search timed out"):
            service.answer("Which project uses Docker?", use_stateful_router=True)

        self.assertEqual(router.deleted_interactions, [])

    def test_generic_concept_project_follow_up_skips_the_router(self):
        generator = RecordingGenerator(self.valid_response())
        router = RecordingRouter(ConversationRoute(mode="conversation", reply="unused"))
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents, router=router
        )

        service.answer(
            "Which project is related to that?",
            (
                ConversationTurn("visitor", "What is networking?", False),
                ConversationTurn("assistant", "Generic networking explanation.", False),
            ),
        )

        self.assertEqual(router.calls, [])
        self.assertEqual(
            generator.calls, ["Which of Mihir's projects is related to networking?"]
        )

    def test_5g_citation_includes_only_the_manifest_defined_simulation_link(self):
        source = self.registry.resolve("project-5g-handover")
        self.assertIsNotNone(source)

        citation = Citation.from_source(source)

        self.assertEqual(
            citation.url,
            "https://github.com/Mihir-Lakhani/5G-Handover-Stability-Aware-ML",
        )
        self.assertEqual(citation.demo_url, "/mobility")
        self.assertEqual(citation.demo_label, "Open Simulation")
        self.assertEqual(citation.to_dict()["demo_url"], "/mobility")

    def test_unsupported_question_refuses_without_citations(self):
        generator = RecordingGenerator(GeneratedAnswer(answerable=False, claims=()))
        service = PortfolioAssistantService(
            settings(), self.registry, generator, self.approved_documents
        )

        result = service.answer("What is Mihir's favourite food?")

        self.assertFalse(result.grounded)
        self.assertEqual(result.answer, INSUFFICIENT_EVIDENCE_ANSWER)
        self.assertEqual(result.citations, ())
        self.assertEqual(result.refusal_reason, "insufficient_generation_evidence")

    def test_mismatched_hash_or_document_citation_is_refused(self):
        response = self.valid_response()
        response = GeneratedAnswer(
            answerable=True,
            claims=response.claims,
            file_citations=(
                FileSearchCitation(
                    source_id="project-digital-twin-fleet",
                    content_sha256="attacker-hash",
                    document_name="fileSearchStores/test-store/documents/attacker",
                    start_index=20,
                    end_index=120,
                ),
            ),
        )
        service = PortfolioAssistantService(
            settings(), self.registry, RecordingGenerator(response), self.approved_documents
        )

        result = service.answer("Which project uses Docker?")

        self.assertFalse(result.grounded)
        self.assertEqual(result.citations, ())
        self.assertEqual(result.refusal_reason, "invalid_generation_evidence")

    def test_citation_outside_the_claim_range_is_refused(self):
        response = self.valid_response()
        response = GeneratedAnswer(
            answerable=True,
            claims=response.claims,
            file_citations=(
                FileSearchCitation(
                    source_id="project-digital-twin-fleet",
                    content_sha256=self.document_hash,
                    document_name=self.document_name,
                    start_index=0,
                    end_index=5,
                ),
            ),
        )
        service = PortfolioAssistantService(
            settings(), self.registry, RecordingGenerator(response), self.approved_documents
        )

        result = service.answer("Which project uses Docker?")

        self.assertFalse(result.grounded)
        self.assertEqual(result.refusal_reason, "invalid_generation_evidence")

    def test_document_file_name_can_be_used_when_uri_is_omitted(self):
        response = self.valid_response()
        response = GeneratedAnswer(
            answerable=True,
            claims=response.claims,
            file_citations=(
                FileSearchCitation(
                    source_id="project-digital-twin-fleet",
                    content_sha256=self.document_hash,
                    document_name=None,
                    file_name="digital_twin_fleet.md",
                    start_index=20,
                    end_index=20 + len(response.claims[0].text),
                ),
            ),
        )
        service = PortfolioAssistantService(
            settings(), self.registry, RecordingGenerator(response), self.approved_documents
        )

        result = service.answer("Which project uses Docker?")

        self.assertTrue(result.grounded)

    def test_store_scoped_uri_uses_matching_approved_file_name(self):
        response = self.valid_response()
        response = GeneratedAnswer(
            answerable=True,
            claims=response.claims,
            file_citations=(
                FileSearchCitation(
                    source_id="project-digital-twin-fleet",
                    content_sha256=self.document_hash,
                    document_name="fileSearchStores/test-store",
                    file_name="digital_twin_fleet.md",
                    start_index=20,
                    end_index=20 + len(response.claims[0].text),
                ),
            ),
        )
        service = PortfolioAssistantService(
            settings(), self.registry, RecordingGenerator(response), self.approved_documents
        )

        result = service.answer("Which project uses Docker?")

        self.assertTrue(result.grounded)


if __name__ == "__main__":
    unittest.main()
