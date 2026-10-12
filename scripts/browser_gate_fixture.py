"""DEC-337: synthetic fixtures and real Beat/worker proof in an isolated database only."""

import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, text

from apps.api.app.auth import TenantContext, hash_password
from apps.api.app.db import SessionLocal
from apps.api.app.models import (
    Incident,
    Membership,
    Organization,
    OutboxEvent,
    Service,
    SimulationEvent,
    SimulationRun,
    User,
)
from apps.api.app.simulation.service import SimulationService


def main() -> None:
    if os.environ.get("AEGISOPS_BROWSER_GATE") != "1":
        raise RuntimeError("Fixtures require the disposable browser gate")
    with SessionLocal() as db:
        if db.scalar(text("SELECT current_database()")) != "aegisops_phase0_verify":
            raise RuntimeError("Refusing to seed a non-verification database")
        if sys.argv[1] == "seed":
            password = sys.stdin.readline().strip()
            assert len(password) >= 24
            password_hash, salt = hash_password(password)
            org = Organization(id=UUID(int=100), name="Browser Gate Workspace")
            user = User(
                id=UUID(int=101),
                email="browser-gate@example.test",
                name="Browser Gate Owner",
                hashed_password=password_hash,
                salt=salt,
                is_active=True,
            )
            db.add_all([org, user])
            db.flush()
            service = Service(
                id=UUID(int=102),
                organization_id=org.id,
                name="shop-api",
                environment="staging",
                current_version="0.1.0",
            )
            db.add_all([service, Membership(user_id=user.id, organization_id=org.id, role="owner")])
            db.flush()
            for number, title in [(103, "Browser Gate Incident"), (104, "Browser Gate Denial")]:
                db.add(
                    Incident(
                        id=UUID(int=number),
                        organization_id=org.id,
                        service_id=service.id,
                        title=title,
                        severity="critical",
                        status="open",
                        environment="staging",
                        fingerprint=f"browser-gate-{number}",
                        started_at=datetime.now(UTC),
                    )
                )
            db.commit()
            print(
                "Seeded isolated workspace, password-authenticated owner, service and two incidents"
            )
            return

        assert sys.argv[1] == "watchdog"
        operator = db.get(User, UUID(int=101))
        workspace = db.get(Organization, UUID(int=100))
        assert operator is not None and workspace is not None
        simulation = SimulationService(
            db, TenantContext(user=operator, organization=workspace, role="owner")
        )
        run: SimulationRun | None = simulation.start_simulation(
            "S01_CHECKOUT_500", service_id=UUID(int=102)
        )
        assert run is not None and run.status == "ACTIVE"
        # Only this disposable fixture's expiry is shortened; production scenario TTL is unchanged.
        run.expires_at = datetime.now(UTC) + timedelta(seconds=25)
        db.commit()
        run_id = run.id

        def fault_active() -> bool:
            with urllib.request.urlopen("http://shop-api:3001/fault/status", timeout=3) as response:
                return bool(json.load(response)["fault_active"])

        assert fault_active(), "Fault must actually reach the isolated shop-api"
        time.sleep(12)  # Beat has time to dispatch at least one pre-expiry check.
        db.expire_all()
        run = db.get(SimulationRun, run_id)
        assert run is not None and run.status == "ACTIVE" and fault_active()
        print("PASS: real fault remains active before TTL", flush=True)
        db.rollback()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            db.expire_all()
            run = db.get(SimulationRun, run_id)
            assert run is not None
            if run.status == "EXPIRED":
                break
            db.rollback()
            time.sleep(1)
        assert run.status == "EXPIRED", "Beat/worker did not expire the run within the deadline"
        assert run.cleanup_status == "CLEANED" and not fault_active()
        print(f"PASS: unattended worker reset real fault; run={run_id}", flush=True)
        db.rollback()
        time.sleep(12)  # Observe another periodic execution, without invoking cleanup ourselves.
        events = db.scalar(
            select(func.count())
            .select_from(SimulationEvent)
            .where(
                SimulationEvent.run_id == run_id, SimulationEvent.event_type == "simulation.expired"
            )
        )
        outbox = db.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.aggregate_id == str(run_id),
                OutboxEvent.event_type == "simulation.expired",
            )
        )
        assert events == 1 and outbox == 1 and not fault_active()
        print("PASS: repeated periodic cleanup is idempotent; one expiry event and outbox record")


if __name__ == "__main__":
    main()
