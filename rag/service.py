from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .config import RagSettings
from .conversation import (
    GeminiConversationRouter,
    generic_concept_project_follow_up,
    is_complete_project_catalogue_request,
    is_explicit_education_question,
    is_profile_overview_question,
    is_self_contained_portfolio_question,
    is_sensitive_personal_request,
    local_conversation_reply,
    profile_expansion_follow_up,
    question_depends_on_conversation,
)
from .diagnostics import trace_event
from .gemini import create_gemini_client
from .generator import GeminiFileSearchAnswerGenerator, INSUFFICIENT_EVIDENCE_ANSWER
from .ingestion import GeminiDocumentRecord, approved_remote_documents, build_ingestion_plan
from .local_generator import GeminiConversationResponder, GeminiLocalAnswerGenerator
from .local_index import load_local_index, validate_local_index
from .local_retriever import LocalHybridRetriever
from .models import (
    AnswerSection,
    ApprovedDiagram,
    AssistantResult,
    Citation,
    ConversationRoute,
    ConversationTurn,
    FileSearchCitation,
    GeneratedAnswer,
    GeneratedClaim,
    LocalChunkCitation,
    Source,
)
from .ollama import OllamaEmbedder
from .query_hints import ApprovedSourceQueryHints
from .response_intent import classify_response_intent
from .retriever import GeminiFileSearchRetriever
from .sources import SourceRegistry


class Generator(Protocol):
    def answer(
        self,
        question: str,
        *,
        previous_interaction_id: str | None = None,
        store: bool = False,
        retrieval_scope: str = "relevant",
        response_profile: str = "concise",
        diagram_scope: str = "none",
    ) -> GeneratedAnswer: ...


class Router(Protocol):
    def route(
        self,
        question: str,
        conversation: tuple[ConversationTurn, ...],
        *,
        previous_interaction_id: str | None = None,
        store: bool = False,
    ) -> ConversationRoute: ...


class ConversationResponder(Protocol):
    def reply(
        self,
        question: str,
        suggested_reply: str,
        *,
        previous_interaction_id: str | None = None,
        store: bool = False,
    ) -> Any: ...


