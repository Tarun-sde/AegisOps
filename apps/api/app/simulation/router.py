"""FastAPI router for Incident Simulation Lab (Phase 7)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from apps.api.app.auth import TenantContext, get_tenant_context
from apps.api.app.db import get_db
from apps.api.app.schemas import (
    SimulationEventOut,
    SimulationResetRequest,
    SimulationRunListResponse,
    SimulationRunOut,
    SimulationScenarioOut,
    SimulationStartRequest,
)
from apps.api.app.simulation.scenarios import list_scenarios
from apps.api.app.simulation.service import (
    SimulationNotFoundError,
    SimulationPermissionDeniedError,
    SimulationService,
    SimulationStateConflictError,
)

router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


@router.get("/scenarios", response_model=list[SimulationScenarioOut])
def get_simulation_scenarios(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[SimulationScenarioOut]:
    """List all 6 predefined simulation scenarios."""
    scenarios = list_scenarios()
    return [
        SimulationScenarioOut(
            scenario_id=s.scenario_id,
            name=s.name,
            description=s.description,
            affected_service=s.affected_service,
            allowed_environment=s.allowed_environment,
            fault_type=s.fault_type,
            expected_cause_category=s.expected_cause_category,
            expected_signal_types=list(s.expected_signal_types),
            permitted_actions=list(s.permitted_actions),
            maximum_duration_seconds=s.maximum_duration_seconds,
            risk_level=s.risk_level,
            enabled=s.enabled,
        )
        for s in scenarios
    ]


@router.get("/runs", response_model=SimulationRunListResponse)
def list_simulation_runs(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SimulationRunListResponse:
    """List simulation runs for active organization."""
    service = SimulationService(db, context)
    runs, total = service.list_runs(status=status, limit=limit, offset=offset)
    return SimulationRunListResponse(
        items=[SimulationRunOut.model_validate(r) for r in runs],
        total=total,
    )


@router.post(
    "/scenarios/{scenario_id}/start",
    response_model=SimulationRunOut,
    status_code=status.HTTP_201_CREATED,
)
def start_simulation(
    scenario_id: str,
    data: SimulationStartRequest,
    request: Request,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[Session, Depends(get_db)],
) -> SimulationRunOut:
    """Start an authorized incident simulation scenario."""
    service = SimulationService(db, context)
    client_ip = request.client.host if request.client else None
    try:
        run = service.start_simulation(
            scenario_id=scenario_id,
            service_id=data.service_id,
            environment=data.environment,
            seed=data.seed,
            ip_address=client_ip,
        )
        return SimulationRunOut.model_validate(run)
    except SimulationPermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except SimulationStateConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    except SimulationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@router.get("/runs/{run_id}", response_model=SimulationRunOut)
def get_simulation_run(
    run_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[Session, Depends(get_db)],
) -> SimulationRunOut:
    """Get simulation run by ID."""
    service = SimulationService(db, context)
    try:
        run = service.get_run(run_id)
        return SimulationRunOut.model_validate(run)
    except SimulationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post("/runs/{run_id}/reset", response_model=SimulationRunOut)
def reset_simulation_run(
    run_id: uuid.UUID,
    data: SimulationResetRequest,
    request: Request,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[Session, Depends(get_db)],
) -> SimulationRunOut:
    """Reset active simulation run."""
    service = SimulationService(db, context)
    client_ip = request.client.host if request.client else None
    try:
        run = service.reset_simulation(run_id=run_id, reason=data.reason, ip_address=client_ip)
        return SimulationRunOut.model_validate(run)
    except SimulationPermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except SimulationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.get("/runs/{run_id}/events", response_model=list[SimulationEventOut])
def get_simulation_run_events(
    run_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SimulationEventOut]:
    """Get timeline events for a simulation run."""
    service = SimulationService(db, context)
    try:
        events = service.get_run_events(run_id)
        return [SimulationEventOut.model_validate(e) for e in events]
    except SimulationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post("/runs/{run_id}/verify-recovery")
def verify_simulation_recovery(
    run_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Verifies that the target demo service has recovered telemetry signals."""
    service = SimulationService(db, context)
    try:
        return service.verify_recovery(run_id)
    except SimulationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@router.post("/watchdog/reconcile")
def watchdog_reconcile(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Watchdog trigger to clean up expired simulation runs."""
    service = SimulationService(db, context)
    cleaned = service.reconcile_and_cleanup_expired()
    return {"cleaned_expired_runs": cleaned}
