from __future__ import annotations

import atexit
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock
from typing import Callable

from flask import Blueprint, current_app, jsonify, request

from .config import RagConfigurationError, RagSettings
from .diagnostics import RagRequestTrace, capture_rag_trace, trace_event
from .ingestion import _safe_provider_diagnostic
from .models import ConversationTurn
from .session_memory import InMemoryConversationSessionStore, parse_browser_session_id
from .service import PortfolioAssistantService, create_gemini_service


class InMemoryMinuteRateLimiter:
    """A small local guard against accidental public API abuse.

    A shared external limiter is appropriate when the site runs across multiple workers.
    This keeps the single-process Flask deployment safe by default without another service.
    """

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._last_prune = 0.0

    def allow(self, key: str, limit: int, now: float | None = None) -> bool:
        current_time = time.monotonic() if now is None else now
        cutoff = current_time - 60
        with self._lock:
            if current_time - self._last_prune >= 60:
                stale_keys = [
                    request_key
                    for request_key, timestamps in self._requests.items()
                    if not timestamps or timestamps[-1] <= cutoff
                ]
                for stale_key in stale_keys:
                    del self._requests[stale_key]
                self._last_prune = current_time
            window = self._requests[key]
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(current_time)
            return True


def _default_service_factory() -> PortfolioAssistantService:
    return create_gemini_service(Path(current_app.root_path))


_SERVICE_CACHE_KEY = "portfolio_rag_service"
_SERVICE_CACHE_LOCK = Lock()
_CONVERSATION_SESSION_STORE_KEY = "portfolio_rag_conversation_sessions"
_DIAGNOSTIC_HISTORY_LIMIT = 20


def _close_service(service: PortfolioAssistantService) -> None:
    closer = getattr(service, "close", None)
    if callable(closer):
        closer()


def _service_from_app() -> PortfolioAssistantService:
    app = current_app._get_current_object()
    factory: Callable[[], PortfolioAssistantService] = app.config.get(
        "RAG_SERVICE_FACTORY", _default_service_factory
    )
    with _SERVICE_CACHE_LOCK:
        service = app.extensions.get(_SERVICE_CACHE_KEY)
        if service is None:
            service = factory()
            app.extensions[_SERVICE_CACHE_KEY] = service
            # Flask has no portable per-process shutdown hook across WSGI servers.
            # The registered callback closes the pooled SDK client when this process exits.
            atexit.register(_close_service, service)
        return service


def _rate_limiter_from_app() -> InMemoryMinuteRateLimiter:
    limiter = current_app.config.get("RAG_RATE_LIMITER")
    if limiter is None:
        limiter = InMemoryMinuteRateLimiter()
        current_app.config["RAG_RATE_LIMITER"] = limiter
    return limiter


def _conversation_session_store_from_app() -> InMemoryConversationSessionStore:
    """Return the process-local map of browser pages to Gemini interaction IDs."""

    store = current_app.config.get(_CONVERSATION_SESSION_STORE_KEY)
    if store is None:
        store = InMemoryConversationSessionStore()
        current_app.config[_CONVERSATION_SESSION_STORE_KEY] = store
    return store


def _write_local_diagnostic(payload: dict[str, object]) -> None:
    """Persist a redacted rolling local history when explicitly configured."""

    configured_path = current_app.config.get("RAG_LOCAL_DIAGNOSTICS_PATH")
    if not configured_path:
        return

    try:
        path = Path(configured_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {**payload, "recorded_at_unix": int(time.time())}
        history: list[dict[str, object]] = []
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("recent"), list):
                history = [item for item in existing["recent"] if isinstance(item, dict)]
            elif isinstance(existing, dict):
                # Preserve the older single-record format as the first history item.
                history = [existing]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        payload = {**entry, "recent": (history + [entry])[-_DIAGNOSTIC_HISTORY_LIMIT:]}
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        temporary_path.replace(path)
    except OSError:
        current_app.logger.warning("Could not write local portfolio assistant diagnostic")


def _respond(
    payload: dict[str, object],
    status_code: int,
    *,
    trace: RagRequestTrace,
    outcome: str,
    provider_error: Exception | None = None,
    evidence: dict[str, object] | None = None,
) -> tuple[object, int] | object:
    """Return a visitor-safe response and, when opted in, a local structural trace."""

    trace_event("route.response", outcome=outcome, status_code=status_code)
    diagnostic: dict[str, object] = {
        "outcome": outcome,
        "http_status": status_code,
        "trace": trace.to_dict(),
    }
    if provider_error is not None:
        diagnostic["message"] = _safe_provider_diagnostic(provider_error)
    if evidence is not None:
        diagnostic["evidence"] = evidence
    _write_local_diagnostic(diagnostic)

    response = jsonify(payload)
    if status_code == 200:
        return response
    return response, status_code


