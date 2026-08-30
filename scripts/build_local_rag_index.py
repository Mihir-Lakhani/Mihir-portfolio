from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import RagConfigurationError, RagSettings
from rag.local_index import (
    build_local_index,
    load_local_index,
    validate_local_index,
    write_local_index,
)
from rag.ollama import OllamaEmbedder
from rag.sources import SourceRegistry


def _index_directory(settings: RagSettings) -> Path:
    directory = Path(settings.local_index_directory)
    return directory if directory.is_absolute() else PROJECT_ROOT / directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or validate the approved local portfolio RAG index."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the current index and local embedding service without rewriting it.",
    )
    args = parser.parse_args()

    try:
        settings = RagSettings.from_environment()
        registry = SourceRegistry.from_file(PROJECT_ROOT / "knowledge" / "sources.json")
        directory = _index_directory(settings)
        embedder = OllamaEmbedder(
            settings.ollama_base_url,
            settings.ollama_embedding_model,
            timeout_seconds=settings.effective_provider_timeout_seconds,
        )

        if args.check:
            index = load_local_index(directory)
            validate_local_index(
                index,
                PROJECT_ROOT / "knowledge",
                registry,
                settings.ollama_embedding_model,
            )
            health_vector = embedder.embed_texts(["approved local portfolio index health check"])
            print(
                "Local index is ready: "
                f"{len(index.chunks)} chunks, {len(index.diagrams)} diagrams, "
                f"{health_vector.shape[1]} dimensions."
            )
            return 0

        index = build_local_index(PROJECT_ROOT / "knowledge", registry, embedder)
        write_local_index(index, directory)
        validate_local_index(
            index,
            PROJECT_ROOT / "knowledge",
            registry,
            settings.ollama_embedding_model,
        )
        print(
            "Built local index: "
            f"{len(index.chunks)} chunks, {len(index.diagrams)} diagrams, "
            f"{index.vectors.shape[1]} dimensions."
        )
        print(f"Index directory: {directory}")
        return 0
    except RagConfigurationError as exc:
        action = "check" if args.check else "build"
        print(f"Local index {action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
