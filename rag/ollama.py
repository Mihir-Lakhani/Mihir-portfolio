from __future__ import annotations

import json
import time
from collections.abc import Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

from .config import RagConfigurationError
from .diagnostics import trace_event


_MAX_EMBED_BATCH_SIZE = 4


class OllamaEmbeddingError(RagConfigurationError):
    """Raised when the local embedding service cannot produce usable vectors."""


class OllamaEmbedder:
    """Small stdlib client for Ollama's local embedding endpoint."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        matrices = [
            self._embed_batch(texts[start : start + _MAX_EMBED_BATCH_SIZE])
            for start in range(0, len(texts), _MAX_EMBED_BATCH_SIZE)
        ]
        matrix = np.vstack(matrices)
        if matrix.ndim != 2 or matrix.shape[0] != len(texts) or matrix.shape[1] == 0:
            raise OllamaEmbeddingError("The local embedding service returned invalid embeddings.")
        if not np.isfinite(matrix).all():
            raise OllamaEmbeddingError("The local embedding service returned invalid embeddings.")
        return matrix

    def _embed_batch(self, texts: Sequence[str]) -> np.ndarray:
        payload = json.dumps({"model": self._model, "input": list(texts)}).encode("utf-8")
        request = Request(
            f"{self._base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw_body = response.read()
        except HTTPError as exc:
            trace_event(
                "ollama.embed_failed",
                error_type=type(exc).__name__,
                status_code=exc.code,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            raise OllamaEmbeddingError("The local embedding service is unavailable.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            trace_event(
                "ollama.embed_failed",
                error_type=type(exc).__name__,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            raise OllamaEmbeddingError("The local embedding service is unavailable.") from exc

        try:
            decoded: Any = json.loads(raw_body.decode("utf-8"))
            embeddings = decoded.get("embeddings") if isinstance(decoded, dict) else None
            matrix = np.asarray(embeddings, dtype=np.float32)
        except (UnicodeDecodeError, ValueError, TypeError) as exc:
            trace_event("ollama.embed_failed", error_type="invalid_response")
            raise OllamaEmbeddingError("The local embedding service returned an invalid response.") from exc

        if matrix.ndim != 2 or matrix.shape[0] != len(texts) or matrix.shape[1] == 0:
            raise OllamaEmbeddingError("The local embedding service returned invalid embeddings.")
        if not np.isfinite(matrix).all():
            raise OllamaEmbeddingError("The local embedding service returned invalid embeddings.")
        trace_event(
            "ollama.embed_batch_completed",
            text_count=len(texts),
            dimensions=int(matrix.shape[1]),
            duration_ms=round((time.monotonic() - started) * 1000),
        )
        return matrix
