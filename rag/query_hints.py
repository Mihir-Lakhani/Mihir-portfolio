from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .diagnostics import trace_event
from .models import Source
from .sources import SourceRegistry


_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9+.#-]*", re.IGNORECASE)
_PRIVATE_REQUEST_TERMS = frozenset(
    {
        "address",
        "birthday",
        "email",
        "gmail",
        "home",
        "mobile",
        "number",
        "phone",
        "private",
        "residence",
        "telephone",
        "whatsapp",
    }
)

# These words describe the shape of a visitor's question rather than a useful
# retrieval target. The remaining terms are matched only against approved local
# source files, then used as navigation hints for Gemini File Search.
_QUESTION_STOP_WORDS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "are",
        "as",
        "at",
        "can",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "mihir",
        "more",
        "of",
        "on",
        "or",
        "portfolio",
        "project",
        "projects",
        "related",
        "relate",
        "tell",
        "tech",
        "technology",
        "the",
        "this",
        "to",
        "tool",
        "tools",
        "use",
        "used",
        "uses",
        "using",
        "what",
        "which",
        "with",
        "you",
    }
)


def _normalized_terms(text: str) -> tuple[str, ...]:
    return tuple(
        normalized
        for token in _TOKEN_PATTERN.findall(text.casefold().replace("_", " ").replace("-", " "))
        for normalized in (token.strip(".,!?;:\"'()[]{}"),)
        if normalized
    )


def _search_terms(text: str) -> frozenset[str]:
    return frozenset(
        term
        for term in _normalized_terms(text)
        if len(term) >= 3 and term not in _QUESTION_STOP_WORDS
    )


@dataclass(frozen=True)
class _TaxonomyConcept:
    identifier: str
    aliases: tuple[str, ...]
    source_ids: tuple[str, ...]
    kind: str


