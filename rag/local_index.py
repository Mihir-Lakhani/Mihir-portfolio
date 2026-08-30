from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np

from .config import RagConfigurationError
from .models import ApprovedDiagram, Source
from .sources import SourceRegistry


INDEX_VERSION = 2
MANIFEST_FILE_NAME = "manifest.json"
VECTORS_FILE_NAME = "vectors.npy"
_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9+#._-]*", re.IGNORECASE)
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_MERMAID_START = re.compile(r"^```mermaid\s*$", re.IGNORECASE)
_WORD_TARGET = 220
_WORD_OVERLAP = 40


class EmbeddingProvider(Protocol):
    @property
    def model(self) -> str: ...

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    source_id: str
    content_sha256: str
    heading_path: tuple[str, ...]
    text: str
    tokens: tuple[str, ...]
    kind: str = "content"

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "IndexedChunk":
        return cls(
            chunk_id=str(payload["chunk_id"]),
            source_id=str(payload["source_id"]),
            content_sha256=str(payload["content_sha256"]),
            heading_path=tuple(str(item) for item in payload.get("heading_path", ())),
            text=str(payload["text"]),
            tokens=tuple(str(item) for item in payload.get("tokens", ())),
            kind=str(payload.get("kind", "content")),
        )


@dataclass(frozen=True)
class LocalIndex:
    version: int
    embedding_model: str
    source_hashes: dict[str, str]
    chunks: tuple[IndexedChunk, ...]
    vectors: np.ndarray
    diagrams: tuple[ApprovedDiagram, ...]

    def chunk_by_id(self, chunk_id: str) -> IndexedChunk | None:
        return next((chunk for chunk in self.chunks if chunk.chunk_id == chunk_id), None)

    def diagram_by_id(self, diagram_id: str) -> ApprovedDiagram | None:
        return next((diagram for diagram in self.diagrams if diagram.diagram_id == diagram_id), None)


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _TOKEN_PATTERN.findall(text))


def active_source_hashes(knowledge_root: Path, registry: SourceRegistry) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for source in registry.active_sources():
        path = (knowledge_root / source.path).resolve()
        if not path.is_file():
            raise RagConfigurationError(f"Approved source '{source.id}' is missing.")
        hashes[source.id] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _vector_sha256(vectors: np.ndarray) -> str:
    matrix = np.asarray(vectors, dtype=np.float32)
    return hashlib.sha256(matrix.tobytes(order="C")).hexdigest()


def _source_sections(source: Source, content: str, content_sha256: str) -> tuple[list[IndexedChunk], list[ApprovedDiagram]]:
    headings: list[tuple[int, str]] = []
    sections: list[tuple[tuple[str, ...], list[str]]] = []
    current: list[str] = []
    diagrams: list[ApprovedDiagram] = []
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    line_index = 0

    def flush() -> None:
        if current:
            sections.append((tuple(title for _, title in headings), current.copy()))
            current.clear()

    while line_index < len(lines):
        line = lines[line_index]
        heading_match = _HEADING_PATTERN.match(line)
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            title = " ".join(heading_match.group(2).split())
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))
            line_index += 1
            continue
        if _MERMAID_START.match(line.strip()):
            diagram_lines: list[str] = []
            line_index += 1
            while line_index < len(lines) and lines[line_index].strip() != "```":
                diagram_lines.append(lines[line_index])
                line_index += 1
            if line_index < len(lines):
                line_index += 1
            mermaid = "\n".join(diagram_lines).strip()
            if mermaid:
                ordinal = len(diagrams) + 1
                heading = headings[-1][1] if headings else source.title
                diagram_id = hashlib.sha256(
                    f"{source.id}|{content_sha256}|{ordinal}|{mermaid}".encode("utf-8")
                ).hexdigest()[:24]
                diagrams.append(
                    ApprovedDiagram(
                        diagram_id=f"diagram-{diagram_id}",
                        source_id=source.id,
                        content_sha256=content_sha256,
                        title=heading,
                        mermaid=mermaid,
                    )
                )
            continue
        current.append(line)
        line_index += 1
    flush()

    chunks: list[IndexedChunk] = []
    source_ordinal = 0
    for heading_path, section_lines in sections:
        section_text = "\n".join(section_lines).strip()
        words = section_text.split()
        if not words:
            continue
        for start in range(0, len(words), _WORD_TARGET - _WORD_OVERLAP):
            window = words[start : start + _WORD_TARGET]
            if not window:
                continue
            body = " ".join(window)
            title = " > ".join(heading_path) or source.title
            text = f"{title}\n{body}".strip()
            digest = hashlib.sha256(
                f"{source.id}|{content_sha256}|{source_ordinal}|{text}".encode("utf-8")
            ).hexdigest()[:24]
            chunks.append(
                IndexedChunk(
                    chunk_id=f"chunk-{digest}",
                    source_id=source.id,
                    content_sha256=content_sha256,
                    heading_path=heading_path,
                    text=text,
                    tokens=tokenize(text),
                )
            )
            source_ordinal += 1
            if start + _WORD_TARGET >= len(words):
                break

    if source.source_type == "project" and chunks:
        overview = chunks[0]
        catalogue_text = (
            f"Project catalogue entry: {source.title}\n"
            f"{overview.text[:900]}"
        )
        digest = hashlib.sha256(
            f"catalogue|{source.id}|{content_sha256}|{catalogue_text}".encode("utf-8")
        ).hexdigest()[:24]
        chunks.append(
            IndexedChunk(
                chunk_id=f"catalogue-{digest}",
                source_id=source.id,
                content_sha256=content_sha256,
                heading_path=("Project catalogue",),
                text=catalogue_text,
                tokens=tokenize(catalogue_text),
                kind="project_catalogue",
            )
        )
    return chunks, diagrams