def _is_provider_rate_limit(exc: Exception) -> bool:
    """Recognize quota errors without depending on a provider SDK exception class."""

    return getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429


def _parse_conversation(
    raw_conversation: object, settings: RagSettings
) -> tuple[ConversationTurn, ...] | None:
    """Validate bounded browser context without treating it as portfolio evidence."""

    if raw_conversation is None:
        return ()
    if not isinstance(raw_conversation, list) or len(raw_conversation) > settings.max_conversation_turns:
        return None

    turns: list[ConversationTurn] = []
    total_characters = 0
    for raw_turn in raw_conversation:
        if not isinstance(raw_turn, dict):
            return None
        role = raw_turn.get("role")
        text = raw_turn.get("text")
        grounded = raw_turn.get("grounded")
        if role not in {"visitor", "assistant"} or not isinstance(text, str) or not isinstance(grounded, bool):
            return None
        normalized_text = " ".join(text.split())
        # Conversation messages can be longer than a new visitor question. The
        # bounded total context window below is the relevant safety limit here.
        if not normalized_text:
            return None
        total_characters += len(normalized_text)
        if total_characters > settings.max_conversation_characters:
            return None
        turns.append(ConversationTurn(role=role, text=normalized_text, grounded=grounded))
    return tuple(turns)


rag_bp = Blueprint("rag", __name__)


