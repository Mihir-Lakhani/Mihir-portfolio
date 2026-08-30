from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .diagnostics import trace_event


class RagConfigurationError(RuntimeError):
    """Raised when the public assistant is called before it is configured."""


_MINIMUM_FILE_SEARCH_TIMEOUT_SECONDS = 60.0


# A Flask process can be restarted from a fresh terminal at any time. Load the
# ignored project-local configuration before reading RAG settings, while keeping
# explicitly supplied process variables authoritative.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _read_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RagConfigurationError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise RagConfigurationError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _read_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RagConfigurationError(f"{name} must be a number.") from exc
    if not minimum <= value <= maximum:
        raise RagConfigurationError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RagConfigurationError(f"{name} must be true or false.")


def _read_optional_bool(name: str) -> bool | None:
    if os.getenv(name) is None:
        return None
    return _read_bool(name, False)


def _read_choice(name: str, default: str, choices: set[str]) -> str:
    value = os.getenv(name, default).strip().casefold()
    if value not in choices:
        choices_text = ", ".join(sorted(choices))
        raise RagConfigurationError(f"{name} must be one of: {choices_text}.")
    return value


@dataclass(frozen=True)
class RagSettings:
    gemini_api_key: str | None
    file_search_store_id: str | None
    model: str
    max_results: int
    max_question_characters: int
    max_answer_tokens: int
    rate_limit_per_minute: int
    global_rate_limit_per_minute: int = 60
    rate_limits_enabled: bool = False
    provider_timeout_seconds: float = 60.0
    provider_max_retries: int = 0
    max_conversation_turns: int = 6
    max_conversation_characters: int = 2400
    router_max_output_tokens: int = 180
    stateful_conversations: bool = True
    conversation_session_ttl_seconds: int = 1200
    retrieval_mode: str = "local_hybrid"
    environment: str = "development"
    local_index_directory: str = "instance/rag_local_index"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embedding_model: str = "nomic-embed-text"
    local_top_k: int = 6

    @classmethod
    def from_environment(cls) -> "RagSettings":
        environment = _read_choice(
            "RAG_ENV", "development", {"development", "production"}
        )
        configured_rate_limits = _read_optional_bool("RAG_ENABLE_RATE_LIMITS")
        settings = cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            file_search_store_id=os.getenv("RAG_GEMINI_FILE_SEARCH_STORE_ID") or None,
            # Flash-Lite supports File Search and structured output while being
            # the lower-latency default for this small public knowledge base.
            model=os.getenv("RAG_GEMINI_MODEL", "gemini-3.5-flash-lite"),
            # Source-aware navigation identifies the relevant document before
            # retrieval, so a bounded result window keeps free-tier latency sane.
            max_results=_read_int("RAG_MAX_RESULTS", 5, 1, 10),
            max_question_characters=_read_int("RAG_MAX_QUESTION_CHARACTERS", 2000, 20, 4000),
            max_answer_tokens=_read_int("RAG_MAX_ANSWER_TOKENS", 350, 50, 1000),
            rate_limit_per_minute=_read_int("RAG_RATE_LIMIT_PER_MINUTE", 12, 1, 10000),
            global_rate_limit_per_minute=_read_int(
                "RAG_GLOBAL_RATE_LIMIT_PER_MINUTE", 60, 1, 10000
            ),
            rate_limits_enabled=(
                configured_rate_limits
                if configured_rate_limits is not None
                else environment == "production"
            ),
            provider_timeout_seconds=_read_float(
                "RAG_GEMINI_TIMEOUT_SECONDS", 60.0, 1.0, 120.0
            ),
            provider_max_retries=_read_int("RAG_GEMINI_MAX_RETRIES", 0, 0, 3),
            max_conversation_turns=_read_int("RAG_MAX_CONVERSATION_TURNS", 6, 0, 12),
            max_conversation_characters=_read_int(
                "RAG_MAX_CONVERSATION_CHARACTERS", 2400, 200, 6000
            ),
            router_max_output_tokens=_read_int(
                "RAG_ROUTER_MAX_OUTPUT_TOKENS", 180, 60, 300
            ),
            stateful_conversations=_read_bool("RAG_STATEFUL_CONVERSATIONS", True),
            conversation_session_ttl_seconds=_read_int(
                "RAG_CONVERSATION_SESSION_TTL_SECONDS", 1200, 60, 3600
            ),
            retrieval_mode=_read_choice(
                "RAG_RETRIEVAL_MODE",
                "local_hybrid",
                {"local_hybrid", "gemini_file_search"},
            ),
            environment=environment,
            local_index_directory=os.getenv(
                "RAG_LOCAL_INDEX_DIR", "instance/rag_local_index"
            ),
            ollama_base_url=os.getenv(
                "RAG_OLLAMA_BASE_URL", "http://127.0.0.1:11434"
            ).rstrip("/"),
            ollama_embedding_model=os.getenv(
                "RAG_OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
            ),
            local_top_k=_read_int("RAG_LOCAL_TOP_K", 6, 1, 12),
        )
        trace_event(
            "config.loaded",
            model=settings.model,
            has_api_key=bool(settings.gemini_api_key),
            has_store_id=bool(settings.file_search_store_id),
            retrieval_mode=settings.retrieval_mode,
            environment=settings.environment,
            max_results=settings.max_results,
            timeout_seconds=settings.effective_provider_timeout_seconds,
            additional_retries=settings.effective_provider_max_retries,
            max_conversation_turns=settings.max_conversation_turns,
            stateful_conversations=settings.stateful_conversations,
        )
        return settings

    @property
    def effective_provider_timeout_seconds(self) -> float:
        """Avoid cutting off File Search before a normal retrieval can complete."""

        return max(self.provider_timeout_seconds, _MINIMUM_FILE_SEARCH_TIMEOUT_SECONDS)

    @property
    def effective_provider_max_retries(self) -> int:
        """Use the explicitly configured retry budget for provider calls."""

        return self.provider_max_retries

    @property
    def effective_rate_limit_per_minute(self) -> int:
        """Return the optional local visitor limit without altering provider quotas."""

        return self.rate_limit_per_minute if self.rate_limits_enabled else 0

    @property
    def effective_global_rate_limit_per_minute(self) -> int:
        """Return the optional local process limit without altering provider quotas."""

        return self.global_rate_limit_per_minute if self.rate_limits_enabled else 0

    def require_api_key(self) -> None:
        if not self.gemini_api_key:
            raise RagConfigurationError("GEMINI_API_KEY is required.")

    def require_runtime_configuration(self) -> None:
        missing = []
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")
        if self.retrieval_mode == "gemini_file_search" and not self.file_search_store_id:
            missing.append("RAG_GEMINI_FILE_SEARCH_STORE_ID")
        if missing:
            trace_event("config.runtime_missing", missing_count=len(missing))
            raise RagConfigurationError(
                "The portfolio assistant is not configured. Missing: " + ", ".join(missing)
            )
        trace_event("config.runtime_ready")
