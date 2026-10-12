import logging
from typing import Any
from uuid import UUID

from agents.incident_investigator.investigator import execute_investigation
from apps.api.app.db import SessionLocal
from apps.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="aegisops.run_investigation", bind=True, max_retries=1)  # type: ignore[untyped-decorator]
def run_investigation_task(self: Any, run_id_str: str) -> dict[str, Any]:
    """Celery background task for asynchronous investigation execution."""
    logger.info(f"Starting Celery investigation task for run {run_id_str}")
    run_id = UUID(run_id_str)
    db = SessionLocal()
    try:
        run = execute_investigation(run_id, db)
        return {
            "run_id": str(run.id),
            "status": run.status,
            "summary": run.summary,
            "tool_call_count": run.tool_call_count,
        }
    except Exception as exc:
        logger.exception(f"Unhandled error in investigation task for run {run_id_str}: {exc}")
        raise
    finally:
        db.close()


@celery_app.task(name="aegisops.ingest_document", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def ingest_document_task(self: Any, document_id_str: str) -> dict[str, Any]:
    """Celery background task for asynchronous document validation, chunking, and embedding."""
    import asyncio

    from apps.api.app.rag.service import DocumentIngestionService

    logger.info(f"Starting Celery document ingestion task for document {document_id_str}")
    doc_id = UUID(document_id_str)
    db = SessionLocal()
    try:
        service = DocumentIngestionService(db)
        doc = asyncio.run(service.process_document_ingestion(doc_id))
        return {
            "document_id": str(doc.id),
            "status": doc.status,
            "filename": doc.filename,
            "version": doc.version,
            "chunk_count": len(doc.chunks) if doc.chunks else 0,
        }
    except Exception as exc:
        logger.exception(f"Unhandled error in document ingestion task for {document_id_str}: {exc}")
        raise
    finally:
        db.close()


@celery_app.task(name="aegisops.dispatch_outbox_events", bind=True, max_retries=1)  # type: ignore[untyped-decorator]
def dispatch_outbox_events_task(self: Any, batch_size: int = 20) -> dict[str, Any]:
    """Celery background task for asynchronous outbox event claiming and dispatch."""
    from apps.api.app.outbox.dispatcher import dispatch_outbox_batch

    logger.info("Starting Celery outbox event dispatch task")
    db = SessionLocal()
    try:
        return dispatch_outbox_batch(db, batch_size=batch_size)
    except Exception as exc:
        logger.exception(f"Unhandled error in outbox dispatch task: {exc}")
        raise
    finally:
        db.close()
