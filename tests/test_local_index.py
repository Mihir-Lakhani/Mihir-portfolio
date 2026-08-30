import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from rag.config import RagConfigurationError
from rag.local_index import (
    build_local_index,
    load_local_index,
    validate_local_index,
    write_local_index,
)
from rag.sources import SourceRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeEmbedder:
    model = "test-nomic"

    def embed_texts(self, texts):
        return np.asarray(
            [
                [float(len(text)), float(text.casefold().count("docker")), float(text.casefold().count("5g"))]
                for text in texts
            ],
            dtype=np.float32,
        )


class LocalIndexTests(unittest.TestCase):
    def setUp(self):
        self.registry = SourceRegistry.from_file(PROJECT_ROOT / "knowledge" / "sources.json")

    def test_build_is_deterministic_and_indexes_only_active_manifest_sources(self):
        first = build_local_index(PROJECT_ROOT / "knowledge", self.registry, FakeEmbedder())
        second = build_local_index(PROJECT_ROOT / "knowledge", self.registry, FakeEmbedder())
        active_ids = {source.id for source in self.registry.active_sources()}

        self.assertTrue(first.chunks)
        self.assertEqual([chunk.chunk_id for chunk in first.chunks], [chunk.chunk_id for chunk in second.chunks])
        self.assertTrue(all(chunk.source_id in active_ids for chunk in first.chunks))
        self.assertTrue(all(chunk.content_sha256 == first.source_hashes[chunk.source_id] for chunk in first.chunks))
        self.assertTrue(any(diagram.source_id == "project-digital-twin-fleet" for diagram in first.diagrams))
        self.assertTrue(
            any(diagram.source_id == "project-source-cited-rag-assistant" for diagram in first.diagrams)
        )
        catalogue_sources = {
            chunk.source_id for chunk in first.chunks if chunk.kind == "project_catalogue"
        }
        expected_projects = {
            source.id for source in self.registry.active_sources() if source.source_type == "project"
        }
        self.assertEqual(catalogue_sources, expected_projects)

        legacy_document = PROJECT_ROOT / "knowledge" / "public" / "projects.md"
        self.assertTrue(legacy_document.is_file())
        self.assertNotIn(
            "public/projects.md",
            {source.path for source in self.registry.active_sources()},
        )
        self.assertNotIn(
            "review_bundle.md",
            {source.path for source in self.registry.active_sources()},
        )
        self.assertFalse(
            any(
                "IoT digital-twin platform for vehicle tracking and analytics" in chunk.text
                for chunk in first.chunks
            )
        )

    def test_persisted_index_validates_hashes_and_embedding_model(self):
        index = build_local_index(PROJECT_ROOT / "knowledge", self.registry, FakeEmbedder())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            write_local_index(index, target)
            loaded = load_local_index(target)
            validate_local_index(loaded, PROJECT_ROOT / "knowledge", self.registry, "test-nomic")
            with self.assertRaisesRegex(RagConfigurationError, "different embedding model"):
                validate_local_index(loaded, PROJECT_ROOT / "knowledge", self.registry, "other-model")
            stale = replace(loaded, source_hashes={"project-digital-twin-fleet": "wrong"})
            with self.assertRaisesRegex(RagConfigurationError, "does not match"):
                validate_local_index(stale, PROJECT_ROOT / "knowledge", self.registry, "test-nomic")

            vector_path = target / "vectors.npy"
            vector_path.write_bytes(b"not a valid vector matrix")
            with self.assertRaisesRegex(RagConfigurationError, "unreadable"):
                load_local_index(target)
