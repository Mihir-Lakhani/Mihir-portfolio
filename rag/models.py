from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """An approved public document described by the local source manifest."""

    id: str
    path: str
    title: str
    url: str
    source_type: str
    project: str
    public: bool
    enabled: bool
    demo_url: str | None = None
    demo_label: str | None = None


@dataclass(frozen=True)
class FileSearchCitation:
    """A Gemini File Search citation returned with generated text."""

    source_id: str | None
    content_sha256: str | None
    document_name: str | None
    start_index: int | None
    end_index: int | None
    file_name: str | None = None


@dataclass(frozen=True)
class LocalChunkCitation:
    """Approved local-index evidence attached to a generated claim."""

    chunk_id: str
    source_id: str
    content_sha256: str


@dataclass(frozen=True)
class ApprovedDiagram:
    """A Mermaid diagram extracted from an approved public source file."""

    diagram_id: str
    source_id: str
    content_sha256: str
    title: str
    mermaid: str


@dataclass(frozen=True)
class GeneratedClaim:
    """One concise model-written claim and its byte range in the JSON response."""

    text: str
    start_index: int | None
    end_index: int | None
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratedSection:
    """One model-written deep-dive section with explicit approved evidence."""

    title: str
    text: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedAnswer:
    """A structured model response validated before anything reaches the browser."""

    answerable: bool
    claims: tuple[GeneratedClaim, ...]
    output_text: str = ""
    file_citations: tuple[FileSearchCitation, ...] = ()
    local_chunk_citations: tuple[LocalChunkCitation, ...] = ()
    interaction_id: str | None = None
    diagram_id: str | None = None
    sections: tuple[GeneratedSection, ...] = ()
    diagram_ids: tuple[str, ...] = ()

    @property
    def requested_diagram_ids(self) -> tuple[str, ...]:
        """Return deduplicated diagram IDs while retaining legacy adapter support."""

        return tuple(
            dict.fromkeys(
                diagram_id
                for diagram_id in (*self.diagram_ids, self.diagram_id)
                if isinstance(diagram_id, str) and diagram_id
            )
        )


@dataclass(frozen=True)
class ConversationTurn:
    """A bounded, browser-provided turn used only to resolve conversation context."""

    role: str
    text: str
    grounded: bool


@dataclass(frozen=True)
class ConversationRoute:
    """A structured decision from Gemini before a visitor answer is generated."""

    mode: str
    standalone_query: str = ""
    reply: str = ""
    # These fields are server-only routing diagnostics. They never reach the
    # browser and cannot create citations or authorize a source.
    reason: str = ""
    topic_source_titles: tuple[str, ...] = ()
    retrieval_scope: str = "relevant"
    # Gemini's opaque interaction ID is server-only state. It is never sent to
    # the browser or written into the local diagnostic trace.
    interaction_id: str | None = None


@dataclass(frozen=True)
class Citation:
    """A citation returned to the browser from a trusted local source registry."""

    source_id: str
    title: str
    url: str
    source_type: str
    project: str
    demo_url: str | None = None
    demo_label: str | None = None

    @classmethod
    def from_source(cls, source: Source) -> "Citation":
        return cls(
            source_id=source.id,
            title=source.title,
            url=source.url,
            source_type=source.source_type,
            project=source.project,
            demo_url=source.demo_url,
            demo_label=source.demo_label,
        )

    def to_dict(self) -> dict[str, str]:
        citation = {
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "project": self.project,
        }
        if self.demo_url and self.demo_label:
            citation["demo_url"] = self.demo_url
            citation["demo_label"] = self.demo_label
        return citation


@dataclass(frozen=True)
class AnswerSection:
    """A validated deep-dive section safe to serialize to the browser."""

    title: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "text": self.text}


@dataclass(frozen=True)
class AssistantResult:
    answer: str
    citations: tuple[Citation, ...]
    grounded: bool
    mode: str = "grounded"
    refusal_reason: str | None = None
    # Local-only, approved-source provenance diagnostic. ``to_dict`` never
    # serializes this to a visitor.
    evidence_diagnostic: dict[str, object] | None = None
    # The stateful router's opaque interaction ID, consumed only by the Flask
    # session store after a successful response.
    conversation_interaction_id: str | None = None
    # A short, non-text navigation category retained only for the active
    # browser session. It never reaches the browser or diagnostic payloads.
    conversation_navigation_topic: str | None = None
    diagram: ApprovedDiagram | None = None
    sections: tuple[AnswerSection, ...] = ()
    diagrams: tuple[ApprovedDiagram, ...] = ()

    def to_dict(self) -> dict[str, object]:
        response: dict[str, object] = {
            "answer": self.answer,
            "citations": [citation.to_dict() for citation in self.citations],
            "grounded": self.grounded,
            "mode": self.mode,
            "refusal_reason": self.refusal_reason,
        }
        if self.diagram is not None:
            approved_diagrams = (self.diagram, *self.diagrams)
        else:
            approved_diagrams = self.diagrams
        approved_diagrams = tuple(
            {diagram.diagram_id: diagram for diagram in approved_diagrams}.values()
        )
        if self.sections:
            response["sections"] = [section.to_dict() for section in self.sections]
        if approved_diagrams:
            serialized_diagrams = [
                {"title": diagram.title, "mermaid": diagram.mermaid}
                for diagram in approved_diagrams
            ]
            # Keep the singular field for existing clients while new clients can
            # render the complete approved diagram collection.
            response["diagram"] = serialized_diagrams[0]
            response["diagrams"] = serialized_diagrams
        return response
