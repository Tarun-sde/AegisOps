from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from apps.api.app.rag.chunking import SemanticChunker
from apps.api.app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from apps.api.app.rag.models import Document, DocumentChunk
from apps.api.app.rag.redaction import redact_document_text

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".md", ".markdown", ".txt"}


class IngestionError(Exception):
    """Base exception for document ingestion errors."""


class ValidationError(IngestionError):
    """Raised when file format, filename, or size fails validation."""


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and null bytes."""
    clean = os.path.basename(filename)
    clean = re.sub(r"[\x00-\x1f\x7f/\\]", "", clean)
    clean = re.sub(r"\.\.+", ".", clean)
    if not clean or clean.startswith("."):
        clean = f"runbook_{clean.lstrip('.')}"
    return clean[:250]


class DocumentIngestionService:
    """Service managing document validation, secret redaction, semantic chunking, and embedding."""

    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider | None = None,
        chunker: SemanticChunker | None = None,
    ) -> None:
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.chunker = chunker or SemanticChunker()
        self.is_postgres = db.bind.dialect.name == "postgresql" if db.bind else False

    def validate_file(self, filename: str, content_bytes: bytes) -> tuple[str, str]:
        """Validate filename, size, and extract content type."""
        if not content_bytes or not content_bytes.strip():
            raise ValidationError("File content cannot be empty")
        if len(content_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValidationError(f"File size ({len(content_bytes)} bytes) exceeds 5MB limit")

        sanitized = sanitize_filename(filename)
        _, ext = os.path.splitext(sanitized.lower())
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: {allowed}")

        content_type = "text/markdown" if ext in (".md", ".markdown") else "text/plain"
        return sanitized, content_type

    def create_pending_document(
        self,
        organization_id: uuid.UUID,
        filename: str,
        content: str,
        service_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
        title: str | None = None,
    ) -> Document:
        """Create a pending document row and determine version number."""
        clean_filename, content_type = self.validate_file(filename, content.encode("utf-8"))
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Extract title from markdown if not provided
        doc_title = title
        if not doc_title:
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if title_match:
                doc_title = title_match.group(1).strip()
            else:
                base_name = os.path.splitext(clean_filename)[0]
                doc_title = base_name.replace("-", " ").replace("_", " ").title()

        # Check existing versions of this document in the organization
        existing_doc = self.db.scalar(
            select(Document)
            .where(
                Document.organization_id == organization_id,
                Document.filename == clean_filename,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.version.desc())
        )

        version = (existing_doc.version + 1) if existing_doc else 1

        doc = Document(
            organization_id=organization_id,
            service_id=service_id,
            filename=clean_filename,
            title=doc_title[:250],
            content_type=content_type,
            checksum=checksum,
            version=version,
            status="PENDING",
            embedding_model_id=self.embedding_provider.model_name,
            embedding_dimension=self.embedding_provider.dimension,
            raw_content=content,
            created_by=created_by,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    async def process_document_ingestion(self, document_id: uuid.UUID) -> Document:
        """Execute the ingestion pipeline: Extract -> Redact -> Chunk -> Embed -> Index -> Ready."""
        doc = self.db.get(Document, document_id)
        if not doc:
            raise IngestionError(f"Document {document_id} not found")

        # Skip if already deleted
        if doc.deleted_at is not None:
            logger.info(f"Document {document_id} is deleted; aborting ingestion")
            return doc

        raw_text = doc.raw_content or ""
        if not raw_text.strip():
            doc.status = "FAILED"
            doc.error_code = "EMPTY_CONTENT"
            doc.error_message = "Document body contains no readable text"
            self.db.commit()
            return doc

        try:
            # 1. State: VALIDATING & EXTRACTING
            doc.status = "EXTRACTING"
            self.db.commit()

            # 2. State: REDACTING
            doc.status = "REDACTING"
            self.db.commit()
            redaction_res = redact_document_text(raw_text)
            clean_text = redaction_res.clean_text

            # 3. State: CHUNKING
            doc.status = "CHUNKING"
            self.db.commit()
            chunks = self.chunker.chunk_document(clean_text, document_title=doc.title)
            if not chunks:
                doc.status = "FAILED"
                doc.error_code = "NO_CHUNKS"
                doc.error_message = "Semantic chunker produced zero chunks from document"
                self.db.commit()
                return doc

            # 4. State: EMBEDDING
            doc.status = "EMBEDDING"
            self.db.commit()
            chunk_texts = [c.content for c in chunks]
            vectors = await self.embedding_provider.embed_documents(chunk_texts)

            if len(vectors) != len(chunks):
                raise IngestionError(
                    f"Embedding count ({len(vectors)}) mismatch with chunk count ({len(chunks)})"
                )

            # 5. State: INDEXING
            doc.status = "INDEXING"
            self.db.commit()

            # Remove previous chunks for this document (e.g. on reindex)
            self.db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()

            chunk_records: list[DocumentChunk] = []
            for chunk_meta, vec in zip(chunks, vectors, strict=True):
                chunk_record = DocumentChunk(
                    document_id=doc.id,
                    organization_id=doc.organization_id,
                    service_id=doc.service_id,
                    document_version=doc.version,
                    chunk_index=chunk_meta.chunk_index,
                    section_title=chunk_meta.section_title,
                    section_path=chunk_meta.section_path,
                    content=chunk_meta.content,
                    content_hash=chunk_meta.content_hash,
                    token_count=chunk_meta.token_count,
                    embedding=vec,
                )
                chunk_records.append(chunk_record)

            self.db.add_all(chunk_records)
            self.db.flush()

            # Populate PostgreSQL tsvector search_vector column if on PostgreSQL
            if self.is_postgres:
                self.db.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.document_id == doc.id)
                    .values(search_vector=func.to_tsvector("english", DocumentChunk.content))
                )

            # 6. State: READY
            doc.status = "READY"
            doc.indexed_at = datetime.now(UTC)
            doc.error_code = None
            doc.error_message = None
            self.db.commit()
            self.db.refresh(doc)
            logger.info(
                f"Document {doc.id} ('{doc.filename}' v{doc.version}) "
                f"successfully indexed with {len(chunks)} chunks"
            )
            return doc

        except Exception as exc:
            logger.exception(f"Document ingestion failed for {document_id}: {exc}")
            doc.status = "FAILED"
            doc.error_code = "INGESTION_ERROR"
            doc.error_message = str(exc)[:990]
            self.db.commit()
            return doc

    async def ingest_document(self, document_id: uuid.UUID) -> Document:
        """Alias for process_document_ingestion."""
        return await self.process_document_ingestion(document_id)

    def soft_delete_document(self, document_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
        """Soft delete document, removing it from active search indexes."""
        doc = self.db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id,
            )
        )
        if not doc or doc.deleted_at is not None:
            return False

        doc.deleted_at = datetime.now(UTC)
        self.db.commit()
        logger.info(f"Document {document_id} marked deleted at {doc.deleted_at}")
        return True
