import unittest

import numpy as np

from rag.local_index import IndexedChunk, LocalIndex, tokenize
from rag.local_retriever import LocalHybridRetriever


class FakeQueryEmbedder:
    def embed_texts(self, texts):
        vectors = []
        for text in texts:
            lowered = text.casefold()
            if "docker" in lowered or "react" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "network" in lowered or "telecom" in lowered or "5g" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return np.asarray(vectors, dtype=np.float32)


def chunk(chunk_id, source_id, text, kind="content"):
    return IndexedChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        content_sha256=f"hash-{source_id}",
        heading_path=("Overview",),
        text=text,
        tokens=tokenize(text),
        kind=kind,
    )


class LocalHybridRetrieverTests(unittest.TestCase):
    def setUp(self):
        self.chunks = (
            chunk("fleet-docker", "project-digital-twin-fleet", "Fleet uses Docker Compose and React."),
            chunk("five-g", "project-5g-handover", "5G mobility uses network KPI history."),
            chunk("closed-loop", "project-closed-loop-automation", "Network SLA analysis uses KPI snapshots."),
            chunk("fleet-catalogue", "project-digital-twin-fleet", "Fleet overview.", "project_catalogue"),
            chunk("five-g-catalogue", "project-5g-handover", "5G overview.", "project_catalogue"),
        )
        self.index = LocalIndex(
            version=1,
            embedding_model="test",
            source_hashes={
                "project-digital-twin-fleet": "hash-project-digital-twin-fleet",
                "project-5g-handover": "hash-project-5g-handover",
                "project-closed-loop-automation": "hash-project-closed-loop-automation",
            },
            chunks=self.chunks,
            vectors=np.asarray(
                [[1, 0, 0], [0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 1, 0]],
                dtype=np.float32,
            ),
            diagrams=(),
        )
        self.retriever = LocalHybridRetriever(self.index, FakeQueryEmbedder(), top_k=2)

    def test_hybrid_search_maps_docker_to_fleet(self):
        results = self.retriever.retrieve("Which project uses Docker?")

        self.assertEqual(results[0].chunk.source_id, "project-digital-twin-fleet")
        self.assertGreater(results[0].lexical_score, 0)

    def test_source_hints_boost_the_reviewed_networking_sources(self):
        results = self.retriever.retrieve(
            "Which project is related to networking?",
            source_ids=("project-5g-handover", "project-closed-loop-automation"),
        )

        self.assertTrue({item.chunk.source_id for item in results} <= {
            "project-5g-handover",
            "project-closed-loop-automation",
        })

    def test_catalogue_scope_returns_every_project_catalogue_chunk(self):
        results = self.retriever.retrieve("Tell me about all projects", scope="all_projects")

        self.assertEqual(
            {item.chunk.source_id for item in results},
            {"project-digital-twin-fleet", "project-5g-handover"},
        )

    def test_deep_dive_returns_named_source_chunks_in_document_order(self):
        results = self.retriever.retrieve_deep_dive(
            ("project-digital-twin-fleet",),
            max_chunks=5,
        )

        self.assertEqual([item.chunk.chunk_id for item in results], ["fleet-docker"])
        self.assertTrue(all(item.fusion_score == 1.0 for item in results))

    def test_deep_dive_without_a_named_source_fails_closed(self):
        self.assertEqual(self.retriever.retrieve_deep_dive(()), ())
