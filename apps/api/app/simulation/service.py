"""Simulation lifecycle service for Phase 7.

Enforces:
- Deterministic 6-scenario catalog (DEC-316).
- Database-enforced single active simulation per service (DEC-317).
- Watchdog lease & on-access lazy expiry (DEC-318).
- Atomic outbox event publication (DEC-327).
- Server-side RBAC and tenant isolation (DEC-328).
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from apps.api.app.auth import TenantContext, log_audit_event
from apps.api.app.models import Service, SimulationEvent, SimulationRun
from apps.api.app.outbox.service import create_outbox_event
from apps.api.app.simulation.scenarios import SCENARIO_CATALOG, get_scenario

logger = logging.getLogger(__name__)


class SimulationError(Exception):
    """Base exception for simulation lab operations."""


class SimulationNotFoundError(SimulationError):
    pass


class SimulationPermissionDeniedError(SimulationError):
    pass


class SimulationStateConflictError(SimulationError):
    pass


class SimulationService:
    def __init__(self, db: Session, context: TenantContext) -> None:
        self.db = db
        self.context = context
        self.shop_api_url = os.environ.get(
            "AEGISOPS_SHOP_API_URL",
            "http://127.0.0.1:3001" if not os.environ.get("IN_DOCKER") else "http://shop-api:3001",
        )
        self.fault_secret = os.environ.get(
            "AEGISOPS_DEMO_FAULT_SECRET", "aegisops-demo-fault-secret"
        )

    def _call_shop_api(
        self, endpoint: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Dispatches HTTP request to shop-api fault control endpoints."""
        url = f"{self.shop_api_url.rstrip('/')}{endpoint}"
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-demo-fault-secret": self.fault_secret,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
                return data
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            logger.warning(f"Could not reach shop-api at {url}: {err}")
            return {"status": "unreachable", "error": str(err)}

    def _check_and_apply_lazy_expiry(self, run: SimulationRun) -> bool:
        """Lazily cleans up active run if past expires_at."""
        now = datetime.now(UTC)
        expires_at = run.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if run.status == "ACTIVE" and expires_at <= now:
            logger.info(
                f"SimulationRun {run.id} has expired (TTL reached). Triggering cleanup reset."
            )
            self._call_shop_api("/fault/reset")
            run.status = "EXPIRED"
            run.cleanup_status = "CLEANED"
            run.ended_at = now

            event = SimulationEvent(
                run_id=run.id,
                organization_id=run.organization_id,
                event_type="simulation.expired",
                actor="system:watchdog",
                payload={
                    "reason": "Maximum scenario duration expired",
                    "scenario_id": run.scenario_id,
                },
            )
            self.db.add(event)
            create_outbox_event(
                self.db,
                organization_id=run.organization_id,
                aggregate_type="simulation_run",
                aggregate_id=str(run.id),
                event_type="simulation.expired",
                payload={
                    "run_id": str(run.id),
                    "scenario_id": run.scenario_id,
                    "status": "EXPIRED",
                },
                idempotency_key=f"outbox:simulation_expired:{run.id}",
            )
            return True
        return False

    def start_simulation(
        self,
        scenario_id: str,
        service_id: uuid.UUID | None = None,
        environment: str = "staging",
        seed: str | None = None,
        ip_address: str | None = None,
    ) -> SimulationRun:
        """Start a predefined failure scenario on the target demo service."""
        # 1. RBAC check: admin or owner only (DEC-328, DEC-329)
        if not self.context.can("admin"):
            raise SimulationPermissionDeniedError(
                f"Role '{self.context.role}' cannot start simulations (requires admin or owner)."
            )

        # 2. Environment check: staging or development only (Rule 1, DEC-322)
        if environment == "production":
            raise ValueError("Simulation fault activation is strictly forbidden in production.")

        # 3. Scenario catalog validation (DEC-316)
        scenario = get_scenario(scenario_id)
        if not scenario:
            allowed = sorted(SCENARIO_CATALOG.keys())
            raise ValueError(f"Scenario '{scenario_id}' is not recognized. Allowed: {allowed}")

        # 4. Resolve target service
        if service_id:
            service = self.db.scalar(
                select(Service).where(
                    Service.id == service_id,
                    Service.organization_id == self.context.organization.id,
                )
            )
            if not service:
                raise SimulationNotFoundError(
                    f"Service {service_id} not found in active organization"
                )
        else:
            service = self.db.scalar(
                select(Service).where(
                    Service.organization_id == self.context.organization.id,
                    Service.name == scenario.affected_service,
                )
            )
            if not service:
                # Fallback to any active service in tenant
                service = self.db.scalar(
                    select(Service).where(Service.organization_id == self.context.organization.id)
                )
            if not service:
                raise SimulationNotFoundError("No services configured for active organization.")

        # 5. Concurrency check: Single active simulation per service (DEC-317)
        active_runs = self.db.scalars(
            select(SimulationRun).where(
                SimulationRun.organization_id == self.context.organization.id,
                SimulationRun.service_id == service.id,
                SimulationRun.status == "ACTIVE",
            )
        ).all()

        modified = False
        for active_run in active_runs:
            if self._check_and_apply_lazy_expiry(active_run):
                modified = True
            else:
                if modified:
                    self.db.commit()
                raise SimulationStateConflictError(
                    f"Simulation '{active_run.scenario_id}' (run {active_run.id}) "
                    f"is already ACTIVE on service {service.name}."
                )

        if modified:
            self.db.commit()

        # 6. Initialize SimulationRun record
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=scenario.maximum_duration_seconds)
        run = SimulationRun(
            organization_id=self.context.organization.id,
            scenario_id=scenario.scenario_id,
            service_id=service.id,
            environment=environment,
            status="ACTIVE",
            scenario_version="1.0.0",
            seed=seed,
            started_by_id=self.context.user.id,
            started_at=now,
            expires_at=expires_at,
            expected_cause=scenario.expected_cause_category,
            initial_release=service.current_version or "0.1.0",
            affected_release="0.1.1-buggy"
            if scenario_id == "S04_BROKEN_RELEASE"
            else (service.current_version or "0.1.0"),
            fault_configuration={
                "scenario_id": scenario_id,
                "seed": seed,
                "fault_type": scenario.fault_type,
            },
            cleanup_status="PENDING",
        )
        self.db.add(run)
        self.db.flush()

        # 7. Dispatch fault activation to shop-api (DEC-319)
        inject_payload: dict[str, Any] = {"scenario": scenario_id}
        if scenario_id == "S02_SLOW_DB_QUERIES":
            inject_payload["delay_ms"] = 800
        elif scenario_id == "S06_SLOW_DOWNSTREAM":
            inject_payload["delay_ms"] = 1200
        elif scenario_id == "S04_BROKEN_RELEASE":
            inject_payload["version"] = "0.1.1-buggy"
            inject_payload["commit_sha"] = "badf00d1234567890abcdef1234567890abcdef1"

        dispatch_res = self._call_shop_api("/fault/inject", inject_payload)

        # 8. Record timeline events & outbox events (DEC-327)
        event_start = SimulationEvent(
            run_id=run.id,
            organization_id=self.context.organization.id,
            event_type="simulation.started",
            actor=str(self.context.user.email),
            payload={
                "scenario_id": scenario_id,
                "environment": environment,
                "dispatch": dispatch_res,
            },
        )
        event_active = SimulationEvent(
            run_id=run.id,
            organization_id=self.context.organization.id,
            event_type="simulation.fault_activated",
            actor=str(self.context.user.email),
            payload={"scenario_id": scenario_id, "fault_type": scenario.fault_type},
        )
        self.db.add(event_start)
        self.db.add(event_active)

        create_outbox_event(
            self.db,
            organization_id=self.context.organization.id,
            aggregate_type="simulation_run",
            aggregate_id=str(run.id),
            event_type="simulation.started",
            payload={
                "run_id": str(run.id),
                "scenario_id": scenario_id,
                "service_id": str(service.id),
                "environment": environment,
                "expires_at": expires_at.isoformat(),
            },
            idempotency_key=f"outbox:simulation_started:{run.id}",
        )

        log_audit_event(
            self.db,
            organization_id=self.context.organization.id,
            actor_id=self.context.user.id,
            resource_type="simulation_run",
            resource_id=str(run.id),
            action="simulation_started",
            result="success",
            metadata={"scenario_id": scenario_id, "environment": environment},
            ip_address=ip_address,
        )

        self.db.commit()
        self.db.refresh(run)
        return run

    def reset_simulation(
        self,
        run_id: uuid.UUID,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> SimulationRun:
        """Reset active simulation fault and mark run completed."""
        # 1. RBAC check
        if not self.context.can("admin"):
            raise SimulationPermissionDeniedError(
                f"Role '{self.context.role}' cannot reset simulations (requires admin or owner)."
            )

        # 2. Tenant scoping
        run = self.db.scalar(
            select(SimulationRun)
            .options(selectinload(SimulationRun.events))
            .where(
                SimulationRun.id == run_id,
                SimulationRun.organization_id == self.context.organization.id,
            )
        )
        if not run:
            raise SimulationNotFoundError(
                f"SimulationRun {run_id} not found in active organization"
            )

        # 3. Dispatch reset to shop-api (DEC-319)
        self._call_shop_api("/fault/reset")

        now = datetime.now(UTC)
        run.status = "COMPLETED"
        run.cleanup_status = "CLEANED"
        run.ended_at = now

        event_reset = SimulationEvent(
            run_id=run.id,
            organization_id=self.context.organization.id,
            event_type="simulation.reset",
            actor=str(self.context.user.email),
            payload={"reason": reason or "Operator manual reset", "ended_at": now.isoformat()},
        )
        self.db.add(event_reset)

        create_outbox_event(
            self.db,
            organization_id=self.context.organization.id,
            aggregate_type="simulation_run",
            aggregate_id=str(run.id),
            event_type="simulation.reset",
            payload={"run_id": str(run.id), "scenario_id": run.scenario_id, "status": "COMPLETED"},
            idempotency_key=f"outbox:simulation_reset:{run.id}",
        )

        log_audit_event(
            self.db,
            organization_id=self.context.organization.id,
            actor_id=self.context.user.id,
            resource_type="simulation_run",
            resource_id=str(run.id),
            action="simulation_reset",
            result="success",
            metadata={"reason": reason},
            ip_address=ip_address,
        )

        self.db.commit()
        self.db.refresh(run)
        return run

    def list_runs(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SimulationRun], int]:
        """List simulation runs for active tenant with lazy expiry check."""
        query = (
            select(SimulationRun)
            .where(SimulationRun.organization_id == self.context.organization.id)
            .order_by(desc(SimulationRun.created_at))
        )
        if status:
            query = query.where(SimulationRun.status == status)

        runs = self.db.scalars(query.offset(offset).limit(limit)).all()

        modified = False
        for r in runs:
            if self._check_and_apply_lazy_expiry(r):
                modified = True
        if modified:
            self.db.commit()

        total = len(runs)
        return list(runs), total

    def get_run(self, run_id: uuid.UUID) -> SimulationRun:
        """Get simulation run with lazy expiry check."""
        run = self.db.scalar(
            select(SimulationRun)
            .options(selectinload(SimulationRun.events))
            .where(
                SimulationRun.id == run_id,
                SimulationRun.organization_id == self.context.organization.id,
            )
        )
        if not run:
            raise SimulationNotFoundError(
                f"SimulationRun {run_id} not found in active organization"
            )

        if self._check_and_apply_lazy_expiry(run):
            self.db.commit()

        return run

    def get_run_events(self, run_id: uuid.UUID) -> list[SimulationEvent]:
        """Get timeline events for a simulation run."""
        # Tenant boundary check
        self.get_run(run_id)
        events = self.db.scalars(
            select(SimulationEvent)
            .where(
                SimulationEvent.run_id == run_id,
                SimulationEvent.organization_id == self.context.organization.id,
            )
            .order_by(SimulationEvent.created_at)
        ).all()
        return list(events)

    def reconcile_and_cleanup_expired(self) -> int:
        """Watchdog / cron reconciler cleaning all expired simulation runs (DEC-318)."""
        now = datetime.now(UTC)
        expired_active_runs = self.db.scalars(
            select(SimulationRun).where(
                SimulationRun.status == "ACTIVE",
                SimulationRun.expires_at <= now,
            )
        ).all()

        cleaned_count = 0
        for run in expired_active_runs:
            if self._check_and_apply_lazy_expiry(run):
                cleaned_count += 1

        if cleaned_count > 0:
            self.db.commit()
            logger.info(f"Reconciled and cleaned up {cleaned_count} expired simulation runs.")
        return cleaned_count

    def verify_recovery(self, run_id: uuid.UUID) -> dict[str, Any]:
        """Verifies observed service recovery independently of command execution (DEC-323)."""
        run = self.get_run(run_id)
        # Query health probe
        url = f"{self.shop_api_url.rstrip('/')}/healthz"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                health = json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            return {"recovered": False, "error": f"Health probe failed: {err}"}

        fault_active = health.get("fault_active", False)
        status_ok = health.get("status") == "ok"
        recovered = status_ok and not fault_active

        if recovered:
            event = SimulationEvent(
                run_id=run.id,
                organization_id=run.organization_id,
                event_type="service.recovery_observed",
                actor="system:verifier",
                payload={"health": health, "recovered_at": datetime.now(UTC).isoformat()},
            )
            self.db.add(event)
            create_outbox_event(
                self.db,
                organization_id=run.organization_id,
                aggregate_type="simulation_run",
                aggregate_id=str(run.id),
                event_type="service.recovery_observed",
                payload={
                    "run_id": str(run.id),
                    "service_id": str(run.service_id),
                    "status": "RECOVERED",
                },
                idempotency_key=f"outbox:recovery_observed:{run.id}",
            )
            self.db.commit()

        return {
            "recovered": recovered,
            "health": health,
            "message": "Service recovered and verified"
            if recovered
            else "Service still reports faults or unhealthiness",
        }