class ApprovedSourceQueryHints:
    """Guide File Search with reviewed portfolio concepts, never source text.

    The taxonomy improves precision for known technologies, project names, and
    aliases. A term not represented in the taxonomy intentionally produces no
    source hint, allowing File Search to search every approved document from the
    visitor's original question instead of being pushed toward a coincidental
    word-frequency match.
    """

    def __init__(self, concepts: tuple[_TaxonomyConcept, ...], sources: dict[str, Source]):
        self._concepts = concepts
        self._sources = sources

    @classmethod
    def from_registry(cls, knowledge_root: Path, registry: SourceRegistry) -> "ApprovedSourceQueryHints":
        sources = {source.id: source for source in registry.active_sources()}
        taxonomy_path = knowledge_root / "portfolio_taxonomy.json"
        try:
            payload = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError(f"Could not read portfolio taxonomy: {taxonomy_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError("Portfolio taxonomy is not valid JSON") from exc

        raw_concepts = payload.get("concepts") if isinstance(payload, dict) else None
        if not isinstance(raw_concepts, list) or not raw_concepts:
            raise ValueError("Portfolio taxonomy must declare at least one concept")

        concepts: list[_TaxonomyConcept] = []
        seen_identifiers: set[str] = set()
        for raw_concept in raw_concepts:
            if not isinstance(raw_concept, dict):
                raise ValueError("Portfolio taxonomy concepts must be objects")
            identifier = raw_concept.get("id")
            raw_aliases = raw_concept.get("aliases")
            raw_source_ids = raw_concept.get("source_ids")
            kind = raw_concept.get("kind", "capability")
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen_identifiers:
                raise ValueError("Portfolio taxonomy concept IDs must be unique non-empty strings")
            if kind not in {"project", "capability"}:
                raise ValueError("Portfolio taxonomy concept kind must be project or capability")
            if not isinstance(raw_aliases, list) or not isinstance(raw_source_ids, list):
                raise ValueError("Portfolio taxonomy concepts require aliases and source_ids lists")

            aliases = tuple(
                dict.fromkeys(
                    normalized
                    for raw_alias in raw_aliases
                    if isinstance(raw_alias, str)
                    for normalized in (" ".join(_normalized_terms(raw_alias)),)
                    if normalized
                )
            )
            source_ids = tuple(
                dict.fromkeys(source_id for source_id in raw_source_ids if isinstance(source_id, str))
            )
            if not aliases or not source_ids or any(source_id not in sources for source_id in source_ids):
                raise ValueError(f"Portfolio taxonomy concept {identifier!r} has invalid aliases or source IDs")
            seen_identifiers.add(identifier)
            concepts.append(
                _TaxonomyConcept(
                    identifier=identifier,
                    aliases=aliases,
                    source_ids=source_ids,
                    kind=kind,
                )
            )
        return cls(tuple(concepts), sources)

    @staticmethod
    def _matching_aliases(question: str, concept: _TaxonomyConcept) -> tuple[str, ...]:
        normalized_question = " ".join(_normalized_terms(question))
        padded_question = f" {normalized_question} "
        exact_aliases = tuple(
            alias for alias in concept.aliases if f" {alias} " in padded_question
        )
        if exact_aliases:
            return exact_aliases

        # A one-character typo in a distinctive reviewed technology or
        # project alias can guide ranking without becoming a spelling map.
        question_terms = set(_normalized_terms(question))
        return tuple(
            alias
            for alias in concept.aliases
            if " " not in alias
            and len(alias) >= 5
            and any(
                abs(len(term) - len(alias)) <= 1
                and SequenceMatcher(a=term, b=alias).ratio() >= 0.84
                for term in question_terms
            )
        )

    def for_question(self, question: str) -> tuple[str, ...]:
        selected_source_ids, source_terms = self._selected_source_ids(question)
        return tuple(
            "Potentially relevant approved source: "
            f"{self._sources[source_id].title} (matched reviewed portfolio concepts: "
            f"{', '.join(dict.fromkeys(source_terms[source_id]))})."
            for source_id in selected_source_ids
        )

    def source_ids_for_question(self, question: str) -> tuple[str, ...]:
        """Return reviewed source navigation IDs for local retrieval only."""

        selected_source_ids, _ = self._selected_source_ids(question)
        return selected_source_ids

    def _selected_source_ids(self, question: str) -> tuple[tuple[str, ...], dict[str, list[str]]]:
        question_terms = _search_terms(question)
        # Sensitive personal requests should never receive document-navigation
        # hints, even if an incidental common word appears in an approved source.
        if question_terms & _PRIVATE_REQUEST_TERMS:
            trace_event("query_hints.suppressed_sensitive_terms")
            return (), {}

        matches: list[tuple[_TaxonomyConcept, tuple[str, ...]]] = []
        for concept in self._concepts:
            aliases = self._matching_aliases(question, concept)
            if aliases:
                matches.append((concept, aliases))

        # A reviewed alias such as "Mihir" can be intentionally omitted from
        # lexical retrieval terms while still being the safest source selector.
        # Only return early when neither ordinary terms nor approved aliases
        # identify a portfolio topic.
        if not question_terms and not matches:
            trace_event("query_hints.selected", query_term_count=0, hint_count=0)
            return (), {}

        # "Mihir" is an intentional profile anchor, but it should not widen
        # an otherwise precise request such as "Mihir's CGPA" or "Mihir's
        # skills" into the general profile source. A reviewed, more specific
        # topic owns the source scope in that case.
        if any(concept.identifier != "mihir-profile" for concept, _ in matches):
            matches = [
                match for match in matches if match[0].identifier != "mihir-profile"
            ]

        # A named project is normally the strongest navigation signal. A longer,
        # more specific reviewed non-project phrase is allowed to win when it
        # identifies a different subject, such as the Network Digital Twin
        # research internship versus the Fleet Digital Twin project.
        project_matches = [match for match in matches if match[0].kind == "project"]
        if project_matches:
            longest_project_alias = max(
                len(alias.split())
                for _, aliases in project_matches
                for alias in aliases
            )
            stronger_non_project_matches = [
                match
                for match in matches
                if match[0].kind != "project"
                and max(len(alias.split()) for alias in match[1]) > longest_project_alias
            ]
            matches = stronger_non_project_matches or project_matches

        matches.sort(
            key=lambda item: (
                -max(len(alias.split()) for alias in item[1]),
                item[0].identifier,
            )
        )
        source_terms: dict[str, list[str]] = {}
        for concept, _ in matches:
            for source_id in concept.source_ids:
                source_terms.setdefault(source_id, []).append(concept.identifier)

        selected_source_ids = tuple(source_terms)[:3]
        trace_event(
            "query_hints.selected",
            query_term_count=len(question_terms),
            matched_concept_count=len(matches),
            hint_count=len(selected_source_ids),
            source_titles=" | ".join(self._sources[source_id].title for source_id in selected_source_ids),
            approved_terms=",".join(sorted({concept.identifier for concept, _ in matches})),
        )
        return selected_source_ids, source_terms
