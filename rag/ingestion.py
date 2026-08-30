from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import RagConfigurationError
from .diagnostics import trace_event
from .models import Source
from .sources import SourceRegistry


GEMINI_CHUNKING_CONFIG = {
    # Gemini File Search accepts at most 512 tokens per chunk. Keep a small
    # margin below that ceiling while preserving enough overlap for continuity.
    "white_space_config": {"max_tokens_per_chunk": 500, "max_overlap_tokens": 100},
}
GEMINI_EMBEDDING_MODEL = "models/gemini-embedding-2"
_MAX_DEDICATED_STORE_DOCUMENTS = 20
_POLL_INTERVAL_SECONDS = 2.0
_MAX_UPLOAD_WAIT_SECONDS = 600.0
_PENDING_UPLOAD_STATUS = "upload_pending"


def _safe_provider_diagnostic(exc: Exception) -> str:
    """Return bounded local CLI diagnostics without echoing a server secret."""

    message = " ".join(str(exc).split())
    message = re.sub(r"AIza[A-Za-z0-9_-]{20,}", "[redacted-api-key]", message)
    message = re.sub(
        r"(?i)(api[_-]?key|x-goog-api-key|key)(\s*[:=]\s*)([^\s,;]+)",
        r"\1\2[redacted]",
        message,
    )
    if len(message) > 600:
        message = message[:597] + "..."

    details = [type(exc).__name__]
    code = getattr(exc, "code", None)
    status = getattr(exc, "status", None)
    if code is not None:
        details.append(f"HTTP {code}")
    if status:
        details.append(str(status))
    if message:
        details.append(message)
    return ": ".join(details)


@dataclass(frozen=True)
class IngestionPlanItem:
    source: Source
    path: Path
    sha256: str


@dataclass(frozen=True)
class GeminiDocumentRecord:
    document_name: str
    sha256: str
    display_name: str | None = None


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_items(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, Mapping)):
        return ()
    data = _field(value, "data")
    if data is not None:
        return tuple(data or ())
    try:
        return tuple(value)
    except TypeError:
        return ()


def _metadata_map(value: Any) -> dict[str, str]:
    if isinstance(value, Mapping):
        return {
            str(key): str(item)
            for key, item in value.items()
            if isinstance(item, (str, int, float, bool))
        }

    metadata: dict[str, str] = {}
    for item in _as_items(value):
        key = _field(item, "key")
        string_value = _field(item, "string_value")
        numeric_value = _field(item, "numeric_value")
        if isinstance(key, str) and key and isinstance(string_value, str):
            metadata[key] = string_value
        elif isinstance(key, str) and key and isinstance(numeric_value, (int, float)):
            metadata[key] = str(numeric_value)
    return metadata


def _custom_metadata_for(source: Source, sha256: str) -> list[dict[str, str]]:
    """Stamp every remote document with the local approval identity."""

    values = {
        "source_id": source.id,
        "content_sha256": sha256,
        "source_type": source.source_type,
        "project": source.project,
        "visibility": "public",
        "manifest_public": "true",
        "manifest_enabled": "true",
    }
    return [{"key": key, "string_value": value} for key, value in values.items()]


def _document_state(document: Any) -> str:
    state = _field(document, "state")
    value = getattr(state, "value", state)
    return str(value or "")


