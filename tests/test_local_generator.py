import json
import unittest
from types import SimpleNamespace

from rag.config import RagSettings
from rag.local_generator import GeminiLocalAnswerGenerator
from rag.local_index import IndexedChunk, tokenize
from rag.local_retriever import RetrievedChunk
from rag.models import ApprovedDiagram, Source


def retrieved(chunk_id="chunk-fleet", source_id="project-digital-twin-fleet"):
    chunk = IndexedChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        content_sha256="fleet-hash",
        heading_path=("Technology stack",),
        text="Fleet uses Docker Compose for local service setup.",
        tokens=tokenize("Fleet uses Docker Compose for local service setup."),
    )
    return RetrievedChunk(chunk, lexical_score=1.0, dense_score=0.8, fusion_score=0.1)


class LocalGeneratorParsingTests(unittest.TestCase):
    def test_selected_chunk_evidence_is_preserved(self):
        item = retrieved()
        result = GeminiLocalAnswerGenerator._parse_answer(
            json.dumps(
                {
                    "answerable": True,
                    "claims": [
                        {
                            "text": "The Fleet project uses Docker Compose for local setup.",
                            "evidence_chunk_ids": [item.chunk.chunk_id],
                        }
                    ],
                    "diagram_ids": ["diagram-fleet"],
                }
            ),
            (item,),
            {item.chunk.chunk_id},
            [{"diagram_id": "diagram-fleet", "title": "Architecture", "source_title": "Fleet"}],
        )

        self.assertTrue(result.answerable)
        self.assertEqual(result.claims[0].evidence_ids, (item.chunk.chunk_id,))
        self.assertEqual(result.local_chunk_citations[0].source_id, item.chunk.source_id)
        self.assertEqual(result.requested_diagram_ids, ("diagram-fleet",))

    def test_unknown_chunk_or_diagram_is_not_accepted(self):
        item = retrieved()
        invalid_claim = GeminiLocalAnswerGenerator._parse_answer(
            '{"answerable":true,"claims":[{"text":"Unsupported","evidence_chunk_ids":["other"]}],"diagram_ids":[]}',
            (item,),
            {item.chunk.chunk_id},
            [],
        )
        valid_claim = GeminiLocalAnswerGenerator._parse_answer(
            '{"answerable":true,"claims":[{"text":"Supported","evidence_chunk_ids":["chunk-fleet"]}],"diagram_ids":["forged"]}',
            (item,),
            {item.chunk.chunk_id},
            [],
        )

        self.assertFalse(invalid_claim.answerable)
        self.assertTrue(valid_claim.answerable)
        self.assertEqual(valid_claim.requested_diagram_ids, ())

    def test_deep_dive_sections_preserve_independent_evidence(self):
        first = retrieved("chunk-overview")
        second = retrieved("chunk-architecture")
        result = GeminiLocalAnswerGenerator._parse_deep_dive_answer(
            json.dumps(
                {
                    "answerable": True,
                    "sections": [
                        {
                            "title": "Purpose",
                            "text": "The prototype explores vehicle twin records.",
                            "evidence_chunk_ids": [first.chunk.chunk_id],
                        },
                        {
                            "title": "Architecture",
                            "text": "The web path connects React, Flask, and storage.",
                            "evidence_chunk_ids": [second.chunk.chunk_id],
                        },
                    ],
                    "diagram_ids": [],
                }
            ),
            (first, second),
            {first.chunk.chunk_id, second.chunk.chunk_id},
            [],
        )

        self.assertTrue(result.answerable)
        self.assertEqual([section.title for section in result.sections], ["Purpose", "Architecture"])
        self.assertEqual(
            {citation.chunk_id for citation in result.local_chunk_citations},
            {"chunk-overview", "chunk-architecture"},
        )


class _FakeInteractions:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text, id="interaction-final")


class _FakeRetriever:
    def __init__(self, item, diagrams):
        self.items = item if isinstance(item, tuple) else (item,)
        self.index = SimpleNamespace(diagrams=diagrams)

    def retrieve(self, question, **options):
        return self.items

    def retrieve_deep_dive(self, source_ids):
        return self.items


class _FleetHints:
    def source_ids_for_question(self, question):
        return ("project-digital-twin-fleet",)


def generator_settings():
    return RagSettings(
        gemini_api_key="test-key",
        file_search_store_id="fileSearchStores/test-store",
        model="gemini-test",
        max_results=5,
        max_question_characters=500,
        max_answer_tokens=350,
        rate_limit_per_minute=20,
    )


