"""Small local-only tracing primitives for debugging RAG request boundaries."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator


_MAX_TRACE_EVENTS = 80
_MAX_STRING_LENGTH = 120
_active_trace: ContextVar["RagRequestTrace | None"] = ContextVar("active_rag_trace", default=None)


def _safe_value(value: object) -> bool | int | float | str | None:
    """Keep trace values bounded and never accept arbitrary provider payloads."""

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]
    return type(value).__name__


@dataclass
class RagRequestTrace:
    """A per-request list of structural events, with no prompt or answer text."""

    events: list[dict[str, object]] = field(default_factory=list)

    def record(self, event: str, **details: object) -> None:
        if len(self.events) >= _MAX_TRACE_EVENTS:
            return
        self.events.append(
            {
                "event": event,
                **{key: _safe_value(value) for key, value in details.items()},
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {"event_count": len(self.events), "events": list(self.events)}


@contextmanager
def capture_rag_trace() -> Iterator[RagRequestTrace]:
    """Activate one trace for the current request or local diagnostic command."""

    trace = RagRequestTrace()
    token = _active_trace.set(trace)
    try:
        yield trace
    finally:
        _active_trace.reset(token)


def trace_event(event: str, **details: object) -> None:
    """Record structural state only when a caller explicitly opened a trace."""

    trace = _active_trace.get()
    if trace is not None:
        trace.record(event, **details)
