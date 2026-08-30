import tempfile
import unittest
from pathlib import Path

from rag.config import RagConfigurationError
from rag.ingestion import (
    GEMINI_CHUNKING_CONFIG,
    _safe_provider_diagnostic,
    approved_remote_documents,
    build_ingestion_plan,
    ingest_plan,
)
from rag.models import Source
from rag.sources import SourceRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Object:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeDocuments:
    def __init__(self):
        self.remote_documents = []
        self.kwargs = []

    def list(self, **kwargs):
        self.kwargs.append(kwargs)
        return list(self.remote_documents)


class FakeFileSearchStores:
    def __init__(self, fail_on_attempt=None):
        self.documents = FakeDocuments()
        self.uploads = []
        self.fail_on_attempt = fail_on_attempt

    def upload_to_file_search_store(self, **kwargs):
        self.uploads.append(kwargs)
        if self.fail_on_attempt == len(self.uploads):
            raise RuntimeError("simulated upload failure")
        source_metadata = {
            item["key"]: item["string_value"] for item in kwargs["config"]["custom_metadata"]
        }
        source_id = source_metadata["source_id"]
        self.documents.remote_documents.append(
            Object(
                name=f"fileSearchStores/test-store/documents/{source_id}",
                display_name=kwargs["config"]["display_name"],
                state="STATE_ACTIVE",
                custom_metadata=[
                    Object(key=key, string_value=value) for key, value in source_metadata.items()
                ],
            )
        )
        return Object(done=True, error=None)


class FakeClient:
    def __init__(self, fail_on_attempt=None):
        self.file_search_stores = FakeFileSearchStores(fail_on_attempt)
        self.operations = Object(get=lambda operation: operation)


class GeminiIngestionTests(unittest.TestCase):
    def setUp(self):
        self.knowledge_root = PROJECT_ROOT / "knowledge"
        self.registry = SourceRegistry.from_file(self.knowledge_root / "sources.json")
        self.plan = build_ingestion_plan(self.knowledge_root, self.registry)

    def test_ingestion_uploads_only_approved_sources_once_with_metadata_and_chunking(self):
        client = FakeClient()

        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "state.json"
            uploaded, skipped = ingest_plan(
                client, "fileSearchStores/test-store", self.plan, state_path
            )

            self.assertEqual(uploaded, len(self.plan))
            self.assertEqual(skipped, 0)
            self.assertEqual(len(client.file_search_stores.uploads), len(self.plan))
            config = client.file_search_stores.uploads[0]["config"]
            self.assertEqual(config["chunking_config"], GEMINI_CHUNKING_CONFIG)
            self.assertLessEqual(
                config["chunking_config"]["white_space_config"]["max_tokens_per_chunk"], 512
            )
            metadata = {item["key"]: item["string_value"] for item in config["custom_metadata"]}
            self.assertEqual(metadata["visibility"], "public")
            self.assertEqual(metadata["manifest_public"], "true")
            self.assertEqual(metadata["content_sha256"], self.plan[0].sha256)

            uploaded_again, skipped_again = ingest_plan(
                client, "fileSearchStores/test-store", self.plan, state_path
            )
            self.assertEqual(uploaded_again, 0)
            self.assertEqual(skipped_again, len(self.plan))

    def test_uncertain_failure_blocks_a_blind_retry(self):
        client = FakeClient(fail_on_attempt=2)

        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "state.json"
            with self.assertRaises(RagConfigurationError):
                ingest_plan(client, "fileSearchStores/test-store", self.plan, state_path)
            self.assertTrue(state_path.is_file())

            client.file_search_stores.fail_on_attempt = None
            with self.assertRaises(RagConfigurationError):
                ingest_plan(client, "fileSearchStores/test-store", self.plan, state_path)
            self.assertEqual(len(client.file_search_stores.uploads), 2)

    def test_remote_inventory_must_exactly_match_current_approved_plan(self):
        client = FakeClient()

        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "state.json"
            ingest_plan(client, "fileSearchStores/test-store", self.plan, state_path)
            approved = approved_remote_documents(
                client, "fileSearchStores/test-store", self.plan
            )
            self.assertEqual(len(approved), len(self.plan))

            client.file_search_stores.documents.remote_documents.append(
                Object(
                    name="fileSearchStores/test-store/documents/unapproved",
                    state="STATE_ACTIVE",
                    custom_metadata=[
                        Object(key="source_id", string_value="unapproved"),
                        Object(key="content_sha256", string_value="x"),
                        Object(key="visibility", string_value="public"),
                        Object(key="manifest_public", string_value="true"),
                        Object(key="manifest_enabled", string_value="true"),
                    ],
                )
            )
            with self.assertRaises(RagConfigurationError):
                approved_remote_documents(client, "fileSearchStores/test-store", self.plan)

    def test_pending_document_blocks_a_resume(self):
        client = FakeClient()
        first_item = self.plan[0]
        client.file_search_stores.documents.remote_documents.append(
            Object(
                name="fileSearchStores/test-store/documents/pending",
                state="STATE_PENDING",
                custom_metadata=[
                    Object(key="source_id", string_value=first_item.source.id),
                    Object(key="content_sha256", string_value=first_item.sha256),
                ],
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(RagConfigurationError):
                ingest_plan(
                    client,
                    "fileSearchStores/test-store",
                    self.plan,
                    Path(temporary_directory) / "state.json",
                )

    def test_plan_excludes_private_or_disabled_sources_before_any_upload(self):
        public_source = Source(
            id="approved",
            path="public.md",
            title="Approved",
            url="/#about",
            source_type="portfolio",
            project="Portfolio",
            public=True,
            enabled=True,
        )
        private_source = Source(
            id="private",
            path="private.md",
            title="Private",
            url="/#about",
            source_type="private",
            project="Private",
            public=False,
            enabled=True,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "public.md").write_text("Approved public text", encoding="utf-8")
            (root / "private.md").write_text("Never upload this", encoding="utf-8")
            plan = build_ingestion_plan(root, SourceRegistry((public_source, private_source)))

        self.assertEqual([item.source.id for item in plan], ["approved"])

    def test_local_debug_diagnostic_redacts_api_keys(self):
        diagnostic = _safe_provider_diagnostic(
            RuntimeError("request key=AIza012345678901234567890123456789 failed")
        )

        self.assertIn("RuntimeError", diagnostic)
        self.assertNotIn("AIza012345678901234567890123456789", diagnostic)
        self.assertIn("[redacted]", diagnostic)


if __name__ == "__main__":
    unittest.main()
