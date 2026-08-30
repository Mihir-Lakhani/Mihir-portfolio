"""Explicit admin command for indexing the approved public Gemini knowledge base."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import RagConfigurationError, RagSettings  # noqa: E402
from rag.gemini import create_gemini_client  # noqa: E402
from rag.ingestion import (  # noqa: E402
    GEMINI_EMBEDDING_MODEL,
    build_ingestion_plan,
    ingest_plan,
)
from rag.sources import SourceRegistry  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index only the approved public portfolio knowledge sources into Gemini File Search."
    )
    parser.add_argument(
        "--file-search-store-id",
        help="Existing Gemini File Search store ID. Defaults to RAG_GEMINI_FILE_SEARCH_STORE_ID.",
    )
    parser.add_argument(
        "--create-file-search-store",
        action="store_true",
        help="Create a new clean Gemini File Search store before indexing sources.",
    )
    parser.add_argument(
        "--name",
        default="mihir-portfolio-public-knowledge",
        help="Display name used only with --create-file-search-store.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List approved files and hashes without contacting Gemini.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print scrubbed provider diagnostics for this local admin command only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    knowledge_root = PROJECT_ROOT / "knowledge"
    registry = SourceRegistry.from_file(knowledge_root / "sources.json")
    plan = build_ingestion_plan(knowledge_root, registry)

    print("Approved public sources:")
    for item in plan:
        print(f"- {item.source.id}: {item.path.relative_to(PROJECT_ROOT)} ({item.sha256[:12]})")

    if args.dry_run:
        print("Dry run complete. No documents were uploaded.")
        return 0

    settings = RagSettings.from_environment()
    if not settings.gemini_api_key:
        raise RagConfigurationError("GEMINI_API_KEY is required for ingestion.")
    client = create_gemini_client(settings)
    file_search_store_id = args.file_search_store_id or settings.file_search_store_id
    try:
        if args.create_file_search_store:
            store = client.file_search_stores.create(
                config={
                    "display_name": args.name,
                    "embedding_model": GEMINI_EMBEDDING_MODEL,
                }
            )
            file_search_store_id = getattr(store, "name", None)
            if not isinstance(file_search_store_id, str) or not file_search_store_id:
                raise RagConfigurationError("Gemini did not return a File Search store ID.")
            print(f"Created Gemini File Search store: {file_search_store_id}")
            print(
                "Set RAG_GEMINI_FILE_SEARCH_STORE_ID to this value in the server environment "
                "before starting Flask."
            )
        elif not file_search_store_id:
            raise RagConfigurationError(
                "Set RAG_GEMINI_FILE_SEARCH_STORE_ID, pass --file-search-store-id, or use "
                "--create-file-search-store."
            )

        state_path = PROJECT_ROOT / "instance" / "rag_gemini_ingestion_state.json"
        uploaded, skipped = ingest_plan(
            client,
            file_search_store_id,
            plan,
            state_path,
            debug=args.debug,
        )
        print(
            f"Ingestion complete. Store: {file_search_store_id}. "
            f"Uploaded: {uploaded}; unchanged and skipped: {skipped}."
        )
        return 0
    finally:
        closer = getattr(client, "close", None)
        if callable(closer):
            closer()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RagConfigurationError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
