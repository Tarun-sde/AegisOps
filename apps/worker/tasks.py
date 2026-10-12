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


@celery_app.task(name="aegisops.reconcile_simulation_expiry", bind=True, max_retries=1)  # type: ignore[untyped-decorator]
def reconcile_simulation_expiry_task(self: Any) -> dict[str, Any]:
    """Celery background watchdog task for reconciling expired simulation runs (DEC-318)."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.auth import TenantContext
    from apps.api.app.models import Organization, SimulationRun, User
    from apps.api.app.simulation.service import SimulationService

    logger.info("Starting Celery simulation watchdog cleanup task")
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        expired_runs = db.scalars(
            select(SimulationRun)
            .where(
                SimulationRun.status == "ACTIVE",
                SimulationRun.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
        ).all()
        cleaned_count = 0
        for run in expired_runs:
            org = db.get(Organization, run.organization_id)
            if org:
                user = User(
                    email="watchdog@system.local",
                    hashed_password="",
                    salt="",
                    name="System Watchdog",
                )
                context = TenantContext(user=user, organization=org, role="owner")
                service = SimulationService(db, context)
                if service._check_and_apply_lazy_expiry(run):
                    cleaned_count += 1
        if cleaned_count > 0:
            db.commit()
        return {"cleaned_expired_runs": cleaned_count}
    except Exception as exc:
        logger.exception(f"Unhandled error in simulation watchdog cleanup task: {exc}")
        raise
    finally:
        db.close()
