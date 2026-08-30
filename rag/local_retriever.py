from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .diagnostics import trace_event
from .local_index import IndexedChunk, LocalIndex, tokenize


class QueryEmbedder(Protocol):
    def embed_texts(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: IndexedChunk
    lexical_score: float
    dense_score: float
    fusion_score: float


class LocalHybridRetriever:
    """BM25 plus dense exact-vector retrieval over approved local Markdown only."""

    def __init__(self, index: LocalIndex, embedder: QueryEmbedder, top_k: int = 6):
        self._index = index
        self._embedder = embedder
        self._top_k = top_k
        self._norm_vectors = self._normalise(index.vectors)

    @property
    def index(self) -> LocalIndex:
        return self._index

    @staticmethod
    def _normalise(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-12)

    def retrieve(
        self,
        question: str,
        *,
        source_ids: tuple[str, ...] = (),
        scope: str = "relevant",
    ) -> tuple[RetrievedChunk, ...]:
        if scope == "all_projects":
            catalogue = [
                (position, chunk)
                for position, chunk in enumerate(self._index.chunks)
                if chunk.kind == "project_catalogue"
            ]
            results = tuple(
                RetrievedChunk(chunk=chunk, lexical_score=0.0, dense_score=0.0, fusion_score=1.0)
                for _, chunk in catalogue
            )
            trace_event(
                "local_retriever.catalogue_selected",
                source_count=len(results),
                chunk_count=len(results),
                selected_source_ids=",".join(item.chunk.source_id for item in results),
                selected_chunk_ids=",".join(item.chunk.chunk_id for item in results),
            )
            return results

        candidates = [
            (position, chunk)
            for position, chunk in enumerate(self._index.chunks)
            if chunk.kind == "content"
        ]
        hinted_sources = set(source_ids)
        if hinted_sources:
            candidates = [
                (position, chunk)
                for position, chunk in candidates
                if chunk.source_id in hinted_sources
            ]
        if not candidates:
            trace_event(
                "local_retriever.no_approved_candidates",
                source_hint_count=len(hinted_sources),
                source_restricted=bool(hinted_sources),
            )
            return ()
        query_tokens = tokenize(question)
        lexical_scores = self._bm25_scores(query_tokens, [chunk.tokens for _, chunk in candidates])
        query_vector = self._embedder.embed_texts([question])
        if query_vector.ndim != 2 or query_vector.shape != (1, self._norm_vectors.shape[1]):
            raise ValueError("The local embedding service returned a vector with an unexpected dimension.")
        normalized_query = self._normalise(query_vector)[0]
        dense_scores = np.array(
            [float(np.dot(self._norm_vectors[position], normalized_query)) for position, _ in candidates],
            dtype=np.float32,
        )
        lexical_ranks = self._ranks(lexical_scores)
        dense_ranks = self._ranks(dense_scores)
        ranked: list[RetrievedChunk] = []
        for index, (position, chunk) in enumerate(candidates):
            fusion = 1.0 / (60 + lexical_ranks[index]) + 1.0 / (60 + dense_ranks[index])
            if chunk.source_id in hinted_sources:
                fusion += 0.02
            ranked.append(
                RetrievedChunk(
                    chunk=chunk,
                    lexical_score=float(lexical_scores[index]),
                    dense_score=float(dense_scores[index]),
                    fusion_score=fusion,
                )
            )
        ranked.sort(key=lambda result: (-result.fusion_score, result.chunk.chunk_id))
        results = tuple(ranked[: self._top_k])
        trace_event(
            "local_retriever.completed",
            query_token_count=len(query_tokens),
            candidate_count=len(candidates),
            source_hint_count=len(hinted_sources),
            source_restricted=bool(hinted_sources),
            result_count=len(results),
            selected_source_ids=",".join(sorted({item.chunk.source_id for item in results})),
            selected_chunk_ids=",".join(item.chunk.chunk_id for item in results),
            score_bands=",".join(f"{item.fusion_score:.4f}" for item in results),
        )
        return results

    def retrieve_deep_dive(
        self,
        source_ids: tuple[str, ...],
        *,
        max_chunks: int = 24,
    ) -> tuple[RetrievedChunk, ...]:
        """Select broad, source-ordered coverage for an explicit named-source deep dive."""

        approved_source_ids = tuple(dict.fromkeys(source_ids))
        if not approved_source_ids or max_chunks < 1:
            return ()

        omitted_headings = {"public project link", "suggested assistant questions"}
        chunks_by_source = {
            source_id: [
                chunk
                for chunk in self._index.chunks
                if chunk.source_id == source_id
                and chunk.kind == "content"
                and (not chunk.heading_path or chunk.heading_path[-1].casefold() not in omitted_headings)
            ]
            for source_id in approved_source_ids
        }
        selected: list[IndexedChunk] = []
        ordinal = 0
        while len(selected) < max_chunks:
            added = False
            for source_id in approved_source_ids:
                source_chunks = chunks_by_source[source_id]
                if ordinal < len(source_chunks):
                    selected.append(source_chunks[ordinal])
                    added = True
                    if len(selected) == max_chunks:
                        break
            if not added:
                break
            ordinal += 1

        results = tuple(
            RetrievedChunk(
                chunk=chunk,
                lexical_score=0.0,
                dense_score=0.0,
                fusion_score=1.0,
            )
            for chunk in selected
        )
        trace_event(
            "local_retriever.deep_dive_selected",
            source_count=len(approved_source_ids),
            chunk_count=len(results),
            selected_source_ids=",".join(approved_source_ids),
            selected_chunk_ids=",".join(item.chunk.chunk_id for item in results),
        )
        return results

    @staticmethod
    def _ranks(scores: np.ndarray) -> np.ndarray:
        order = np.argsort(-scores, kind="stable")
        ranks = np.empty(len(scores), dtype=np.int32)
        ranks[order] = np.arange(1, len(scores) + 1)
        return ranks

    @staticmethod
    def _bm25_scores(query_tokens: tuple[str, ...], documents: list[tuple[str, ...]]) -> np.ndarray:
        if not query_tokens or not documents:
            return np.zeros(len(documents), dtype=np.float32)
        document_count = len(documents)
        document_lengths = np.array([len(document) for document in documents], dtype=np.float32)
        average_length = max(float(document_lengths.mean()), 1.0)
        document_frequency: dict[str, int] = {}
        for document in documents:
            for token in set(document):
                document_frequency[token] = document_frequency.get(token, 0) + 1
        scores = np.zeros(document_count, dtype=np.float32)
        k1 = 1.2
        b = 0.75
        for token in set(query_tokens):
            frequency = document_frequency.get(token)
            if not frequency:
                continue
            idf = math.log(1 + (document_count - frequency + 0.5) / (frequency + 0.5))
            for position, document in enumerate(documents):
                term_frequency = document.count(token)
                if not term_frequency:
                    continue
                denominator = term_frequency + k1 * (
                    1 - b + b * document_lengths[position] / average_length
                )
                scores[position] += idf * (term_frequency * (k1 + 1) / denominator)
        return scores
