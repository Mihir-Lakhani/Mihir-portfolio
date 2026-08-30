import unittest

from rag.config import RagSettings
from rag.gemini import configure_interaction_retry_budget, create_gemini_client


class GeminiClientTests(unittest.TestCase):
    def test_zero_retry_budget_disables_interaction_retries(self):
        settings = RagSettings(
            gemini_api_key="test-key",
            file_search_store_id="fileSearchStores/test-store",
            model="gemini-3.7-flash",
            max_results=5,
            max_question_characters=500,
            max_answer_tokens=350,
            rate_limit_per_minute=4,
            provider_max_retries=0,
        )

        client = create_gemini_client(settings)
        try:
            configure_interaction_retry_budget(client, 0)
            interaction_client = client.interactions
            self.assertEqual(
                interaction_client.sdk_configuration.retry_config.max_retries, 0
            )
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