def build_local_index(
    knowledge_root: Path, registry: SourceRegistry, embedder: EmbeddingProvider
) -> LocalIndex:
    source_hashes = active_source_hashes(knowledge_root, registry)
    chunks: list[IndexedChunk] = []
    diagrams: list[ApprovedDiagram] = []
    for source in registry.active_sources():
        path = (knowledge_root / source.path).resolve()
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RagConfigurationError(f"Approved source '{source.id}' is not UTF-8 Markdown.") from exc
        source_chunks, source_diagrams = _source_sections(source, content, source_hashes[source.id])
        chunks.extend(source_chunks)
        diagrams.extend(source_diagrams)
    if not chunks:
        raise RagConfigurationError("No approved public content is available for the local index.")
    vectors = embedder.embed_texts([chunk.text for chunk in chunks])
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
        raise RagConfigurationError("The local embedding service returned an invalid index matrix.")
    return LocalIndex(
        version=INDEX_VERSION,
        embedding_model=embedder.model,
        source_hashes=source_hashes,
        chunks=tuple(chunks),
        vectors=np.asarray(vectors, dtype=np.float32),
        diagrams=tuple(diagrams),
    )


def write_local_index(index: LocalIndex, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": index.version,
        "embedding_model": index.embedding_model,
        "source_hashes": index.source_hashes,
        "vector_sha256": _vector_sha256(index.vectors),
        "chunks": [asdict(chunk) for chunk in index.chunks],
        "diagrams": [asdict(diagram) for diagram in index.diagrams],
    }
    manifest_path = directory / MANIFEST_FILE_NAME
    vector_path = directory / VECTORS_FILE_NAME
    manifest_temp = directory / f"{MANIFEST_FILE_NAME}.tmp"
    vector_temp = directory / f"{VECTORS_FILE_NAME}.tmp"
    manifest_temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    with vector_temp.open("wb") as output:
        np.save(output, index.vectors)
    # Publish vectors first and the manifest last. A reader can therefore only
    # accept a matching vector digest; a midway replacement fails closed.
    os.replace(vector_temp, vector_path)
    os.replace(manifest_temp, manifest_path)


def load_local_index(directory: Path) -> LocalIndex:
    manifest_path = directory / MANIFEST_FILE_NAME
    vector_path = directory / VECTORS_FILE_NAME
    if not manifest_path.is_file() or not vector_path.is_file():
        raise RagConfigurationError(
            "The local portfolio index is missing. Build it before starting the assistant."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        vectors = np.load(vector_path, allow_pickle=False)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RagConfigurationError("The local portfolio index is unreadable. Rebuild it.") from exc
    if not isinstance(manifest, dict) or manifest.get("version") != INDEX_VERSION:
        raise RagConfigurationError("The local portfolio index version is unsupported. Rebuild it.")
    try:
        chunks = tuple(IndexedChunk.from_dict(item) for item in manifest["chunks"])
        diagrams = tuple(ApprovedDiagram(**item) for item in manifest.get("diagrams", ()))
        source_hashes = {str(key): str(value) for key, value in manifest["source_hashes"].items()}
        embedding_model = str(manifest["embedding_model"])
        vector_sha256 = str(manifest["vector_sha256"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RagConfigurationError("The local portfolio index manifest is invalid. Rebuild it.") from exc
    matrix = np.asarray(vectors, dtype=np.float32)
    if not chunks or matrix.ndim != 2 or matrix.shape[0] != len(chunks) or matrix.shape[1] == 0:
        raise RagConfigurationError("The local portfolio index is incomplete. Rebuild it.")
    if _vector_sha256(matrix) != vector_sha256:
        raise RagConfigurationError("The local portfolio index files do not match. Rebuild it.")
    return LocalIndex(
        version=INDEX_VERSION,
        embedding_model=embedding_model,
        source_hashes=source_hashes,
        chunks=chunks,
        vectors=matrix,
        diagrams=diagrams,
    )


def validate_local_index(
    index: LocalIndex, knowledge_root: Path, registry: SourceRegistry, embedding_model: str
) -> None:
    expected_hashes = active_source_hashes(knowledge_root, registry)
    if index.embedding_model != embedding_model:
        raise RagConfigurationError("The local index uses a different embedding model. Rebuild it.")
    if index.source_hashes != expected_hashes:
        raise RagConfigurationError("The local index does not match approved public sources. Rebuild it.")
    approved = set(expected_hashes)
    if any(
        chunk.source_id not in approved
        or chunk.content_sha256 != expected_hashes[chunk.source_id]
        for chunk in index.chunks
    ):
        raise RagConfigurationError("The local index contains unapproved source data. Rebuild it.")
    if any(
        diagram.source_id not in approved
        or diagram.content_sha256 != expected_hashes[diagram.source_id]
        for diagram in index.diagrams
    ):
        raise RagConfigurationError("The local index contains unapproved diagrams. Rebuild it.")
