from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import RagConfigurationError
from .diagnostics import trace_event
from .models import Source


class SourceRegistry:
    """Loads the allow-list used both for ingestion and citation rendering."""

    def __init__(self, sources: Iterable[Source]):
        self._sources = {source.id: source for source in sources}
        if not self._sources:
            raise RagConfigurationError("The approved-public source registry is empty.")

    @classmethod
    def from_file(cls, manifest_path: Path) -> "SourceRegistry":
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RagConfigurationError(
                f"Approved-public source manifest was not found: {manifest_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RagConfigurationError(
                f"Approved-public source manifest is invalid JSON: {manifest_path}"
            ) from exc

        records = data.get("sources")
        if not isinstance(records, list):
            raise RagConfigurationError("The source manifest must contain a 'sources' list.")

        manifest_root = manifest_path.parent.resolve()
        sources: list[Source] = []
        seen_ids: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise RagConfigurationError("Every source manifest entry must be an object.")
            required = ("id", "path", "title", "url", "source_type", "project", "public", "enabled")
            missing = [field for field in required if field not in record]
            if missing:
                raise RagConfigurationError(
                    f"Source manifest entry is missing: {', '.join(missing)}"
                )

            source_id = str(record["id"]).strip()
            relative_path = Path(str(record["path"]))
            resolved_path = (manifest_root / relative_path).resolve()
            if not source_id or source_id in seen_ids:
                raise RagConfigurationError("Source IDs must be non-empty and unique.")
            if not resolved_path.is_relative_to(manifest_root):
                raise RagConfigurationError(f"Source '{source_id}' must stay inside the knowledge directory.")
            if not resolved_path.is_file():
                raise RagConfigurationError(f"Source '{source_id}' file does not exist: {relative_path}")

            source_url = str(record["url"]).strip()
            demo_url = record.get("demo_url")
            demo_label = record.get("demo_label")
            if (demo_url is None) != (demo_label is None):
                raise RagConfigurationError(
                    f"Source '{source_id}' must declare both demo_url and demo_label."
                )
            if demo_url is not None and not isinstance(demo_url, str):
                raise RagConfigurationError(f"Source '{source_id}' has an invalid demo URL.")
            if demo_label is not None and not isinstance(demo_label, str):
                raise RagConfigurationError(f"Source '{source_id}' has an invalid demo label.")
            demo_url = demo_url.strip() if demo_url is not None else None
            demo_label = demo_label.strip() if demo_label is not None else None
            for url, label in ((source_url, "canonical"), (demo_url, "demo")):
                if url and not (url.startswith("/") or url.startswith("https://")):
                    raise RagConfigurationError(
                        f"Source '{source_id}' has a non-public {label} URL."
                    )
            if demo_url and not demo_label:
                raise RagConfigurationError(f"Source '{source_id}' has an empty demo label.")

            sources.append(
                Source(
                    id=source_id,
                    path=relative_path.as_posix(),
                    title=str(record["title"]).strip(),
                    url=source_url,
                    source_type=str(record["source_type"]).strip(),
                    project=str(record["project"]).strip(),
                    public=record["public"] is True,
                    enabled=record["enabled"] is True,
                    demo_url=demo_url,
                    demo_label=demo_label,
                )
            )
            seen_ids.add(source_id)

        registry = cls(sources)
        trace_event(
            "sources.manifest_loaded",
            declared_sources=len(sources),
            active_sources=len(registry.active_sources()),
        )
        return registry

    def active_sources(self) -> tuple[Source, ...]:
        return tuple(source for source in self._sources.values() if source.public and source.enabled)

    def resolve(self, source_id: str | None) -> Source | None:
        """Resolve only an explicit, allow-listed source ID from vector metadata.

        Filenames are intentionally not identifiers: a file in a vector store can be
        renamed to resemble an approved document. The ingestion flow stamps a stable
        ``source_id`` attribute on every approved file, which must be present here.
        """

        source = self._sources.get(source_id or "")
        if source is None or not source.public or not source.enabled:
            return None
        return source