class PortfolioAssistantService:
    def __init__(
        self,
        settings: RagSettings,
        registry: SourceRegistry,
        generator: Generator,
        approved_documents: Mapping[str, GeminiDocumentRecord],
        router: Router | None = None,
        conversation_responder: ConversationResponder | None = None,
        approved_local_chunks: Mapping[str, LocalChunkCitation] | None = None,
        approved_diagrams: Mapping[str, ApprovedDiagram] | None = None,
        source_selector: Callable[[str], tuple[str, ...]] | None = None,
        closer: Callable[[], None] | None = None,
    ):
        self._settings = settings
        self._registry = registry
        self._generator = generator
        self._approved_documents = dict(approved_documents)
        self._router = router
        self._conversation_responder = conversation_responder
        self._approved_local_chunks = dict(approved_local_chunks or {})
        self._approved_diagrams = dict(approved_diagrams or {})
        self._source_selector = source_selector
        self._closer = closer

    def close(self) -> None:
        """Release the shared Gemini client's connection pool during shutdown."""

        if self._closer is not None:
            self._closer()

    def answer(
        self,
        question: str,
        conversation: tuple[ConversationTurn, ...] = (),
        *,
        previous_interaction_id: str | None = None,
        use_stateful_router: bool = False,
        profile_context: bool = False,
    ) -> AssistantResult:
        trace_event(
            "service.answer_started",
            question_characters=len(question),
            conversation_turn_count=len(conversation),
            stateful_router=use_stateful_router,
            continuing_interaction=previous_interaction_id is not None,
        )
        profile_expansion_query = profile_expansion_follow_up(
            question,
            conversation,
            has_profile_context=profile_context,
        )
        if is_sensitive_personal_request(question):
            # Keep this decision local even if the configured router is unavailable.
            route = ConversationRoute(
                mode="refuse", reason="sensitive_personal_request"
            )
            trace_event("service.route_selected", path="local_sensitive_refusal")
        elif is_self_contained_portfolio_question(question):
            # Direct questions about Mihir, a named project, or an explicit
            # education topic have enough stable meaning to avoid a routing
            # rewrite. The final answer call still persists the real reply for
            # the browser's Gemini memory chain.
            route = ConversationRoute(
                mode="grounded",
                standalone_query=question,
                reason="direct_portfolio_question",
                retrieval_scope=(
                    "all_projects"
                    if is_complete_project_catalogue_request(question)
                    else "relevant"
                ),
            )
            trace_event("service.route_selected", path="local_grounded_request")
        elif profile_expansion_query is not None:
            # "Tell me everything" is context-dependent. Once the latest
            # visitor topic is Mihir, keep the deep dive restricted to the
            # reviewed profile rather than allowing a broad provider rewrite
            # to introduce education details or every project.
            route = ConversationRoute(
                mode="follow_up",
                standalone_query=profile_expansion_query,
                reason="context_dependent_portfolio_question",
                topic_source_titles=("Mihir Lakhani profile",),
            )
            trace_event("service.route_selected", path="local_profile_expansion_follow_up")
        elif use_stateful_router and self._router is not None:
            # Gemini requires ``store=true`` to read a prior interaction. The
            # router therefore gets a temporary stored node only while it
            # classifies this question; it is deleted before the final reply is
            # written. The final visitor-facing reply remains the sole saved
            # conversation pointer for the browser page.
            router_requires_temporary_storage = previous_interaction_id is not None
            route = self._router.route(
                question,
                conversation,
                previous_interaction_id=previous_interaction_id,
                store=router_requires_temporary_storage,
            )
            if router_requires_temporary_storage and route.interaction_id is not None:
                deleter = getattr(self._router, "delete_interaction", None)
                deleted = bool(deleter(route.interaction_id)) if callable(deleter) else False
                trace_event(
                    "service.router_transient_interaction_cleanup",
                    attempted=True,
                    deleted=deleted,
                )
                # A router node must never become the browser's remembered
                # final reply, even when provider-side deletion is delayed.
                route = replace(route, interaction_id=None)
            trace_event("service.route_selected", path="stateful_gemini_router")
        elif (reply := local_conversation_reply(question)) is not None:
            route = ConversationRoute(
                mode="conversation", reply=reply, reason="generic_conversation"
            )
            trace_event("service.route_selected", path="local_social_reply")
        elif (standalone_query := generic_concept_project_follow_up(question, conversation)) is not None:
            route = ConversationRoute(
                mode="follow_up",
                standalone_query=standalone_query,
                reason="context_dependent_portfolio_question",
            )
            trace_event("service.route_selected", path="local_generic_concept_follow_up")
        else:
            route = (
                self._router.route(question, conversation)
                if self._router is not None
                else ConversationRoute(mode="grounded", standalone_query=question)
            )
            trace_event("service.route_selected", path="gemini_router")
        route = self._constrain_route(question, route)
        trace_event(
            "service.route_plan",
            mode=route.mode,
            reason=route.reason or None,
            next_action=(
                "approved_retrieval"
                if route.mode in {"grounded", "follow_up"}
                else "ordinary_reply"
                if route.mode == "conversation"
                else "refuse"
            ),
            source_title_hint_count=len(route.topic_source_titles),
            retrieval_scope=route.retrieval_scope,
        )
        if route.mode == "conversation":
            response = self._conversation_reply(
                question,
                route.reply,
                previous_interaction_id=previous_interaction_id,
                store=use_stateful_router,
            )
            trace_event("service.answer_conversation")
            return AssistantResult(
                answer=response[0],
                citations=(),
                grounded=False,
                mode="conversation",
                conversation_interaction_id=response[1],
            )
        if route.mode == "refuse":
            trace_event("service.answer_refused", reason="sensitive_or_unsupported_request")
            return AssistantResult(
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                citations=(),
                grounded=False,
                mode="refuse",
                refusal_reason="sensitive_or_unsupported_request",
                conversation_interaction_id=route.interaction_id,
            )

        # A self-contained portfolio question already carries its strongest
        # retrieval terms. Preserve it unless either the router selected a
        # follow-up or the visitor's wording explicitly refers to prior context.
        # The latter prevents a mistaken "grounded" label from dropping the
        # previous subject, such as Docker in "Does his project use this?".
        use_contextual_rewrite = bool(
            route.standalone_query
            and (route.mode == "follow_up" or question_depends_on_conversation(question))
        )
        retrieval_question = route.standalone_query if use_contextual_rewrite else question
        trace_event(
            "service.retrieval_question_selected",
            used_contextual_rewrite=use_contextual_rewrite,
        )
        response_intent = classify_response_intent(question)
        if (
            profile_expansion_query is not None
            or self._is_profile_continuation(question, route)
            or (
                is_profile_overview_question(question)
                and response_intent.response_profile == "deep_dive"
            )
        ):
            # A bare "tell me more" after a profile answer is too vague for a
            # fragile one-claim JSON response. The detailed local path carries
            # broader profile evidence and has a source-only fallback if the
            # writer's structured output is invalid.
            response_intent = replace(response_intent, response_profile="profile_deep_dive")
        if retrieval_question != question:
            contextual_intent = classify_response_intent(
                f"{question}\n{retrieval_question}"
            )
            # A follow-up rewrite can restore the missing diagram noun in
            # "show all of them". Detail mode remains opt-in from the visitor's
            # own wording rather than a router-authored rewrite.
            response_intent = replace(
                response_intent,
                diagram_scope=contextual_intent.diagram_scope,
            )
        generation_options: dict[str, object] = {
            "previous_interaction_id": previous_interaction_id,
            "store": use_stateful_router,
            "retrieval_scope": route.retrieval_scope,
        }
        # Preserve the exact existing generator call for ordinary questions.
        # Explicit presentation requests alone receive the additive profile fields.
        if response_intent.response_profile != "concise":
            generation_options["response_profile"] = response_intent.response_profile
        if response_intent.diagram_scope != "none":
            generation_options["diagram_scope"] = response_intent.diagram_scope
        generated = self._generator.answer(retrieval_question, **generation_options)
        allowed_source_ids = (
            frozenset(self._source_selector(retrieval_question))
            if self._source_selector is not None and route.retrieval_scope != "all_projects"
            else frozenset()
        )
        trace_event(
            "service.source_scope_selected",
            source_restricted=bool(allowed_source_ids),
            source_count=len(allowed_source_ids),
        )
        trace_event(
            "service.generation_received",
            answerable=generated.answerable,
            claim_count=len(generated.claims),
            section_count=len(generated.sections),
            file_citation_count=len(generated.file_citations),
            local_chunk_citation_count=len(generated.local_chunk_citations),
            diagram_count=len(generated.requested_diagram_ids),
            response_profile=response_intent.response_profile,
            output_bytes=len(generated.output_text.encode("utf-8")),
        )
        if not generated.answerable or not (generated.claims or generated.sections):
            trace_event("service.answer_refused", reason="insufficient_generation_evidence")
            return AssistantResult(
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                citations=(),
                grounded=False,
                mode="refuse",
                refusal_reason="insufficient_generation_evidence",
                conversation_interaction_id=generated.interaction_id,
            )

        citations: list[Citation] = []
        cited_source_ids: set[str] = set()
        answer_parts: list[str] = []
        for claim_index, claim in enumerate(generated.claims):
            sources = self._sources_for_claim(
                claim,
                generated.file_citations,
                generated.local_chunk_citations,
                allowed_source_ids,
            )
            trace_event(
                "service.claim_checked",
                claim_index=claim_index,
                has_valid_sources=bool(sources),
                source_count=len(sources),
            )
            if not sources:
                trace_event("service.answer_refused", reason="invalid_generation_evidence")
                return self._generation_refusal(generated, generated.interaction_id)
            for source in sources:
                if source.id not in cited_source_ids:
                    citations.append(Citation.from_source(source))
                    cited_source_ids.add(source.id)
            answer_parts.append(claim.text)

        validated_sections: list[AnswerSection] = []
        for section_index, section in enumerate(generated.sections):
            sources = self._sources_for_claim(
                GeneratedClaim(section.text, None, None, section.evidence_ids),
                generated.file_citations,
                generated.local_chunk_citations,
                allowed_source_ids,
            )
            trace_event(
                "service.section_checked",
                section_index=section_index,
                has_valid_sources=bool(sources),
                source_count=len(sources),
            )
            if not sources:
                trace_event("service.answer_refused", reason="invalid_generation_evidence")
                return self._generation_refusal(generated, generated.interaction_id)
            for source in sources:
                if source.id not in cited_source_ids:
                    citations.append(Citation.from_source(source))
                    cited_source_ids.add(source.id)
            validated_sections.append(AnswerSection(section.title, section.text))

        if validated_sections:
            answer_parts.extend(
                f"{section.title}\n{section.text}" for section in validated_sections
            )

        answer = "\n\n".join(answer_parts).strip() if validated_sections else " ".join(answer_parts).strip()
        if not answer or answer == INSUFFICIENT_EVIDENCE_ANSWER:
            trace_event("service.answer_refused", reason="empty_validated_answer")
            return self._generation_refusal(interaction_id=generated.interaction_id)
        diagrams = self._approved_diagrams_for_answer(
            generated.requested_diagram_ids, cited_source_ids
        )
        trace_event("service.answer_grounded", citation_count=len(citations))
        return AssistantResult(
            answer=answer,
            citations=tuple(citations),
            grounded=True,
            mode=route.mode,
            conversation_interaction_id=generated.interaction_id,
            conversation_navigation_topic=self._conversation_navigation_topic(
                question,
                retrieval_question,
                route,
            ),
            diagram=diagrams[0] if diagrams else None,
            diagrams=diagrams,
            sections=tuple(validated_sections),
        )

    @staticmethod
    def _is_profile_continuation(question: str, route: ConversationRoute) -> bool:
        """Recognize a vague continuation that Gemini resolved to Mihir's profile."""

        return (
            question_depends_on_conversation(question)
            and route.mode in {"grounded", "follow_up"}
            and (
                is_profile_overview_question(route.standalone_query)
                or "Mihir Lakhani profile" in route.topic_source_titles
            )
        )

    @staticmethod
    def _conversation_navigation_topic(
        question: str, retrieval_question: str, route: ConversationRoute
    ) -> str:
        """Return a minimal category for safe navigation of the next turn."""

        if (
            is_profile_overview_question(question)
            or retrieval_question == "Mihir Lakhani profile."
            or "Mihir Lakhani profile" in route.topic_source_titles
        ):
            return "profile"
        return "other"

    def _constrain_route(self, question: str, route: ConversationRoute) -> ConversationRoute:
        """Enforce disclosure and catalogue rules after Gemini routing."""

        if route.mode not in {"grounded", "follow_up"}:
            return route

        if route.retrieval_scope == "all_projects" and not is_complete_project_catalogue_request(
            question
        ):
            route = replace(route, retrieval_scope="relevant")
            trace_event("service.router_scope_clamped", reason="catalogue_not_explicit")

        if (
            route.standalone_query
            and not is_explicit_education_question(question)
            and is_explicit_education_question(route.standalone_query)
        ):
            # A routing rewrite may navigate the corpus, but it cannot make an
            # education disclosure implicit. For an ambiguous continuation,
            # keep the response on the approved public profile instead.
            fallback_query = (
                "Tell me more about Mihir Lakhani's public professional profile."
                if question_depends_on_conversation(question)
                or is_profile_overview_question(question)
                else question
            )
            route = replace(
                route,
                standalone_query=fallback_query,
                topic_source_titles=(),
            )
            trace_event("service.router_rewrite_clamped", reason="implicit_education")

        return route

    def _conversation_reply(
        self,
        question: str,
        suggested_reply: str,
        *,
        previous_interaction_id: str | None,
        store: bool,
    ) -> tuple[str, str | None]:
        if self._conversation_responder is None:
            return suggested_reply, None
        response = self._conversation_responder.reply(
            question,
            suggested_reply,
            previous_interaction_id=previous_interaction_id,
            store=store,
        )
        return response.reply, response.interaction_id

    def end_conversation(self, interaction_id: str) -> bool:
        """Delete one stored final-reply chain without exposing provider state to a visitor."""

        deleter = getattr(self._router, "delete_interaction", None)
        return bool(deleter(interaction_id)) if callable(deleter) else False

    def _sources_for_claim(
        self,
        claim: GeneratedClaim,
        file_citations: tuple[FileSearchCitation, ...],
        local_chunk_citations: tuple[LocalChunkCitation, ...],
        allowed_source_ids: frozenset[str] = frozenset(),
    ) -> tuple[Source, ...]:
        if claim.evidence_ids:
            sources = self._sources_for_local_claim(claim, local_chunk_citations)
        else:
            if claim.start_index is None or claim.end_index is None or claim.end_index <= claim.start_index:
                return ()

            sources: list[Source] = []
            seen_source_ids: set[str] = set()
            for citation in file_citations:
                if not self._citation_overlaps_claim(citation, claim):
                    continue
                source, reason = self._validate_citation(citation)
                trace_event(
                    "service.citation_checked",
                    overlap=True,
                    approved=source is not None,
                    reason=reason,
                )
                if source is not None and source.id not in seen_source_ids:
                    sources.append(source)
                    seen_source_ids.add(source.id)
            sources = tuple(sources)
        if allowed_source_ids and any(source.id not in allowed_source_ids for source in sources):
            trace_event("service.source_scope_rejected", approved=False)
            return ()
        return tuple(sources)

    def _sources_for_local_claim(
        self,
        claim: GeneratedClaim,
        local_chunk_citations: tuple[LocalChunkCitation, ...],
    ) -> tuple[Source, ...]:
        supplied = {
            citation.chunk_id: citation
            for citation in local_chunk_citations
        }
        sources: list[Source] = []
        seen_source_ids: set[str] = set()
        for chunk_id in claim.evidence_ids:
            diagram = self._approved_diagrams.get(chunk_id)
            if diagram is not None:
                source = self._registry.resolve(diagram.source_id)
                if source is None:
                    trace_event("service.local_diagram_checked", approved=False)
                    return ()
                if source.id not in seen_source_ids:
                    sources.append(source)
                    seen_source_ids.add(source.id)
                trace_event("service.local_diagram_checked", approved=True)
                continue
            expected = self._approved_local_chunks.get(chunk_id)
            citation = supplied.get(chunk_id)
            if expected is None or citation is None:
                trace_event("service.local_chunk_checked", approved=False, reason="unknown_chunk")
                return ()
            if citation != expected:
                trace_event("service.local_chunk_checked", approved=False, reason="chunk_hash_mismatch")
                return ()
            source = self._registry.resolve(expected.source_id)
            if source is None:
                trace_event("service.local_chunk_checked", approved=False, reason="unapproved_source")
                return ()
            if source.id not in seen_source_ids:
                sources.append(source)
                seen_source_ids.add(source.id)
            trace_event("service.local_chunk_checked", approved=True, reason="approved")
        return tuple(sources)

    @staticmethod
    def _citation_overlaps_claim(citation: FileSearchCitation, claim: GeneratedClaim) -> bool:
        if citation.start_index is None or citation.end_index is None:
            return False
        return citation.start_index < claim.end_index and citation.end_index > claim.start_index

    def _approved_source_for_citation(self, citation: FileSearchCitation) -> Source | None:
        source, _ = self._validate_citation(citation)
        return source

    def _validate_citation(self, citation: FileSearchCitation) -> tuple[Source | None, str]:
        source = self._registry.resolve(citation.source_id)
        if source is None:
            return None, "unapproved_source_id"
        expected = self._approved_documents.get(source.id)
        if expected is None:
            return None, "source_not_in_validated_store"
        if citation.content_sha256 != expected.sha256:
            return None, "content_hash_mismatch"
        # Gemini can return a store-scoped ``document_uri`` rather than the
        # per-document resource name. In that case the exact approved display
        # name remains the usable document identity. It is accepted only with
        # the already-checked source ID and content hash above.
        document_uri_matches = citation.document_name == expected.document_name
        file_name_matches = citation.file_name == expected.display_name
        if citation.file_name is not None and not file_name_matches:
            return None, "file_name_mismatch"
        if citation.document_name is not None and not document_uri_matches and not file_name_matches:
            return None, "document_uri_mismatch"
        if not document_uri_matches and not file_name_matches:
            return None, "missing_document_identity"
        return source, "approved"

    def _generation_refusal(
        self,
        generated: GeneratedAnswer | None = None,
        interaction_id: str | None = None,
    ) -> AssistantResult:
        return AssistantResult(
            answer=INSUFFICIENT_EVIDENCE_ANSWER,
            citations=(),
            grounded=False,
            mode="refuse",
            refusal_reason="invalid_generation_evidence",
            evidence_diagnostic=(
                self._evidence_diagnostic(generated) if generated is not None else None
            ),
            conversation_interaction_id=interaction_id,
        )

    def _approved_diagrams_for_answer(
        self, diagram_ids: tuple[str, ...], cited_source_ids: set[str]
    ) -> tuple[ApprovedDiagram, ...]:
        approved: list[ApprovedDiagram] = []
        for diagram_id in dict.fromkeys(diagram_ids):
            diagram = self._approved_diagrams.get(diagram_id)
            if diagram is None or diagram.source_id not in cited_source_ids:
                trace_event("service.diagram_checked", approved=False, diagram_requested=True)
                continue
            approved.append(diagram)
            trace_event("service.diagram_checked", approved=True, diagram_id=diagram.diagram_id)
        return tuple(approved)

    def _evidence_diagnostic(self, generated: GeneratedAnswer) -> dict[str, object]:
        """Summarize rejected provenance without retaining visitor or model text."""

        return {
            "claim_ranges": [
                {"start": claim.start_index, "end": claim.end_index}
                for claim in generated.claims
            ],
            "section_evidence_counts": [
                len(section.evidence_ids) for section in generated.sections
            ],
            "file_citations": [
                {
                    "source_id": citation.source_id,
                    "has_content_hash": citation.content_sha256 is not None,
                    "document_name": citation.document_name,
                    "file_name": citation.file_name,
                    "start": citation.start_index,
                    "end": citation.end_index,
                    "approved_identity": self._approved_source_for_citation(citation)
                    is not None,
                }
                for citation in generated.file_citations
            ],
            "local_chunk_citations": [
                {
                    "chunk_id": citation.chunk_id,
                    "source_id": citation.source_id,
                    "has_content_hash": bool(citation.content_sha256),
                    "approved_identity": self._approved_local_chunks.get(citation.chunk_id)
                    == citation,
                }
                for citation in generated.local_chunk_citations
            ],
        }


