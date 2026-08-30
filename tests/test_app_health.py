import os
import unittest
from unittest.mock import patch

import app as portfolio_app


class PortfolioHealthTests(unittest.TestCase):
    def test_healthz_reports_ready_for_a_configured_file_search_adapter(self):
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "test-key",
                "RAG_RETRIEVAL_MODE": "gemini_file_search",
                "RAG_GEMINI_FILE_SEARCH_STORE_ID": "fileSearchStores/test-store",
            },
            clear=True,
        ):
            response = portfolio_app.app.test_client().get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "ok", "retrieval_mode": "gemini_file_search"},
        )

    def test_healthz_hides_missing_configuration_details(self):
        with patch.dict(
            os.environ,
            {"RAG_RETRIEVAL_MODE": "local_hybrid"},
            clear=True,
        ):
            response = portfolio_app.app.test_client().get("/healthz")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"status": "unready"})


if __name__ == "__main__":
    unittest.main()
