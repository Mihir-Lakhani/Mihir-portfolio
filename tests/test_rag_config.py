import os
import unittest
from unittest.mock import patch

from rag.config import RagConfigurationError, RagSettings


class RagSettingsTests(unittest.TestCase):
    def test_missing_gemini_key_and_store_id_are_reported_to_server_code(self):
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "",
                "RAG_GEMINI_FILE_SEARCH_STORE_ID": "",
                "RAG_RETRIEVAL_MODE": "gemini_file_search",
            },
            clear=False,
        ):
            settings = RagSettings.from_environment()
            with self.assertRaisesRegex(
                RagConfigurationError,
                "GEMINI_API_KEY.*RAG_GEMINI_FILE_SEARCH_STORE_ID",
            ):
                settings.require_runtime_configuration()

    def test_gemini_environment_names_and_defaults_are_used(self):
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "RAG_GEMINI_FILE_SEARCH_STORE_ID": "fileSearchStores/test-store",
                "RAG_GEMINI_MODEL": "test-model",
                "RAG_MAX_RESULTS": "4",
                "RAG_GEMINI_TIMEOUT_SECONDS": "12",
                "RAG_GEMINI_MAX_RETRIES": "2",
                "RAG_MAX_CONVERSATION_TURNS": "5",
                "RAG_MAX_CONVERSATION_CHARACTERS": "1800",
                "RAG_STATEFUL_CONVERSATIONS": "false",
                "RAG_CONVERSATION_SESSION_TTL_SECONDS": "600",
                "RAG_ENABLE_RATE_LIMITS": "true",
            },
            clear=False,
        ):
            settings = RagSettings.from_environment()

        self.assertEqual(settings.gemini_api_key, "test-key")
        self.assertEqual(settings.file_search_store_id, "fileSearchStores/test-store")
        self.assertEqual(settings.model, "test-model")
        self.assertEqual(settings.max_results, 4)
        self.assertEqual(settings.provider_timeout_seconds, 12.0)
        self.assertEqual(settings.provider_max_retries, 2)
        self.assertEqual(settings.effective_provider_timeout_seconds, 60.0)
        self.assertEqual(settings.effective_provider_max_retries, 2)
        self.assertEqual(settings.max_conversation_turns, 5)
        self.assertEqual(settings.max_conversation_characters, 1800)
        self.assertFalse(settings.stateful_conversations)
        self.assertEqual(settings.conversation_session_ttl_seconds, 600)
        self.assertTrue(settings.rate_limits_enabled)

    def test_default_model_is_the_free_tier_flash_lite_option(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = RagSettings.from_environment()

        self.assertEqual(settings.model, "gemini-3.5-flash-lite")
        self.assertTrue(settings.stateful_conversations)

    def test_local_hybrid_is_the_default_and_does_not_require_a_file_search_store(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            settings = RagSettings.from_environment()

        self.assertEqual(settings.retrieval_mode, "local_hybrid")
        settings.require_runtime_configuration()

    def test_production_enables_local_limits_unless_explicitly_overridden(self):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key", "RAG_ENV": "production"},
            clear=True,
        ):
            production = RagSettings.from_environment()
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "RAG_ENV": "production",
                "RAG_ENABLE_RATE_LIMITS": "false",
            },
            clear=True,
        ):
            overridden = RagSettings.from_environment()

        self.assertTrue(production.rate_limits_enabled)
        self.assertEqual(production.effective_rate_limit_per_minute, 12)
        self.assertEqual(production.effective_global_rate_limit_per_minute, 60)
        self.assertFalse(overridden.rate_limits_enabled)

    def test_file_search_uses_a_safe_timeout_and_retry_floor(self):
        settings = RagSettings(
            gemini_api_key="test-key",
            file_search_store_id="fileSearchStores/test-store",
            model="test-model",
            max_results=5,
            max_question_characters=500,
            max_answer_tokens=350,
            rate_limit_per_minute=20,
            provider_timeout_seconds=20,
            provider_max_retries=0,
        )

        self.assertEqual(settings.effective_provider_timeout_seconds, 60.0)
        self.assertEqual(settings.effective_provider_max_retries, 0)
        self.assertEqual(settings.effective_rate_limit_per_minute, 0)
        self.assertEqual(settings.effective_global_rate_limit_per_minute, 0)

    def test_explicit_rate_limits_are_not_clamped(self):
        settings = RagSettings(
            gemini_api_key="test-key",
            file_search_store_id="fileSearchStores/test-store",
            model="test-model",
            max_results=5,
            max_question_characters=500,
            max_answer_tokens=350,
            rate_limit_per_minute=25,
            global_rate_limit_per_minute=100,
            rate_limits_enabled=True,
        )

        self.assertEqual(settings.effective_rate_limit_per_minute, 25)
        self.assertEqual(settings.effective_global_rate_limit_per_minute, 100)

    def test_admin_client_only_requires_the_api_key_before_store_creation(self):
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "RAG_GEMINI_FILE_SEARCH_STORE_ID": "",
                "RAG_RETRIEVAL_MODE": "gemini_file_search",
            },
            clear=False,
        ):
            settings = RagSettings.from_environment()

        settings.require_api_key()
        with self.assertRaises(RagConfigurationError):
            settings.require_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
