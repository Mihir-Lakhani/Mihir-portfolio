from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.config import RagConfigurationError, RagSettings
from rag.local_index import load_local_index, validate_local_index
from rag.local_retriever import LocalHybridRetriever
from rag.ollama import OllamaEmbedder
from rag.query_hints import ApprovedSourceQueryHints
from rag.sources import SourceRegistry


def _index_directory(settings: RagSettings) -> Path:
    directory = Path(settings.local_index_directory)
    return directory if directory.is_absolute() else PROJECT_ROOT / directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate approved-source retrieval before any Gemini answer evaluation."
    )
    parser.add_argument("--case", dest="case_ids", action="append", default=[])
    args = parser.parse_args()

    try:
        settings = RagSettings.from_environment()
        registry = SourceRegistry.from_file(PROJECT_ROOT / "knowledge" / "sources.json")
        index = load_local_index(_index_directory(settings))
        validate_local_index(
            index, PROJECT_ROOT / "knowledge", registry, settings.ollama_embedding_model
        )
        retriever = LocalHybridRetriever(
            index,
            OllamaEmbedder(
                settings.ollama_base_url,
                settings.ollama_embedding_model,
                timeout_seconds=settings.effective_provider_timeout_seconds,
            ),
            settings.local_top_k,
        )
        hints = ApprovedSourceQueryHints.from_registry(PROJECT_ROOT / "knowledge", registry)
        cases = [
            json.loads(line)
            for line in (PROJECT_ROOT / "evals" / "portfolio_eval.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]
    except RagConfigurationError as exc:
        print(f"Local retrieval evaluation failed: {exc}", file=sys.stderr)
        return 1
    selected_cases = [case for case in cases if not args.case_ids or case["id"] in args.case_ids]
    missing_case_ids = set(args.case_ids) - {case["id"] for case in selected_cases}
    if missing_case_ids:
        parser.error("Unknown evaluation case: " + ", ".join(sorted(missing_case_ids)))

    failures: list[str] = []
    for case in selected_cases:
        if not case["should_answer"]:
            continue
        query = case.get("retrieval_query", case["question"])
        scope = case.get("retrieval_scope", "relevant")
        results = retriever.retrieve(
            query,
            source_ids=hints.source_ids_for_question(query),
            scope=scope,
        )
        actual_source_ids = {result.chunk.source_id for result in results}
        expected_source_ids = set(case["expected_source_ids"])
        missing_sources = expected_source_ids - actual_source_ids
        if missing_sources:
            failures.append(
                f"{case['id']}: missing expected source IDs {', '.join(sorted(missing_sources))}"
            )
        else:
            print(f"PASS {case['id']}: {', '.join(sorted(actual_source_ids))}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print(f"Local retrieval evaluation passed for {len(selected_cases)} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