def build_ingestion_plan(knowledge_root: Path, registry: SourceRegistry) -> tuple[IngestionPlanItem, ...]:
    items: list[IngestionPlanItem] = []
    for source in registry.active_sources():
        path = (knowledge_root / source.path).resolve()
        content = path.read_bytes()
        items.append(
            IngestionPlanItem(
                source=source,
                path=path,
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )
    plan = tuple(items)
    trace_event("ingestion.plan_built", approved_sources=len(plan))
    return plan


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.is_file():
        return {"provider": "gemini_file_search", "sources": {}}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RagConfigurationError(f"RAG ingestion state is invalid: {state_path}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("sources", {}), dict):
        raise RagConfigurationError(f"RAG ingestion state has an invalid shape: {state_path}")
    if data.get("provider") not in (None, "gemini_file_search"):
        raise RagConfigurationError(
            f"RAG ingestion state belongs to another provider: {state_path}. "
            "Use the Gemini-specific state file."
        )
    data["provider"] = "gemini_file_search"
    return data


def _write_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_suffix(state_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_path.replace(state_path)


def _remote_documents(client: Any, file_search_store_id: str) -> tuple[Any, ...]:
    documents = _as_items(
        client.file_search_stores.documents.list(
            parent=file_search_store_id,
            config={"page_size": _MAX_DEDICATED_STORE_DOCUMENTS},
        )
    )
    trace_event("ingestion.remote_documents_listed", document_count=len(documents))
    if len(documents) > _MAX_DEDICATED_STORE_DOCUMENTS:
        raise RagConfigurationError(
            "The Gemini File Search store has more documents than this dedicated assistant allows. "
            "Use a new clean store."
        )

    unsettled: list[str] = []
    for document in documents:
        if _document_state(document) == "STATE_ACTIVE":
            continue
        metadata = _metadata_map(_field(document, "custom_metadata", ()))
        label = metadata.get("source_id") or str(_field(document, "name", "unknown document"))
        unsettled.append(f"{label} ({_document_state(document) or 'unknown state'})")
    if unsettled:
        raise RagConfigurationError(
            "The Gemini File Search store has documents that are not active: "
            + ", ".join(unsettled)
            + ". Wait for indexing to finish before rerunning ingestion. "
            "For failed documents, use a new dedicated store."
        )
    return documents


def _remote_source_records(
    client: Any, file_search_store_id: str
) -> dict[str, GeminiDocumentRecord]:
    """Read only a settled, small store and validate its policy metadata."""

    records: dict[str, GeminiDocumentRecord] = {}
    for document in _remote_documents(client, file_search_store_id):
        metadata = _metadata_map(_field(document, "custom_metadata", ()))
        source_id = metadata.get("source_id")
        content_sha256 = metadata.get("content_sha256")
        document_name = _field(document, "name")
        display_name = _field(document, "display_name")
        if not all(
            isinstance(value, str) and value
            for value in (source_id, content_sha256, document_name, display_name)
        ):
            raise RagConfigurationError(
                "The Gemini File Search store contains a document without a source ID, "
                "content hash, document name, or display name. Use a new dedicated store."
            )
        expected_prefix = f"{file_search_store_id}/documents/"
        if not document_name.startswith(expected_prefix):
            raise RagConfigurationError(
                "The Gemini File Search store returned a document from an unexpected store. "
                "Use a new dedicated store."
            )
        if (
            metadata.get("visibility") != "public"
            or metadata.get("manifest_public") != "true"
            or metadata.get("manifest_enabled") != "true"
        ):
            raise RagConfigurationError(
                "The Gemini File Search store contains a document outside the approved public "
                "source policy. Use a new dedicated store."
            )
        if source_id in records:
            raise RagConfigurationError(
                f"The Gemini File Search store contains duplicate documents for '{source_id}'. "
                "Use a new dedicated store."
            )
        records[source_id] = GeminiDocumentRecord(
            document_name=document_name,
            sha256=content_sha256,
            display_name=display_name,
        )
    return records


def approved_remote_documents(
    client: Any,
    file_search_store_id: str,
    plan: tuple[IngestionPlanItem, ...],
) -> dict[str, GeminiDocumentRecord]:
    """Fail closed unless the remote store exactly matches the approved source plan."""

    records = _remote_source_records(client, file_search_store_id)
    expected = {item.source.id: item.sha256 for item in plan}
    unexpected = sorted(set(records) - set(expected))
    missing = sorted(set(expected) - set(records))
    if unexpected or missing:
        details: list[str] = []
        if unexpected:
            details.append("unexpected: " + ", ".join(unexpected))
        if missing:
            details.append("missing: " + ", ".join(missing))
        raise RagConfigurationError(
            "The configured Gemini File Search store does not exactly match the approved public "
            "source plan ("
            + "; ".join(details)
            + "). Create and ingest a new dedicated store."
        )

    approved: dict[str, GeminiDocumentRecord] = {}
    for source_id, sha256 in expected.items():
        record = records[source_id]
        if record.sha256 != sha256:
            raise RagConfigurationError(
                f"Remote source '{source_id}' does not match the current approved file. "
                "Create and ingest a new dedicated store."
            )
        expected_display_name = next(
            item.path.name for item in plan if item.source.id == source_id
        )
        if record.display_name != expected_display_name:
            raise RagConfigurationError(
                f"Remote source '{source_id}' has an unexpected display name. "
                "Create and ingest a new dedicated store."
            )
        approved[source_id] = record
    trace_event("ingestion.remote_store_validated", approved_documents=len(approved))
    return approved


def _wait_for_upload(client: Any, operation: Any, source_id: str) -> Any:
    deadline = time.monotonic() + _MAX_UPLOAD_WAIT_SECONDS
    while not bool(_field(operation, "done", False)):
        if time.monotonic() >= deadline:
            raise RagConfigurationError(
                f"Gemini indexing for '{source_id}' did not finish within the allowed wait time. "
                "Check the store before retrying."
            )
        time.sleep(_POLL_INTERVAL_SECONDS)
        operation = client.operations.get(operation)
    if _field(operation, "error"):
        raise RagConfigurationError(
            f"Gemini could not index '{source_id}'. Check the Gemini API response in the server "
            "environment before retrying."
        )
    return operation


def _state_record(
    item: IngestionPlanItem,
    file_search_store_id: str,
    document_name: str,
    display_name: str | None = None,
    *,
    status: str | None = None,
) -> dict[str, str]:
    record = {
        "file_search_store_id": file_search_store_id,
        "sha256": item.sha256,
        "document_name": document_name,
        "filename": item.path.name,
    }
    if display_name is not None:
        record["display_name"] = display_name
    if status is not None:
        record["status"] = status
    return record


def ingest_plan(
    client: Any,
    file_search_store_id: str,
    plan: tuple[IngestionPlanItem, ...],
    state_path: Path,
    *,
    debug: bool = False,
) -> tuple[int, int]:
    """Upload newly approved documents without silently mixing public source versions."""

    state = _load_state(state_path)
    state_sources: dict[str, Any] = state.setdefault("sources", {})
    remote_sources = _remote_source_records(client, file_search_store_id)
    expected_source_ids = {item.source.id for item in plan}
    unexpected_sources = sorted(set(remote_sources) - expected_source_ids)
    if unexpected_sources:
        raise RagConfigurationError(
            "The Gemini File Search store contains unapproved sources: "
            + ", ".join(unexpected_sources)
            + ". Use a new dedicated store."
        )

    uploaded = 0
    skipped = 0
    for item in plan:
        previous = state_sources.get(item.source.id)
        if previous is not None and not isinstance(previous, dict):
            raise RagConfigurationError(
                f"RAG ingestion state for '{item.source.id}' has an invalid shape. "
                "Use a new dedicated store."
            )
        if previous and previous.get("file_search_store_id") == file_search_store_id:
            if previous.get("sha256") != item.sha256:
                raise RagConfigurationError(
                    f"Source '{item.source.id}' changed after ingestion. Create a new File Search "
                    "store and ingest again so old and new public claims cannot be mixed."
                )

        remote = remote_sources.get(item.source.id)
        if (
            previous
            and previous.get("file_search_store_id") == file_search_store_id
            and previous.get("status") == _PENDING_UPLOAD_STATUS
        ):
            if remote is None:
                raise RagConfigurationError(
                    f"A previous upload for '{item.source.id}' may have been accepted but is not "
                    "visible in the Gemini store yet. Do not retry blindly; inspect the store or "
                    "use a new dedicated store."
                )
            if remote.sha256 != item.sha256:
                raise RagConfigurationError(
                    f"The uncertain remote upload for '{item.source.id}' does not match the "
                    "approved local file. Use a new dedicated store."
                )
            state_sources[item.source.id] = _state_record(
                item, file_search_store_id, remote.document_name, remote.display_name
            )
            _write_state(state_path, state)
            skipped += 1
            continue

        if remote is not None:
            if remote.sha256 != item.sha256:
                raise RagConfigurationError(
                    f"Remote source '{item.source.id}' differs from the approved local file. "
                    "Create and ingest a new dedicated store."
                )
            state_sources[item.source.id] = _state_record(
                item, file_search_store_id, remote.document_name, remote.display_name
            )
            _write_state(state_path, state)
            skipped += 1
            continue

        # The provider does not expose an idempotency key for direct store uploads. Persist
        # an in-flight marker before the request so a crash or timeout cannot trigger a blind
        # duplicate on the next run.
        state_sources[item.source.id] = _state_record(
            item,
            file_search_store_id,
            "",
            status=_PENDING_UPLOAD_STATUS,
        )
        _write_state(state_path, state)
        try:
            operation = client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=file_search_store_id,
                file=item.path,
                config={
                    "display_name": item.path.name,
                    "mime_type": "text/markdown",
                    "custom_metadata": _custom_metadata_for(item.source, item.sha256),
                    "chunking_config": GEMINI_CHUNKING_CONFIG,
                },
            )
            _wait_for_upload(client, operation, item.source.id)
        except Exception as exc:
            diagnostic = (
                " Local admin diagnostic: " + _safe_provider_diagnostic(exc)
                if debug
                else ""
            )
            raise RagConfigurationError(
                f"Gemini upload for '{item.source.id}' may have been accepted but could not be "
                "confirmed. Inspect the store before retrying, or use a new dedicated store."
                + diagnostic
            ) from exc

        # Re-list after the completed operation rather than trusting a local filename or
        # operation payload. The remote document metadata is the serving-time identity.
        remote_sources = _remote_source_records(client, file_search_store_id)
        remote = remote_sources.get(item.source.id)
        if remote is None or remote.sha256 != item.sha256:
            raise RagConfigurationError(
                f"Gemini finished indexing '{item.source.id}' without a matching approved document. "
                "Do not serve this store; create a new dedicated store."
            )

        state_sources[item.source.id] = _state_record(
            item, file_search_store_id, remote.document_name, remote.display_name
        )
        _write_state(state_path, state)
        uploaded += 1

    return uploaded, skipped