def create_gemini_service(project_root: Path) -> PortfolioAssistantService:
    """Construct the live service lazily so a missing SDK/key cannot break Flask startup."""

    settings = RagSettings.from_environment()
    settings.require_runtime_configuration()
    client: Any = create_gemini_client(settings)
    try:
        manifest_path = project_root / "knowledge" / "sources.json"
        registry = SourceRegistry.from_file(manifest_path)
        query_hints = ApprovedSourceQueryHints.from_registry(project_root / "knowledge", registry)
        sources = {source.id: source for source in registry.active_sources()}
        router = GeminiConversationRouter(
            client,
            settings,
            trusted_source_titles=tuple(source.title for source in registry.active_sources()),
        )
        responder = GeminiConversationResponder(client, settings)
        if settings.retrieval_mode == "local_hybrid":
            index_directory = Path(settings.local_index_directory)
            if not index_directory.is_absolute():
                index_directory = project_root / index_directory
            index = load_local_index(index_directory)
            validate_local_index(
                index,
                project_root / "knowledge",
                registry,
                settings.ollama_embedding_model,
            )
            embedder = OllamaEmbedder(
                settings.ollama_base_url,
                settings.ollama_embedding_model,
                timeout_seconds=settings.effective_provider_timeout_seconds,
            )
            trace_event(
                "service.local_index_loaded",
                retrieval_mode=settings.retrieval_mode,
                index_version=index.version,
                chunk_count=len(index.chunks),
                diagram_count=len(index.diagrams),
            )
            approved_chunks = {
                chunk.chunk_id: LocalChunkCitation(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    content_sha256=chunk.content_sha256,
                )
                for chunk in index.chunks
            }
            return PortfolioAssistantService(
                settings=settings,
                registry=registry,
                generator=GeminiLocalAnswerGenerator(
                    client,
                    settings,
                    LocalHybridRetriever(index, embedder, settings.local_top_k),
                    query_hints,
                    sources,
                ),
                approved_documents={},
                approved_local_chunks=approved_chunks,
                approved_diagrams={diagram.diagram_id: diagram for diagram in index.diagrams},
                source_selector=query_hints.source_ids_for_question,
                router=router,
                conversation_responder=responder,
                closer=getattr(client, "close", None),
            )
        plan = build_ingestion_plan(project_root / "knowledge", registry)
        approved_documents = approved_remote_documents(client, settings.file_search_store_id, plan)
        return PortfolioAssistantService(
            settings=settings,
            registry=registry,
            generator=GeminiFileSearchAnswerGenerator(
                GeminiFileSearchRetriever(client, settings), query_hints.for_question
            ),
            approved_documents=approved_documents,
            source_selector=query_hints.source_ids_for_question,
            router=router,
            conversation_responder=responder,
            closer=getattr(client, "close", None),
        )
    except Exception:
        closer = getattr(client, "close", None)
        if callable(closer):
            closer()
        raise
