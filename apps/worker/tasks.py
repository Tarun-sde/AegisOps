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
