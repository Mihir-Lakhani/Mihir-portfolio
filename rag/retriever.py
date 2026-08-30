from __future__ import annotations

import time
from typing import Any

from .config import RagSettings
from .diagnostics import trace_event
from .gemini import configure_interaction_retry_budget


class GeminiFileSearchRetriever:
    """Runs a single Gemini interaction with File Search as its only tool."""

    def __init__(self, client: Any, settings: RagSettings):
        self._client = client
        self._settings = settings

    def generate(
        self,
        question: str,
        *,
        system_instruction: str,
        previous_interaction_id: str | None = None,
        store: bool = False,
    ) -> Any:
        # Configure this immediately before ``interactions`` is materialized.
        # The generated client reads retries differently from File Search
        # uploads; zero must mean no second provider attempt for a visitor.
        configure_interaction_retry_budget(
            self._client, self._settings.effective_provider_max_retries
        )
        trace_event(
            "retriever.interaction_started",
            model=self._settings.model,
            question_characters=len(question.strip()),
            top_k=self._settings.max_results,
            timeout_seconds=self._settings.effective_provider_timeout_seconds,
        )
        request_started = time.monotonic()
        try:
            request_kwargs: dict[str, Any] = {
                "model": self._settings.model,
                "input": question.strip(),
                "system_instruction": system_instruction,
                # File Search cannot be combined with Google Search or URL Context. The
                # exact store inventory is independently checked at service construction.
                "tools": [
                    {
                        "type": "file_search",
                        "file_search_store_names": [self._settings.file_search_store_id],
                        "metadata_filter": 'visibility="public"',
                        "top_k": self._settings.max_results,
                    }
                ],
                "generation_config": {"max_output_tokens": self._settings.max_answer_tokens},
                "store": store,
                "timeout": self._settings.effective_provider_timeout_seconds,
            }
            if previous_interaction_id is not None:
                request_kwargs["previous_interaction_id"] = previous_interaction_id
            interaction = self._client.interactions.create(**request_kwargs)
        except Exception as exc:
            trace_event(
                "retriever.interaction_failed",
                error_type=type(exc).__name__,
                status_code=getattr(exc, "status_code", getattr(exc, "code", None)),
                duration_ms=round((time.monotonic() - request_started) * 1000),
            )
            raise

        trace_event(
            "retriever.interaction_completed",
            step_count=len(getattr(interaction, "steps", ()) or ()),
            output_text_characters=len(getattr(interaction, "output_text", "") or ""),
            duration_ms=round((time.monotonic() - request_started) * 1000),
        )
        step_types = ",".join(
            str(getattr(step, "type", "unknown"))
            for step in (getattr(interaction, "steps", ()) or ())
        )
        trace_event("retriever.interaction_steps", step_types=step_types)
        return interaction