@rag_bp.post("/api/ask")
def ask_portfolio() -> tuple[object, int] | object:
    with capture_rag_trace() as trace:
        trace_event("route.request_received", json_request=request.is_json)
        if not request.is_json:
            return _respond(
                {"error": "Send a JSON request with a 'question' field."},
                400,
                trace=trace,
                outcome="invalid_content_type",
            )

        payload = request.get_json(silent=True)
        question = payload.get("question") if isinstance(payload, dict) else None
        if not isinstance(question, str):
            return _respond(
                {"error": "'question' must be a text value."},
                400,
                trace=trace,
                outcome="invalid_question_type",
            )

        normalized_question = " ".join(question.split())
        trace_event("route.question_normalized", question_characters=len(normalized_question))
        if len(normalized_question) < 2:
            return _respond(
                {"error": "Please enter a question."},
                400,
                trace=trace,
                outcome="empty_question",
            )

        try:
            settings = RagSettings.from_environment()
        except RagConfigurationError:
            # Configuration exceptions can contain environment variable names. Do not
            # retain raw exception text in application logs alongside deployment secrets.
            current_app.logger.error("Invalid portfolio assistant configuration")
            return _respond(
                {"error": "The portfolio assistant is not configured yet."},
                503,
                trace=trace,
                outcome="invalid_configuration",
            )

        if len(normalized_question) > settings.max_question_characters:
            return _respond(
                {"error": f"Please keep questions under {settings.max_question_characters} characters."},
                400,
                trace=trace,
                outcome="question_too_long",
            )

        browser_session_id: str | None = None
        if "conversation_session_id" in payload:
            browser_session_id = parse_browser_session_id(
                payload.get("conversation_session_id")
            )
            if browser_session_id is None:
                return _respond(
                    {"error": "Conversation session must be a valid browser session."},
                    400,
                    trace=trace,
                    outcome="invalid_conversation_session",
                )
            if payload.get("conversation") is not None:
                return _respond(
                    {
                        "error": (
                            "Send either legacy conversation context or a browser conversation session, "
                            "not both."
                        )
                    },
                    400,
                    trace=trace,
                    outcome="mixed_conversation_context",
                )

        conversation = _parse_conversation(payload.get("conversation"), settings)
        if conversation is None:
            return _respond(
                {"error": "Conversation context must contain a small list of valid chat messages."},
                400,
                trace=trace,
                outcome="invalid_conversation_context",
            )
        trace_event(
            "route.conversation_validated",
            turn_count=len(conversation),
            character_count=sum(len(turn.text) for turn in conversation),
        )

        use_stateful_router = bool(settings.stateful_conversations and browser_session_id)
        previous_interaction_id: str | None = None
        navigation_topic: str | None = None
        session_store: InMemoryConversationSessionStore | None = None
        if use_stateful_router and browser_session_id is not None:
            session_store = _conversation_session_store_from_app()
            previous_interaction_id = session_store.previous_interaction_id(
                browser_session_id,
                settings.conversation_session_ttl_seconds,
            )
            navigation_topic = session_store.navigation_topic(
                browser_session_id,
                settings.conversation_session_ttl_seconds,
            )
        trace_event(
            "route.conversation_session_selected",
            stateful_router=use_stateful_router,
            continuing_interaction=previous_interaction_id is not None,
        )

        visitor_key = request.remote_addr or "unknown"
        global_limit = settings.effective_global_rate_limit_per_minute
        visitor_limit = settings.effective_rate_limit_per_minute
        if global_limit and not _rate_limiter_from_app().allow(
            "__portfolio_assistant_global__", global_limit
        ):
            return _respond(
                {"error": "The portfolio assistant is busy. Please try again shortly."},
                429,
                trace=trace,
                outcome="global_rate_limited",
            )
        if visitor_limit and not _rate_limiter_from_app().allow(visitor_key, visitor_limit):
            return _respond(
                {"error": "Please wait a moment before asking another question."},
                429,
                trace=trace,
                outcome="visitor_rate_limited",
            )

        try:
            service = _service_from_app()
            service_options: dict[str, object] = {
                "previous_interaction_id": previous_interaction_id,
                "use_stateful_router": use_stateful_router,
            }
            if navigation_topic == "profile":
                service_options["profile_context"] = True
            result = service.answer(normalized_question, conversation, **service_options)
        except RagConfigurationError:
            # Do not tell a public visitor which environment setting is missing.
            return _respond(
                {"error": "The portfolio assistant is not configured yet."},
                503,
                trace=trace,
                outcome="runtime_configuration_error",
            )
        except Exception as exc:
            if _is_provider_rate_limit(exc):
                return _respond(
                    {"error": "The portfolio assistant is busy. Please try again in a minute."},
                    429,
                    trace=trace,
                    outcome="provider_rate_limited",
                    provider_error=exc,
                )
            # Provider exception strings may include request metadata. Keep public and
            # server-side reporting generic so a secret-like value cannot be logged.
            current_app.logger.error("Portfolio assistant request failed")
            return _respond(
                {"error": "The portfolio assistant is temporarily unavailable. Please try again."},
                502,
                trace=trace,
                outcome="provider_failure",
                provider_error=exc,
            )

        if (
            session_store is not None
            and browser_session_id is not None
            and result.conversation_interaction_id is not None
        ):
            # Commit a new provider chain only after a visitor-safe result is ready.
            # A failed retrieval or answer request therefore leaves the last usable turn intact.
            session_store.save(
                browser_session_id,
                result.conversation_interaction_id,
                settings.conversation_session_ttl_seconds,
                navigation_topic=result.conversation_navigation_topic,
            )
            trace_event("route.conversation_session_saved")

        outcome = (
            "grounded_answer"
            if result.grounded
            else "conversation_answer"
            if result.mode == "conversation"
            else "refused_answer"
        )
        return _respond(
            result.to_dict(),
            200,
            trace=trace,
            outcome=outcome,
            evidence=result.evidence_diagnostic,
        )


@rag_bp.post("/api/conversation/end")
def end_portfolio_conversation() -> tuple[object, int] | object:
    """Best-effort removal of a stateful Gemini final-reply chain for one browser page."""

    with capture_rag_trace() as trace:
        trace_event("route.conversation_end_received", json_request=request.is_json)
        if not request.is_json:
            return _respond(
                {"error": "Send a JSON browser conversation session."},
                400,
                trace=trace,
                outcome="invalid_conversation_end_content_type",
            )

        payload = request.get_json(silent=True)
        raw_session_id = (
            payload.get("conversation_session_id") if isinstance(payload, dict) else None
        )
        browser_session_id = parse_browser_session_id(raw_session_id)
        if browser_session_id is None:
            return _respond(
                {"error": "Conversation session must be a valid browser session."},
                400,
                trace=trace,
                outcome="invalid_conversation_end_session",
            )

        interaction_id = _conversation_session_store_from_app().pop(browser_session_id)
        deleted = False
        if interaction_id is not None:
            try:
                deleted = _service_from_app().end_conversation(interaction_id)
            except Exception:
                # The browser has already dropped its page UUID. Retention falls back
                # to the provider policy if this best-effort deletion cannot complete.
                current_app.logger.warning("Could not delete portfolio conversation interaction")
        trace_event(
            "route.conversation_end_completed",
            had_active_interaction=interaction_id is not None,
            provider_deleted=deleted,
        )
        return _respond(
            {"ended": True},
            200,
            trace=trace,
            outcome="conversation_ended",
        )
