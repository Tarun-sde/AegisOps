from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from apps.api.app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from apps.api.app.rag.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60
DEFAULT_RETRIEVAL_LIMIT = 5
MAX_RETRIEVAL_LIMIT = 20


@dataclass
class RetrievedChunk:
    evidence_id: str
    document_id: str
    chunk_id: str
    document_version: int
    title: str
    section_title: str
    section_path: str
    content: str
    content_hash: str
    relevance_score: float
    source_type: str = "runbook"


@dataclass
class HybridRetrievalResult:
    query: str
    mode: str  # "hybrid" | "vector" | "keyword"
    results: list[RetrievedChunk]
    total_candidates: int


def calculate_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def reciprocal_rank_fusion(
    vector_ranked: list[uuid.UUID],
    keyword_ranked: list[uuid.UUID],
    k: int = DEFAULT_RRF_K,
) -> list[tuple[uuid.UUID, float]]:
    """Compute Reciprocal Rank Fusion (RRF) scores across vector and keyword lists.

    RRF(d) = sum(1 / (k + rank_i(d)))
    Returns a sorted list of (chunk_id, rrf_score) descending.
    """
    scores: dict[uuid.UUID, float] = {}

    for rank, chunk_id in enumerate(vector_ranked):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank + 1))

    for rank, chunk_id in enumerate(keyword_ranked):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + (1.0 / (k + rank + 1))

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class HybridRetrievalService:
    """Tenant-scoped hybrid retrieval service combining pgvector similarity with lexical search."""

    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider | None = None,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.rrf_k = rrf_k
        self.is_postgres = db.bind.dialect.name == "postgresql" if db.bind else False

    async def search(
        self,
        organization_id: uuid.UUID,
        query: str,
        service_id: uuid.UUID | None = None,
        limit: int = DEFAULT_RETRIEVAL_LIMIT,
        mode: str = "hybrid",  # hybrid | vector | keyword
    ) -> HybridRetrievalResult:
        """Execute tenant-scoped hybrid retrieval returning ranked chunks with citations."""
        limit = max(1, min(limit, MAX_RETRIEVAL_LIMIT))
        clean_query = query.strip()

        if not clean_query:
            return HybridRetrievalResult(
                query=query,
                mode=mode,
                results=[],
                total_candidates=0,
            )

        # Base filter: tenant isolation, ready status, not soft-deleted
        base_conditions = [
            DocumentChunk.organization_id == organization_id,
            Document.status == "READY",
            Document.deleted_at.is_(None),
        ]
        if service_id is not None:
            # Match service-specific or service-agnostic documentation
            base_conditions.append(
                or_(DocumentChunk.service_id == service_id, DocumentChunk.service_id.is_(None))
            )

        # 1. Vector Search
        vector_ranked_ids: list[uuid.UUID] = []
        query_vector: list[float] | None = None
        vector_scores: dict[uuid.UUID, float] = {}

        if mode in ("hybrid", "vector"):
            try:
                query_vector = await self.embedding_provider.embed_query(clean_query)
                vector_ranked_ids, vector_scores = self._execute_vector_search(
                    base_conditions, query_vector, candidate_limit=limit * 3
                )
            except Exception as exc:
                logger.warning(
                    f"Vector search embedding failed ({exc}). Falling back to keyword search."
                )
                if mode == "vector":
                    # If strictly vector search was requested and failed, return empty with warning
                    return HybridRetrievalResult(
                        query=clean_query,
                        mode="vector_failed",
                        results=[],
                        total_candidates=0,
                    )
                mode = "keyword_fallback"

        # 2. Keyword / Lexical Search
        keyword_ranked_ids: list[uuid.UUID] = []
        if mode in ("hybrid", "keyword", "keyword_fallback"):
            keyword_ranked_ids = self._execute_keyword_search(
                base_conditions, clean_query, candidate_limit=limit * 3
            )

        # 3. Fusion & Ranking
        final_ranked_ids: list[tuple[uuid.UUID, float]] = []
        if mode == "vector":
            final_ranked_ids = [
                (cid, vector_scores.get(cid, 0.0)) for cid in vector_ranked_ids[:limit]
            ]
        elif mode in ("keyword", "keyword_fallback"):
            final_ranked_ids = [
                (cid, 1.0 / (rank + 1)) for rank, cid in enumerate(keyword_ranked_ids[:limit])
            ]
        else:
            # Hybrid RRF
            fused = reciprocal_rank_fusion(vector_ranked_ids, keyword_ranked_ids, k=self.rrf_k)
            final_ranked_ids = fused[:limit]

        if not final_ranked_ids:
            return HybridRetrievalResult(
                query=clean_query,
                mode=mode,
                results=[],
                total_candidates=0,
            )

        # 4. Fetch full chunk and document records
        target_ids = [item[0] for item in final_ranked_ids]
        chunks_stmt = (
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.id.in_(target_ids))
        )
        chunk_map = {c.id: (c, d) for c, d in self.db.execute(chunks_stmt).all()}

        results: list[RetrievedChunk] = []
        for chunk_id, score in final_ranked_ids:
            if chunk_id not in chunk_map:
                continue
            chunk, doc = chunk_map[chunk_id]
            ev_id = f"ev_runbook_{chunk.id.hex[:12]}"
            results.append(
                RetrievedChunk(
                    evidence_id=ev_id,
                    document_id=str(doc.id),
                    chunk_id=str(chunk.id),
                    document_version=chunk.document_version,
                    title=doc.title,
                    section_title=chunk.section_title,
                    section_path=chunk.section_path,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    relevance_score=round(score, 4),
                    source_type="runbook",
                )
            )

        return HybridRetrievalResult(
            query=clean_query,
            mode=mode,
            results=results,
            total_candidates=len(final_ranked_ids),
        )

    def _execute_vector_search(
        self,
        base_conditions: list[Any],
        query_vector: list[float],
        candidate_limit: int,
    ) -> tuple[list[uuid.UUID], dict[uuid.UUID, float]]:
        """Run vector similarity query on PostgreSQL pgvector or in-memory fallback on SQLite."""
        if self.is_postgres:
            # Native PostgreSQL pgvector cosine distance: embedding <=> query_vector
            distance_expr = DocumentChunk.embedding.cosine_distance(query_vector)
            stmt = (
                select(DocumentChunk.id, distance_expr.label("distance"))
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(and_(*base_conditions))
                .order_by("distance")
                .limit(candidate_limit)
            )
            rows = self.db.execute(stmt).all()
            ids = [row[0] for row in rows]
            scores = {row[0]: max(0.0, 1.0 - float(row[1])) for row in rows}
            return ids, scores
        else:
            # SQLite / Test environment fallback: compute cosine similarity over candidate chunks
            stmt = (
                select(DocumentChunk.id, DocumentChunk.embedding)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(and_(*base_conditions))
            )
            rows = self.db.execute(stmt).all()
            scored: list[tuple[uuid.UUID, float]] = []
            for row in rows:
                c_id, emb = row[0], row[1]
                if emb:
                    sim = calculate_cosine_similarity(query_vector, list(emb))
                    scored.append((c_id, sim))
            scored.sort(key=lambda x: x[1], reverse=True)
            top = scored[:candidate_limit]
            ids = [x[0] for x in top]
            scores = {x[0]: x[1] for x in top}
            return ids, scores

    def _execute_keyword_search(
        self,
        base_conditions: list[Any],
        query: str,
        candidate_limit: int,
    ) -> list[uuid.UUID]:
        """Run full-text search on PostgreSQL tsquery or token matching on SQLite."""
        tokens = [t.lower() for t in query.split() if len(t) >= 2]
        if not tokens:
            return []

        if self.is_postgres:
            # PostgreSQL full-text search with plainto_tsquery
            safe_query = " | ".join(tokens)
            stmt = (
                select(DocumentChunk.id)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(
                    and_(
                        *base_conditions,
                        func.to_tsvector("english", DocumentChunk.content).op("@@")(
                            func.to_tsquery("english", safe_query)
                        ),
                    )
                )
                .order_by(
                    func.ts_rank_cd(
                        func.to_tsvector("english", DocumentChunk.content),
                        func.to_tsquery("english", safe_query),
                    ).desc()
                )
                .limit(candidate_limit)
            )
            rows = self.db.execute(stmt).all()
            return [row[0] for row in rows]
        else:
            # SQLite / Test environment: rank by matching token count
            sqlite_stmt = (
                select(DocumentChunk.id, DocumentChunk.content)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(and_(*base_conditions))
            )
            sqlite_rows = self.db.execute(sqlite_stmt).all()
            scored: list[tuple[uuid.UUID, int]] = []
            for s_row in sqlite_rows:
                c_id = s_row[0]
                content = str(s_row[1])
                c_lower = content.lower()
                matches = sum(1 for t in tokens if t in c_lower)
                if matches > 0:
                    scored.append((c_id, matches))
            scored.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in scored[:candidate_limit]]
