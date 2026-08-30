import json
import unittest
from unittest.mock import patch

import numpy as np

from rag.ollama import OllamaEmbedder


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class OllamaEmbedderTests(unittest.TestCase):
    def test_batches_large_embedding_requests_without_reordering_vectors(self):
        request_inputs = []

        def urlopen(request, timeout):
            payload = json.loads(request.data.decode("utf-8"))
            request_inputs.append(payload["input"])
            return FakeResponse(
                {"embeddings": [[float(len(text)), 1.0] for text in payload["input"]]}
            )

        with patch("rag.ollama.urlopen", side_effect=urlopen):
            vectors = OllamaEmbedder("http://localhost:11434", "nomic-embed-text").embed_texts(
                ["one", "two", "three", "four", "five"]
            )

        self.assertEqual(request_inputs, [["one", "two", "three", "four"], ["five"]])
        np.testing.assert_array_equal(
            vectors,
            np.asarray([[3.0, 1.0], [3.0, 1.0], [5.0, 1.0], [4.0, 1.0], [4.0, 1.0]], dtype=np.float32),
        )
