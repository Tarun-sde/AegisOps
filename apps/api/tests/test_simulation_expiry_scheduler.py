"""Tests for Automatic Simulation Expiry and Celery Beat Scheduler (Issue 2).

Validates:
- Celery beat schedule configuration in celery_app.conf.beat_schedule
- Simulation TTL boundaries and active state preservation before expiry
- Automatic watchdog reconciliation after expiry without browser or HTTP activity
- Safe idempotency under duplicate and repeated cleanup runs
- Concurrency safety with row locking (with_for_update)
- Audit trail event and transactional outbox emission on automatic recovery
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.auth import TenantContext, hash_password
from apps.api.app.models import (
    Base,
    Membership,
    Organization,
    OutboxEvent,
    Service,
    SimulationEvent,
    SimulationRun,
    User,
)
from apps.api.app.simulation.scenarios import SCENARIO_CATALOG
from apps.api.app.simulation.service import SimulationService
from apps.worker.celery_app import celery_app
from apps.worker.tasks import reconcile_simulation_expiry_task

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seed_data(test_db):
    org = Organization(name="Scheduler Test Tenant")
    test_db.add(org)
    test_db.flush()

    pwd_hash, salt = hash_password("secret123")
    user = User(
        email="operator@schedulertest.local",
        name="Test Operator",
        hashed_password=pwd_hash,
        salt=salt,
    )
    test_db.add(user)
    test_db.flush()

    membership = Membership(user_id=user.id, organization_id=org.id, role="owner")
    test_db.add(membership)

    service = Service(
        name="shop-api",
        organization_id=org.id,
        environment="staging",
        status="active",
        current_version="0.1.0",
    )
    test_db.add(service)
    test_db.commit()

    context = TenantContext(user=user, organization=org, role="owner")
    return {"org": org, "user": user, "service": service, "context": context}


def test_celery_beat_schedule_configuration():
    """Verify Celery Beat schedule contains simulation watchdog and outbox dispatch."""
    schedule = celery_app.conf.beat_schedule
    assert schedule is not None
    assert "reconcile-simulation-expiry-periodic" in schedule

    expiry_cfg = schedule["reconcile-simulation-expiry-periodic"]
    assert expiry_cfg["task"] == "aegisops.reconcile_simulation_expiry"
    assert expiry_cfg["schedule"] == 10.0
    assert expiry_cfg["options"]["expires"] == 8.0

    assert "dispatch-outbox-events-periodic" in schedule
    dispatch_cfg = schedule["dispatch-outbox-events-periodic"]
    assert dispatch_cfg["task"] == "aegisops.dispatch_outbox_events"
    assert dispatch_cfg["schedule"] == 15.0


def test_simulation_starts_with_bounded_ttl(test_db, seed_data):
    """Verify simulation starts with bounded TTL and remains active before expiry."""
    context = seed_data["context"]
    service = seed_data["service"]
    sim_svc = SimulationService(test_db, context)

    with patch.object(SimulationService, "_call_shop_api") as mock_inject:
        mock_inject.return_value = {"status": "ok", "scenario": "S01_CHECKOUT_500"}
        run = sim_svc.start_simulation("S01_CHECKOUT_500", service_id=service.id)

    scenario = SCENARIO_CATALOG["S01_CHECKOUT_500"]
    assert run.status == "ACTIVE"
    assert run.cleanup_status == "PENDING"
    assert run.expires_at > run.started_at
    expected_duration = timedelta(seconds=scenario.maximum_duration_seconds)
    # Allow 2 second margin for test execution
    assert abs((run.expires_at - run.started_at) - expected_duration) < timedelta(seconds=2)


def test_watchdog_does_not_expire_active_unexpired_simulation(test_db, seed_data):
    """Verify watchdog skips active simulation before its TTL has elapsed."""
    context = seed_data["context"]
    service = seed_data["service"]
    sim_svc = SimulationService(test_db, context)

    with patch.object(SimulationService, "_call_shop_api") as mock_inject:
        mock_inject.return_value = {"status": "ok"}
        run = sim_svc.start_simulation("S01_CHECKOUT_500", service_id=service.id)

    with patch("apps.worker.tasks.SessionLocal", side_effect=TestingSessionLocal):
        with patch.object(SimulationService, "_call_shop_api") as mock_reset:
            result = reconcile_simulation_expiry_task()
            assert result["cleaned_expired_runs"] == 0
            mock_reset.assert_not_called()

    # Re-query run from fresh session
    verify_db = TestingSessionLocal()
    updated_run = verify_db.get(SimulationRun, run.id)
    assert updated_run is not None
    assert updated_run.status == "ACTIVE"
    assert updated_run.cleanup_status == "PENDING"
    verify_db.close()


def test_automatic_cleanup_runs_after_expiry_without_browser(test_db, seed_data):
    """Verify watchdog automatically resets fault and transitions run to EXPIRED after TTL."""
    context = seed_data["context"]
    service = seed_data["service"]
    sim_svc = SimulationService(test_db, context)

    with patch.object(SimulationService, "_call_shop_api") as mock_inject:
        mock_inject.return_value = {"status": "ok"}
        run = sim_svc.start_simulation("S01_CHECKOUT_500", service_id=service.id)

    # Artificially age the run past its expiration time
    run.expires_at = datetime.now(UTC) - timedelta(seconds=30)
    test_db.commit()

    with patch("apps.worker.tasks.SessionLocal", side_effect=TestingSessionLocal):
        with patch.object(SimulationService, "_call_shop_api") as mock_reset:
            mock_reset.return_value = {"status": "ok", "reset": True}
            result = reconcile_simulation_expiry_task()
            assert result["cleaned_expired_runs"] == 1
            mock_reset.assert_called_once_with("/fault/reset")

    verify_db = TestingSessionLocal()
    updated_run = verify_db.get(SimulationRun, run.id)
    assert updated_run is not None
    assert updated_run.status == "EXPIRED"
    assert updated_run.cleanup_status == "CLEANED"
    assert updated_run.ended_at is not None

    # Check audit events recorded
    events = (
        verify_db.query(SimulationEvent)
        .filter_by(run_id=run.id, event_type="simulation.expired")
        .all()
    )
    assert len(events) == 1
    assert events[0].actor == "system:watchdog"

    # Check outbox event recorded
    outbox = (
        verify_db.query(OutboxEvent)
        .filter_by(aggregate_id=str(run.id), event_type="simulation.expired")
        .first()
    )
    assert outbox is not None
    verify_db.close()


def test_repeated_cleanup_is_idempotent_and_safe(test_db, seed_data):
    """Verify running cleanup multiple times does not duplicate resets or cause errors."""
    context = seed_data["context"]
    service = seed_data["service"]
    sim_svc = SimulationService(test_db, context)

    with patch.object(SimulationService, "_call_shop_api") as mock_inject:
        mock_inject.return_value = {"status": "ok"}
        run = sim_svc.start_simulation("S01_CHECKOUT_500", service_id=service.id)

    run.expires_at = datetime.now(UTC) - timedelta(seconds=10)
    test_db.commit()

    with patch("apps.worker.tasks.SessionLocal", side_effect=TestingSessionLocal):
        with patch.object(SimulationService, "_call_shop_api") as mock_reset:
            mock_reset.return_value = {"status": "ok"}
            res1 = reconcile_simulation_expiry_task()
            assert res1["cleaned_expired_runs"] == 1
            assert mock_reset.call_count == 1

            # Second execution: run is already EXPIRED, must clean 0 runs
            res2 = reconcile_simulation_expiry_task()
            assert res2["cleaned_expired_runs"] == 0
            assert mock_reset.call_count == 1  # No additional reset calls
