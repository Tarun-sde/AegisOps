import asyncio
import logging
import os
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from agents.incident_investigator.agent import run_investigation_agent
from agents.incident_investigator.tools.gateway import ReadOnlyToolGateway
from apps.api.app.models import HypothesisRecord, Incident, InvestigationRun
from apps.api.app.outbox.service import create_outbox_event
from apps.api.app.schemas import Scope

logger = logging.getLogger(__name__)


def execute_investigation(
    run_id: UUID,
    db: Session,
    *,
    execution_mode: str | None = None,
    use_live_model: bool = False,
    scenario: str = "supported",
) -> InvestigationRun:
    """Execute the end-to-end investigation run lifecycle with state transitions and persistence."""
    run = db.get(InvestigationRun, run_id)
    if not run:
        raise ValueError(f"Investigation run {run_id} not found")

    # Idempotency check: only QUEUED runs may be executed
    if run.status != "QUEUED":
        logger.info(
            f"Investigation run {run_id} is in status {run.status}; skipping duplicate execution"
        )
        return run

    incident = db.get(Incident, run.incident_id)
    if not incident:
        run.status = "FAILED"
        run.error_message = f"Associated incident {run.incident_id} not found"
        run.completed_at = datetime.now(UTC)
        db.commit()
        return run

    mode = (
        execution_mode
        or getattr(run, "execution_mode", None)
        or os.environ.get("AEGISOPS_AGENT_MODE", ("live" if use_live_model else "offline"))
    ).lower()
    run.execution_mode = mode
    run.provider = "gemini" if mode == "live" else "offline"

    try:
        # 1. Collecting Context
        run.status = "COLLECTING_CONTEXT"
        run.started_at = datetime.now(UTC)
        db.commit()

        scope = Scope(
            organization_id=run.organization_id,
            service_id=run.service_id,
            run_id=run.id,
        )
        gateway = ReadOnlyToolGateway(
            scope=scope,
            incident=incident,
            run_record=run,
            db_session=db,
        )

        # 2. Investigating
        run.status = "INVESTIGATING"
        db.commit()

        result = asyncio.run(
            run_investigation_agent(
                gateway,
                model_name=run.model,
                scenario=scenario,
                execution_mode=mode,
            )
        )

        # 3. Validating
        run.status = "VALIDATING"
        db.commit()

        # 4. Persisting Hypotheses & Terminal State
        for h in result.hypotheses:
            h_record = HypothesisRecord(
                run_id=run.id,
                cause=h.cause,
                confidence=h.confidence,
                supporting_evidence=[
                    item.model_dump(mode="json") for item in h.supporting_evidence
                ],
                contradicting_evidence_ids=h.contradicting_evidence_ids,
                unverified_assumptions=h.unverified_assumptions,
                next_check=h.next_check,
            )
            db.add(h_record)

        run.summary = result.summary
        run.missing_evidence = result.missing_evidence
        run.limitations = result.limitations
        run.suggested_actions = result.suggested_action_catalog_ids
        run.status = "COMPLETE" if result.status == "complete" else "INCONCLUSIVE"
        top_hypothesis = result.hypotheses[0] if result.hypotheses else None
        create_outbox_event(
            db,
            organization_id=run.organization_id,
            aggregate_type="investigation",
            aggregate_id=str(run.id),
            event_type="investigation.completed",
            payload={
                "run_id": str(run.id),
                "incident_id": str(run.incident_id),
                "service_id": str(run.service_id),
                "status": run.status,
                "summary": run.summary,
                "top_hypothesis": top_hypothesis.cause if top_hypothesis else None,
                "evidence_count": (
                    len(result.hypotheses[0].supporting_evidence) if top_hypothesis else 0
                ),
            },
            idempotency_key=f"outbox:investigation_completed:{run.id}",
        )

        db.commit()
        db.refresh(run)
        return run

    except Exception as err:
        logger.exception(f"Investigation run {run_id} failed: {err}")
        run.status = "FAILED"
        run.error_message = str(err)
        run.completed_at = datetime.now(UTC)

        try:
            create_outbox_event(
                db,
                organization_id=run.organization_id,
                aggregate_type="investigation",
                aggregate_id=str(run.id),
                event_type="investigation.completed",
                payload={
                    "run_id": str(run.id),
                    "incident_id": str(run.incident_id),
                    "service_id": str(run.service_id),
                    "status": "FAILED",
                    "summary": f"Investigation failed: {err}",
                    "top_hypothesis": None,
                    "confidence": "none",
                    "evidence_count": 0,
                    "suggested_actions": [],
                },
                idempotency_key=f"outbox:investigation_failed:{run.id}",
            )
        except Exception as outbox_err:
            logger.warning(f"Could not record outbox event for failed run {run_id}: {outbox_err}")

        db.commit()
        db.refresh(run)
        return run
