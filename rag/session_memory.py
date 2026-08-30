from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from threading import Lock


def parse_browser_session_id(value: object) -> str | None:
    """Accept only a canonical browser-generated UUID without retaining it in logs."""

    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except (AttributeError, ValueError):
        return None


@dataclass
class _ConversationSession:
    interaction_id: str
    expires_at: float
    navigation_topic: str | None = None


class InMemoryConversationSessionStore:
    """Keep final-reply IDs and a short non-text navigation category per page.

    The category can be values such as ``profile`` or ``other`` and exists only
    to make a vague follow-up deterministic. This process-local cache never
    stores visitor text, answers, citations, sources, or raw provider output.
    A page reload creates a new browser UUID, so it cannot resume a prior chain.
    Expiry is a fallback when an unload request never reaches the server.
    """

    def __init__(self, maximum_sessions: int = 512) -> None:
        self._maximum_sessions = maximum_sessions
        self._sessions: dict[str, _ConversationSession] = {}
        self._lock = Lock()

    def previous_interaction_id(
        self, session_id: str, ttl_seconds: int, now: float | None = None
    ) -> str | None:
        current_time = time.monotonic() if now is None else now
        with self._lock:
            self._prune(current_time)
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.expires_at = current_time + ttl_seconds
            return session.interaction_id

    def save(
        self,
        session_id: str,
        interaction_id: str,
        ttl_seconds: int,
        now: float | None = None,
        navigation_topic: str | None = None,
    ) -> None:
        current_time = time.monotonic() if now is None else now
        with self._lock:
            self._prune(current_time)
            if session_id not in self._sessions and len(self._sessions) >= self._maximum_sessions:
                oldest_session_id = min(
                    self._sessions,
                    key=lambda candidate: self._sessions[candidate].expires_at,
                )
                del self._sessions[oldest_session_id]
            existing = self._sessions.get(session_id)
            self._sessions[session_id] = _ConversationSession(
                interaction_id=interaction_id,
                expires_at=current_time + ttl_seconds,
                navigation_topic=(
                    navigation_topic
                    if navigation_topic is not None
                    else existing.navigation_topic
                    if existing is not None
                    else None
                ),
            )

    def navigation_topic(
        self, session_id: str, ttl_seconds: int, now: float | None = None
    ) -> str | None:
        """Read one bounded navigation category while refreshing the session TTL."""

        current_time = time.monotonic() if now is None else now
        with self._lock:
            self._prune(current_time)
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.expires_at = current_time + ttl_seconds
            return session.navigation_topic

    def pop(self, session_id: str, now: float | None = None) -> str | None:
        current_time = time.monotonic() if now is None else now
        with self._lock:
            self._prune(current_time)
            session = self._sessions.pop(session_id, None)
            return session.interaction_id if session is not None else None

    def _prune(self, current_time: float) -> None:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= current_time
        ]
        for session_id in expired:
            del self._sessions[session_id]
