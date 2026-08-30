from __future__ import annotations

from typing import Any

from .config import RagConfigurationError, RagSettings
from .diagnostics import trace_event


def create_gemini_client(settings: RagSettings) -> Any:
    """Build one server-side Gemini client with bounded request behaviour."""

    # Ingestion can create a store before a store ID exists. Serving code calls
    # ``require_runtime_configuration`` separately before it reaches this helper.
    settings.require_api_key()
    try:
        from google import genai
    except ImportError as exc:
        raise RagConfigurationError(
            "The Google Gen AI Python package is not installed. Install requirements.txt first."
        ) from exc

    # File Search can take longer than a text-only request. Keep its timeout
    # floor, but do not retry quota responses unless an operator opts in. The
    # legacy File Search APIs count the original request in ``attempts``;
    # Interactions is configured separately below because it does not.
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options={
            "api_version": "v1beta",
            "timeout": int(settings.effective_provider_timeout_seconds * 1000),
            "retry_options": {
                "attempts": settings.effective_provider_max_retries + 1,
                "initial_delay": 1,
                "max_delay": 4,
                "exp_base": 2,
                "jitter": 0.1,
            },
        },
    )
    trace_event(
        "gemini.client_created",
        model=settings.model,
        timeout_seconds=settings.effective_provider_timeout_seconds,
        additional_retries=settings.effective_provider_max_retries,
    )
    return client


def configure_interaction_retry_budget(client: Any, additional_retries: int) -> None:
    """Apply Interactions' retry semantics without changing File Search uploads.

    The SDK's generated Interactions client treats ``attempts`` as the number
    of retries, while the older File Search client treats it as the total
    number of attempts. Assigning the value immediately before the
    Interactions client is materialized keeps a zero retry budget genuinely
    zero for visitor questions and keeps the upload client's single-attempt
    configuration intact.
    """

    api_client = getattr(client, "_api_client", None)
    http_options = getattr(api_client, "_http_options", None)
    retry_options = getattr(http_options, "retry_options", None)
    if retry_options is not None:
        retry_options.attempts = additional_retries
        trace_event("gemini.interaction_retry_configured", additional_retries=additional_retries)
    else:
        trace_event("gemini.interaction_retry_unavailable")
