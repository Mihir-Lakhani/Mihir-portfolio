import unittest

from rag.config import RagSettings
from rag.diagnostics import capture_rag_trace
from rag.retriever import GeminiFileSearchRetriever


class Object:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeInteractions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return Object(output_text="{}", steps=[])


class FakeClient:
    def __init__(self):
        self.interactions = FakeInteractions()


def settings() -> RagSettings:
    return RagSettings(
        gemini_api_key="test-key",
        file_search_store_id="fileSearchStores/test-store",
        model="gemini-test",
        max_results=5,
        max_question_characters=500,
        max_answer_tokens=350,
        rate_limit_per_minute=20,
    )


class GeminiFileSearchRetrieverTests(unittest.TestCase):
    def test_interaction_uses_only_public_file_search_with_bounded_output(self):
        client = FakeClient()

        GeminiFileSearchRetriever(client, settings()).generate(
            "What framework is used?",
            system_instruction="Use only the store.",
        )

        request = client.interactions.kwargs
        self.assertEqual(request["model"], "gemini-test")
        self.assertEqual(request["input"], "What framework is used?")
        self.assertEqual(request["tools"], [
            {
                "type": "file_search",
                "file_search_store_names": ["fileSearchStores/test-store"],
                "metadata_filter": 'visibility="public"',
                "top_k": 5,
            }
        ])
        self.assertNotIn("google_search", str(request["tools"]))
        self.assertNotIn("url_context", str(request["tools"]))
        self.assertEqual(request["generation_config"], {"max_output_tokens": 350})
        self.assertNotIn("response_format", request)
        self.assertFalse(request["store"])
        self.assertEqual(request["timeout"], 60.0)

    def test_trace_includes_duration_without_retaining_question_text(self):
        client = FakeClient()
        with capture_rag_trace() as trace:
            GeminiFileSearchRetriever(client, settings()).generate(
                "Which project uses Docker?",
                system_instruction="Use only the store.",
            )

        completed = next(
            item for item in trace.events if item["event"] == "retriever.interaction_completed"
        )
        self.assertIn("duration_ms", completed)
        self.assertNotIn("Which project", str(trace.to_dict()))


if __name__ == "__main__":
    unittest.main()
