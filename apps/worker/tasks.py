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


@celery_app.task(name="aegisops.probe_monitored_services", bind=True, max_retries=1)  # type: ignore[untyped-decorator]
def probe_monitored_services_task(self: Any = None) -> dict[str, Any]:
    """Continuous scheduled health probing of monitored applications (AUD-005, DEC-393)."""
    import os
    import time
    import urllib.request
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.auth import get_ssrf_safe_opener, validate_connector_url
    from apps.api.app.models import Incident, IncidentEvent, Service, ServiceHealthObservation

    logger.info("Starting scheduled health probing for monitored services")
    db = SessionLocal()
    allow_local = os.environ.get("AEGISOPS_ALLOW_LOCAL_CONNECTOR", "false").lower() in ("true", "1")
    probed_count = 0
    now = datetime.now(UTC)

    try:
        # Select active services with configured healthcheck and monitoring enabled
        services = db.scalars(
            select(Service).where(
                Service.is_monitored == True,  # noqa: E712
                Service.healthcheck_url.isnot(None),
                Service.status == "active",
            )
        ).all()

        for service in services:
            if not service.healthcheck_url:
                continue

            interval = service.monitoring_interval_seconds or 60
            if service.last_verified_at:
                last_v = (
                    service.last_verified_at.replace(tzinfo=UTC)
                    if service.last_verified_at.tzinfo is None
                    else service.last_verified_at
                )
                elapsed = (now - last_v).total_seconds()
                if elapsed < interval:
                    continue

            probed_count += 1
            t0 = time.perf_counter()
            success = False
            st_code = None
            error_msg = None

            try:
                validated_url = validate_connector_url(
                    service.healthcheck_url, allow_local_demo=allow_local
                )
                req = urllib.request.Request(
                    validated_url,
                    headers={"User-Agent": "AegisOps-Monitor/1.0", "Accept": "*/*"},
                )
                opener = get_ssrf_safe_opener(allow_local_demo=allow_local)
                with opener.open(req, timeout=5.0) as res:
                    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                    st_code = res.status
                    success = 200 <= st_code < 400
                    if not success:
                        error_msg = f"HTTP {st_code}"
            except Exception as exc:
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                error_msg = str(exc)[:500]

            # Update observation & state
            service.last_verified_at = now
            service.last_probe_status_code = st_code
            service.last_probe_latency_ms = latency_ms

            if success:
                service.last_success_at = now
                service.consecutive_successes += 1
                service.consecutive_failures = 0
                service.last_probe_error = None
                service.monitoring_status = "reachable"

                obs = ServiceHealthObservation(
                    service_id=service.id,
                    organization_id=service.organization_id,
                    observed_at=now,
                    status="reachable",
                    status_code=st_code,
                    latency_ms=latency_ms,
                    error_message=None,
                )
                db.add(obs)

                # Recovery Detection: resolve active monitoring incidents for this service
                import hashlib

                from apps.api.app.lifecycle import ACTIVE_INCIDENT_STATUSES

                fp = hashlib.sha256(f"healthcheck:{service.id}".encode()).hexdigest()[:32]
                active_incidents = db.scalars(
                    select(Incident).where(
                        Incident.service_id == service.id,
                        Incident.organization_id == service.organization_id,
                        Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
                        Incident.fingerprint == fp,
                    )
                ).all()
                for active_incident in active_incidents:
                    active_incident.status = "resolved"
                    active_incident.updated_at = now
                    active_incident.resolved_at = now
                    evt = IncidentEvent(
                        incident_id=active_incident.id,
                        event_type="resolved",
                        actor="system:healthcheck_monitor",
                        occurred_at=now,
                        payload={
                            "message": (
                                f"Service recovered. Healthcheck responded with HTTP {st_code} "
                                f"({latency_ms} ms)."
                            )
                        },
                    )
                    db.add(evt)
                    logger.info(
                        "Resolved outage incident %s for service %s",
                        active_incident.id,
                        service.name,
                    )
            else:
                service.consecutive_failures += 1
                service.consecutive_successes = 0
                service.last_probe_error = error_msg

                # Cold-start protection: threshold of consecutive failures before marking down
                threshold = service.failure_threshold or 3
                if service.consecutive_failures < threshold:
                    service.monitoring_status = "degraded"
                    obs_status = "degraded"
                else:
                    service.monitoring_status = "down"
                    obs_status = "down"

                    # Outage Detection: Check if active incident already exists for this service
                    import hashlib

                    from apps.api.app.lifecycle import ACTIVE_INCIDENT_STATUSES

                    fp = hashlib.sha256(f"healthcheck:{service.id}".encode()).hexdigest()[:32]
                    existing_incident = db.scalar(
                        select(Incident).where(
                            Incident.service_id == service.id,
                            Incident.organization_id == service.organization_id,
                            Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
                            Incident.fingerprint == fp,
                        )
                    )
                    if not existing_incident:
                        incident = Incident(
                            organization_id=service.organization_id,
                            service_id=service.id,
                            title=f"Service Outage: {service.name} unreachable",
                            severity="critical",
                            status="open",
                            environment=service.environment,
                            fingerprint=fp,
                            started_at=now,
                        )
                        db.add(incident)
                        try:
                            db.flush()
                            evt = IncidentEvent(
                                incident_id=incident.id,
                                event_type="created",
                                actor="system:healthcheck_monitor",
                                occurred_at=now,
                                payload={
                                    "message": (
                                        f"Outage incident automatically triggered after "
                                        f"{service.consecutive_failures} consecutive failed probes."
                                    ),
                                    "error": error_msg or "Unknown error",
                                    "healthcheck_url": service.healthcheck_url,
                                },
                            )
                            db.add(evt)
                            logger.warning(
                                "Created outage incident %s for service %s after %s failures",
                                incident.id,
                                service.name,
                                service.consecutive_failures,
                            )
                        except Exception as race_err:
                            # Unique index uq_active_incident_fingerprint prevented duplicate
                            db.rollback()
                            logger.info(
                                "Concurrent incident creation race handled for %s: %s",
                                service.name,
                                race_err,
                            )

                obs = ServiceHealthObservation(
                    service_id=service.id,
                    organization_id=service.organization_id,
                    observed_at=now,
                    status=obs_status,
                    status_code=st_code,
                    latency_ms=latency_ms,
                    error_message=error_msg,
                )
                db.add(obs)

        db.commit()
        return {"probed_services": probed_count}
    except Exception as exc:
        logger.exception(f"Unhandled error in health probing task: {exc}")
        db.rollback()
        raise
    finally:
        db.close()
