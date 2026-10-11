from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import random
import re
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-004"
DEFAULT_EMBEDDING_DIMENSION = 768
DEFAULT_BATCH_SIZE = 16
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RETRIES = 3


class EmbeddingError(Exception):
    """Base exception for embedding provider errors."""


class EmbeddingDimensionMismatchError(EmbeddingError):
    """Raised when provider returns vectors with unexpected dimensions."""


class EmbeddingRateLimitError(EmbeddingError):
    """Raised when embedding provider returns 429 Too Many Requests."""


class EmbeddingProvider(ABC):
    """Abstract provider interface for document and query embeddings."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name/ID of the active embedding model."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of produced vectors."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized vector embeddings for a list of document chunks."""

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Generate a normalized vector embedding for a search query."""

    def validate_vector(self, vector: list[float], context: str = "") -> list[float]:
        """Verify vector integrity: correct dimension, finite floats, non-empty."""
        if not vector or len(vector) != self.dimension:
            raise EmbeddingDimensionMismatchError(
                f"Vector dimension mismatch ({context}): "
                f"expected {self.dimension}, got {len(vector)}"
            )
        for i, val in enumerate(vector):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise EmbeddingError(f"Invalid non-finite float at index {i} in vector ({context})")
        return vector


class DeterministicHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic offline embedding provider generating reproducible unit vectors.

    Uses token hashing and L2 normalization to allow offline unit, integration,
    and evaluation tests without paid inference, rate limits, or network dependencies.
    """

    def __init__(
        self,
        model_name: str = "deterministic-hash-768",
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_text_to_vector(self, text: str) -> list[float]:
        if not text.strip():
            # Return zero vector with slight base bias normalized
            raw = [0.0] * self._dimension
            raw[0] = 1.0
            return raw

        vec = [0.0] * self._dimension
        words = re.findall(r"\w+", text.lower())

        if not words:
            words = [text.strip()]

        for word in words:
            # Deterministic hash of each token
            h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
            # Project onto 4 pseudo-random feature indices
            for shift in range(4):
                idx = (h >> (shift * 16)) % self._dimension
                sign = 1.0 if ((h >> (shift * 16 + 8)) & 1) else -1.0
                vec[idx] += sign

        # Global document context hash
        doc_h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        for i in range(min(16, self._dimension)):
            idx = (doc_h + i * 37) % self._dimension
            vec[idx] += 0.5

        # L2 Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        else:
            vec[0] = 1.0

        return vec

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = [self._hash_text_to_vector(t) for t in texts]
        for v in vectors:
            self.validate_vector(v, "embed_documents")
        return vectors

    async def embed_query(self, query: str) -> list[float]:
        vec = self._hash_text_to_vector(query)
        self.validate_vector(vec, "embed_query")
        return vec


class GoogleGenAIEmbeddingProvider(EmbeddingProvider):
    """Live embedding provider utilizing Google GenAI API (text-embedding-004)."""

    def __init__(
        self,
        api_key: str,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        batch_size: int = DEFAULT_BATCH_SIZE,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.api_key = api_key
        self._model_name = model_name
        self._dimension = dimension
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_retries = max_retries

        from google import genai
        from google.genai import types

        self.client = genai.Client(
            api_key=api_key,
            vertexai=False,
            http_options=types.HttpOptions(
                base_url="https://generativelanguage.googleapis.com",
                timeout=int(self.timeout * 1000),
            ),
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _embed_batch_with_retry(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        from google.genai import types

        config = types.EmbedContentConfig(
            task_type=types.TaskType.RETRIEVAL_DOCUMENT
            if task_type == "RETRIEVAL_DOCUMENT"
            else types.TaskType.RETRIEVAL_QUERY,
            output_dimensionality=self._dimension,
        )

        for attempt in range(self.max_retries):
            try:
                # Wrap synchronous client call in thread pool for async compatibility
                response = await asyncio.to_thread(
                    self.client.models.embed_content,
                    model=self._model_name,
                    contents=texts,
                    config=config,
                )

                if not response or not response.embeddings:
                    raise EmbeddingError(f"Empty embedding response from {self._model_name}")

                results: list[list[float]] = []
                for emb in response.embeddings:
                    vec = list(emb.values or [])
                    self.validate_vector(vec, f"batch attempt {attempt}")
                    results.append(vec)

                return results

            except Exception as exc:
                err_str = str(exc)
                if (
                    "429" in err_str
                    or "quota" in err_str.lower()
                    or "resource_exhausted" in err_str.lower()
                ):
                    if attempt < self.max_retries - 1:
                        backoff = (2**attempt) + random.uniform(0.1, 0.5)
                        logger.warning(
                            f"Embedding rate limit (429). Retrying in {backoff:.2f}s "
                            f"(attempt {attempt + 1})"
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise EmbeddingRateLimitError(
                        f"Embedding rate limit exceeded after {self.max_retries} attempts: {exc}"
                    ) from exc

                if attempt < self.max_retries - 1:
                    backoff = (1.5**attempt) + random.uniform(0.05, 0.2)
                    logger.warning(
                        f"Embedding error: {exc}. Retrying in {backoff:.2f}s "
                        f"(attempt {attempt + 1})"
                    )
                    await asyncio.sleep(backoff)
                    continue

                raise EmbeddingError(f"Embedding call failed: {exc}") from exc

        raise EmbeddingError(f"Embedding failed after {self.max_retries} retries")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_vectors = await self._embed_batch_with_retry(batch, "RETRIEVAL_DOCUMENT")
            all_vectors.extend(batch_vectors)

        return all_vectors

    async def embed_query(self, query: str) -> list[float]:
        results = await self._embed_batch_with_retry([query], "RETRIEVAL_QUERY")
        return results[0]


def get_embedding_provider() -> EmbeddingProvider:
    """Factory creating configured embedding provider based on environment variables."""
    provider_type = os.environ.get("AEGISOPS_EMBEDDING_PROVIDER", "").lower()
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    model_name = os.environ.get("AEGISOPS_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    dimension = int(
        os.environ.get("AEGISOPS_EMBEDDING_DIMENSION", str(DEFAULT_EMBEDDING_DIMENSION))
    )

    is_live = provider_type == "live" or (
        not provider_type and bool(api_key) and os.environ.get("AEGISOPS_AGENT_MODE") == "live"
    )

    if is_live:
        if not api_key:
            raise ValueError(
                "Live embedding mode requested (AEGISOPS_EMBEDDING_PROVIDER=live) "
                "but GOOGLE_API_KEY is not set."
            )
        batch_size = int(os.environ.get("AEGISOPS_EMBEDDING_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
        timeout = float(os.environ.get("AEGISOPS_EMBEDDING_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
        max_retries = int(
            os.environ.get("AEGISOPS_EMBEDDING_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))
        )
        return GoogleGenAIEmbeddingProvider(
            api_key=api_key,
            model_name=model_name,
            dimension=dimension,
            batch_size=batch_size,
            timeout=timeout,
            max_retries=max_retries,
        )

    # Default to deterministic offline hash provider
    return DeterministicHashEmbeddingProvider(
        model_name="deterministic-hash-768",
        dimension=dimension,
    )