class LocalGeneratorDiagramRegressionTests(unittest.TestCase):
    def setUp(self):
        self.item = retrieved()
        self.diagrams = (
            ApprovedDiagram(
                "diagram-architecture",
                "project-digital-twin-fleet",
                "fleet-hash",
                "End-to-end architecture",
                "flowchart LR\nA --> B",
            ),
            ApprovedDiagram(
                "diagram-browser",
                "project-digital-twin-fleet",
                "fleet-hash",
                "Browser-to-API twin-management flow",
                "sequenceDiagram\nA->>B: Request",
            ),
        )
        self.source = Source(
            id="project-digital-twin-fleet",
            path="projects/fleet.md",
            title="Fleet Smart Vehicle Digital Twin Prototype",
            url="https://example.test/fleet",
            source_type="project",
            project="fleet",
            public=True,
            enabled=True,
        )

    def _generator(self, output_text):
        client = SimpleNamespace(interactions=_FakeInteractions(output_text))
        return GeminiLocalAnswerGenerator(
            client,
            generator_settings(),
            _FakeRetriever(self.item, self.diagrams),
            _FleetHints(),
            {self.source.id: self.source},
        )

    def test_exact_mermaid_request_returns_approved_diagram_even_if_writer_refuses(self):
        generator = self._generator(
            '{"answerable":false,"claims":[],"diagram_ids":[]}'
        )

        result = generator.answer(
            "mermaid diagram for fleet",
            diagram_scope="single",
        )

        self.assertTrue(result.answerable)
        self.assertEqual(result.requested_diagram_ids, ("diagram-architecture",))
        self.assertIn("End-to-end architecture", result.claims[0].text)
        self.assertEqual(result.interaction_id, "interaction-final")

    def test_all_diagrams_returns_every_approved_diagram_for_named_project(self):
        generator = self._generator(
            '{"answerable":false,"claims":[],"diagram_ids":[]}'
        )

        result = generator.answer(
            "Give me all diagrams for Fleet",
            diagram_scope="all",
        )

        self.assertEqual(
            result.requested_diagram_ids,
            ("diagram-architecture", "diagram-browser"),
        )

    def test_deep_dive_uses_source_only_sections_when_structured_output_is_invalid(self):
        generator = self._generator(
            '{"answerable":false,"sections":[],"diagram_ids":[]}'
        )

        result = generator.answer(
            "Tell me everything about Fleet",
            response_profile="deep_dive",
        )

        self.assertTrue(result.answerable)
        self.assertFalse(result.claims)
        self.assertEqual(result.sections[0].title, "Technology stack")
        self.assertEqual(result.sections[0].evidence_ids, ("chunk-fleet",))
        self.assertEqual(result.local_chunk_citations[0].chunk_id, "chunk-fleet")

    def test_profile_deep_dive_restores_every_approved_profile_area(self):
        headings = (
            ("Current direction", "Mihir is building toward practical AI and MLOps work."),
            ("Research internship and network digital twins", "His research explored digital twins."),
            ("AI and machine-learning journey", "He learned decision-tree fundamentals directly."),
            ("Skills and recognition", "He uses Python and Flask and earned recognition."),
            ("Outside technical work", "He enjoys story-driven games in free time."),
        )
        profile_items = tuple(
            RetrievedChunk(
                IndexedChunk(
                    chunk_id=f"profile-{index}",
                    source_id="portfolio-background",
                    content_sha256="profile-hash",
                    heading_path=(heading,),
                    text=f"# {heading}\n\n{body}",
                    tokens=tokenize(body),
                ),
                lexical_score=1.0,
                dense_score=0.8,
                fusion_score=0.1,
            )
            for index, (heading, body) in enumerate(headings)
        )
        source = Source(
            id="portfolio-background",
            path="public/background.md",
            title="Mihir Lakhani profile",
            url="/#about",
            source_type="background",
            project="Portfolio",
            public=True,
            enabled=True,
        )
        client = SimpleNamespace(
            interactions=_FakeInteractions(
                json.dumps(
                    {
                        "answerable": True,
                        "sections": [
                            {
                                "title": "Current direction",
                                "text": headings[0][1],
                                "evidence_chunk_ids": ["profile-0"],
                            },
                            {
                                "title": "Research",
                                "text": headings[1][1],
                                "evidence_chunk_ids": ["profile-1"],
                            },
                            {
                                "title": "Skills",
                                "text": headings[3][1],
                                "evidence_chunk_ids": ["profile-3"],
                            },
                        ],
                        "diagram_ids": [],
                    }
                )
            )
        )
        generator = GeminiLocalAnswerGenerator(
            client,
            generator_settings(),
            _FakeRetriever(profile_items, ()),
            SimpleNamespace(source_ids_for_question=lambda question: ("portfolio-background",)),
            {source.id: source},
        )

        result = generator.answer("Mihir Lakhani profile.", response_profile="profile_deep_dive")

        self.assertEqual(len(result.sections), 5)
        self.assertEqual(
            {evidence_id for section in result.sections for evidence_id in section.evidence_ids},
            {f"profile-{index}" for index in range(5)},
        )
