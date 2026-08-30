"""Run a local-only Gemini RAG diagnostic without exposing server secrets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import RagConfigurationError, RagSettings  # noqa: E402
from rag.diagnostics import capture_rag_trace  # noqa: E402
from rag.gemini import create_gemini_client  # noqa: E402
from rag.generator import GeminiFileSearchAnswerGenerator  # noqa: E402
from rag.ingestion import (  # noqa: E402
    _safe_provider_diagnostic,
    approved_remote_documents,
    build_ingestion_plan,
)
from rag.query_hints import ApprovedSourceQueryHints  # noqa: E402
from rag.retriever import GeminiFileSearchRetriever  # noqa: E402
from rag.sources import SourceRegistry  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the configured Gemini File Search store and run one local diagnostic query."
    )
    parser.add_argument(
        "--question",
        default="Which project uses Docker?",
        help="Public portfolio question used for the diagnostic query.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = None
    with capture_rag_trace() as trace:
        try:
            settings = RagSettings.from_environment()
            settings.require_runtime_configuration()
            client = create_gemini_client(settings)
            registry = SourceRegistry.from_file(PROJECT_ROOT / "knowledge" / "sources.json")
            query_hints = ApprovedSourceQueryHints.from_registry(
                PROJECT_ROOT / "knowledge", registry
            )
            plan = build_ingestion_plan(PROJECT_ROOT / "knowledge", registry)
            approved_documents = approved_remote_documents(client, settings.file_search_store_id, plan)
            print(f"Store validation passed: {len(approved_documents)} approved documents.")

            generated = GeminiFileSearchAnswerGenerator(
                GeminiFileSearchRetriever(client, settings), query_hints.for_question
            ).answer(args.question)
            print(f"Interaction completed: answerable={generated.answerable}.")
            print(f"File citations returned: {len(generated.file_citations)}.")
            exit_code = 0
        except RagConfigurationError as exc:
            print(f"RAG configuration or store validation failed: {exc}", file=sys.stderr)
            exit_code = 2
        except Exception as exc:
            print(
                "Gemini interaction failed: " + _safe_provider_diagnostic(exc),
                file=sys.stderr,
            )
            exit_code = 3
        finally:
            closer = getattr(client, "close", None)
            if callable(closer):
                closer()

        print("Function trace (no prompt, answer, or secret values):")
        for event in trace.events:
            print("- " + json.dumps(event, sort_keys=True))
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
