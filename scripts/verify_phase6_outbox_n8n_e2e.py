"""Phase 6 End-to-End Verification Demonstration Script.

Demonstrates the five core Phase 6 capabilities:
1. PostgreSQL Transactional Outbox (atomic publication with business entity state).
2. HMAC-SHA256 signed event delivery with timestamp replay protection.
3. Receiver-side idempotency deduplication (zero duplicate demo tickets on retry).
4. Full incident lifecycle notification outbox events (created, investigated, approved).
5. Human-governed remediation proposals (canonical SHA-256 hash, RBAC gating, audit trail).
6. Security boundary verification: ZERO remediation execution in Phase 6 (DEC-312).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.actions.catalog import (
    ACTION_CATALOG,
    execute_action,
    validate_proposal_parameters,
)
from apps.api.app.auth import hash_password
from apps.api.app.db import get_db
from apps.api.app.main import app
from apps.api.app.models import (
    Base,
    Incident,
    Membership,
    Organization,
    OutboxEvent,
    Service,
    User,
)
from apps.api.app.outbox.service import create_outbox_event
from apps.api.app.outbox.signer import (
    sign_event_envelope,
    verify_event_signature,
)


def print_step(step: str, title: str) -> None:
    print("\n" + "=" * 80)
    print(f"STEP {step}: {title}")
    print("=" * 80)


def main() -> None:
    print("=" * 80)
    print("AEGISOPS — PHASE 6 END-TO-END AUTOMATION, OUTBOX & APPROVALS VERIFICATION")
    print("=" * 80)

    # 1. Hermetic DB Setup
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    # -------------------------------------------------------------------------
    # STEP 1: Multi-Tenant Architecture & Roles
    # -------------------------------------------------------------------------
    print_step("1", "Initializing Multi-Tenant RBAC Hierarchy")

    with TestingSession() as db:
        pwd_hash, salt = hash_password("Password123!")

        # Tenant A: Acme Corp
        org_acme = Organization(name="Acme Corp")
        admin_acme = User(
            email="admin@acme.com",
            name="Alice Admin",
            hashed_password=pwd_hash,
            salt=salt,
            is_active=True,
        )
        viewer_acme = User(
            email="viewer@acme.com",
            name="Bob Viewer",
            hashed_password=pwd_hash,
            salt=salt,
            is_active=True,
        )
        db.add_all([org_acme, admin_acme, viewer_acme])
        db.flush()

        db.add(Membership(user_id=admin_acme.id, organization_id=org_acme.id, role="admin"))
        db.add(Membership(user_id=viewer_acme.id, organization_id=org_acme.id, role="viewer"))

        svc_shop = Service(organization_id=org_acme.id, name="shop-api", environment="staging")
        db.add(svc_shop)

        # Tenant B: Initech (Alien Tenant for cross-tenant testing)
        org_initech = Organization(name="Initech")
        admin_initech = User(
            email="admin@initech.com",
            name="Eve Initech",
            hashed_password=pwd_hash,
            salt=salt,
            is_active=True,
        )
        db.add_all([org_initech, admin_initech])
        db.flush()
        db.add(Membership(user_id=admin_initech.id, organization_id=org_initech.id, role="admin"))

        db.commit()
        acme_org_id = org_acme.id
        shop_svc_id = svc_shop.id

    print(f" [✓] Created Acme Corp (Org: {acme_org_id}) with Admin & Viewer")
    print(" [✓] Created Initech (Alien Tenant) for cross-tenant security verification")

    admin_client = TestClient(app)
    viewer_client = TestClient(app)
    initech_client = TestClient(app)

    def login_session(c: TestClient, email: str) -> str:
        res = c.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert res.status_code == 200, res.text
        return res.cookies["aegisops_csrf"]

    admin_csrf = login_session(admin_client, "admin@acme.com")
    viewer_csrf = login_session(viewer_client, "viewer@acme.com")
    initech_csrf = login_session(initech_client, "admin@initech.com")

    # -------------------------------------------------------------------------
    # STEP 2: Atomic Transactional Outbox (incident.created)
    # -------------------------------------------------------------------------
    print_step("2", "Simulating Incident Creation with Atomic Outbox Publication")

    incident_id = uuid.uuid4()
    with TestingSession() as db:
        # Atomic transaction: Incident + OutboxEvent in single commit
        incident = Incident(
            id=incident_id,
            organization_id=acme_org_id,
            service_id=shop_svc_id,
            environment="staging",
            title="Elevated HTTP 500 error rate on checkout",
            severity="high",
            status="open",
            fingerprint="checkout-http500-staging",
            started_at=datetime.now(UTC),
        )
        db.add(incident)

        outbox_event = create_outbox_event(
            db,
            organization_id=acme_org_id,
            aggregate_type="incident",
            aggregate_id=str(incident_id),
            event_type="incident.created",
            payload={
                "incident_id": str(incident_id),
                "service_name": "shop-api",
                "severity": "HIGH",
                "title": "Elevated HTTP 500 error rate on checkout",
                "environment": "staging",
            },
        )
        db.commit()
        outbox_id = outbox_event.id

    print(f" [✓] Incident {incident_id} committed atomically with OutboxEvent {outbox_id}")
    print(f" [✓] Initial Outbox Status: {outbox_event.status} (attempt_count=0)")

    # -------------------------------------------------------------------------
    # STEP 3: HMAC-SHA256 Signing & Demo Sink Delivery
    # -------------------------------------------------------------------------
    print_step("3", "Cryptographic HMAC-SHA256 Signing & Webhook Delivery")

    with TestingSession() as db:
        event_record = db.get(OutboxEvent, outbox_id)
        assert event_record is not None
        payload_bytes = json.dumps(event_record.payload, sort_keys=True).encode("utf-8")
        event_uuid = str(event_record.id)
        timestamp_now = datetime.now(UTC).isoformat()

        # Sign envelope
        signature = sign_event_envelope(payload_bytes, event_uuid, timestamp_now)
        headers = {
            "X-AegisOps-Signature": signature,
            "X-AegisOps-Timestamp": timestamp_now,
            "X-AegisOps-Event-ID": event_uuid,
            "X-AegisOps-Key-ID": "v1",
        }

    # Verify signature verification algorithm
    is_valid, reason = verify_event_signature(payload_bytes, event_uuid, timestamp_now, signature)
    assert is_valid is True
    print(f" [✓] HMAC Signature verified: {signature[:28]}... (Reason: {reason})")

    # Send to demo sink
    sink_res = client.post("/api/v1/automations/demo-sink", content=payload_bytes, headers=headers)
    assert sink_res.status_code == 200, sink_res.text
    ticket_data = sink_res.json()
    assert ticket_data["status"] == "accepted"
    print(f" [✓] Demo sink accepted event: Ticket ID = {ticket_data['ticket_id']}")

    # -------------------------------------------------------------------------
    # STEP 4: Idempotency & Replay Protection (Mandatory Exit Gate)
    # -------------------------------------------------------------------------
    print_step("4", "Verifying Receiver Idempotency & Replay Deduplication")

    replay_res = client.post(
        "/api/v1/automations/demo-sink", content=payload_bytes, headers=headers
    )
    assert replay_res.status_code == 200
    replay_data = replay_res.json()
    assert replay_data["status"] == "duplicate_ignored"
    assert replay_data["ticket_id"] is None
    print(" [✓] Replayed webhook cleanly deduplicated!")
    print(f" [✓] Receiver message: '{replay_data['message']}'")
    print(" [✓] Zero duplicate demo tickets created.")

    # -------------------------------------------------------------------------
    # STEP 5: Remediation Proposal Creation with Canonical Hash (DEC-309)
    # -------------------------------------------------------------------------
    print_step("5", "Creating Human Remediation Proposal via Catalog Policy")

    catalog_item = ACTION_CATALOG["rollback_demo_release"]
    print(f" [✓] Action Catalog ID: {catalog_item.action_catalog_id}")
    print(f" [✓] Applicable Environments: {catalog_item.applicable_environments}")
    print(f" [✓] Risk Classification: {catalog_item.risk_classification}")

    params = {
        "service_name": "shop-api",
        "target_version": "v1.2.0",
        "reason": "Reverting broken checkout deployment v1.3.0",
    }
    validated_params, canonical_hash = validate_proposal_parameters("rollback_demo_release", params)
    print(f" [✓] Computed Canonical SHA-256 Hash: {canonical_hash}")

    # Create proposal via API
    create_payload = {
        "service_id": str(shop_svc_id),
        "environment": "staging",
        "action_catalog_id": "rollback_demo_release",
        "immutable_parameters": validated_params,
        "reason": "Checkout 500 error rate exceeded 5% threshold",
        "expected_outcome": "Restores error rate to baseline < 0.1%",
        "known_risks": "Reverts new promotional discounts introduced in v1.3.0",
        "expires_in_seconds": 1800,
    }

    create_res = admin_client.post(
        "/api/v1/actions/proposals",
        json=create_payload,
        headers={"x-csrf-token": admin_csrf},
    )
    assert create_res.status_code == 201, create_res.text
    prop_data = create_res.json()
    proposal_id = prop_data["id"]
    print(f" [✓] Created Proposal {proposal_id} in state PROPOSED")
    assert prop_data["parameters_hash"] == canonical_hash

    # -------------------------------------------------------------------------
    # STEP 6: Security Boundary Checks (Adversarial Testing)
    # -------------------------------------------------------------------------
    print_step("6", "Adversarial Security Boundary Verification")

    # A. Unauthorized approval by Viewer
    unauth_res = viewer_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={"expected_parameters_hash": canonical_hash, "comment": "Unauthorized attempt"},
        headers={"x-csrf-token": viewer_csrf},
    )
    assert unauth_res.status_code == 403
    print(" [✓] Check A Passed: Viewer approval attempt rejected with 403 Forbidden")

    # B. Tampered / Modified parameter hash
    tampered_hash = hashlib.sha256(b"malicious_parameters").hexdigest()
    mismatch_res = admin_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={"expected_parameters_hash": tampered_hash, "comment": "Hash attack"},
        headers={"x-csrf-token": admin_csrf},
    )
    assert mismatch_res.status_code == 400
    print(" [✓] Check B Passed: Hash mismatch rejected with 400 Bad Request")

    # C. Cross-tenant access by Alien Tenant
    cross_res = initech_client.get(
        f"/api/v1/actions/proposals/{proposal_id}",
        headers={"x-csrf-token": initech_csrf},
    )
    assert cross_res.status_code == 404
    print(" [✓] Check C Passed: Alien tenant read rejected with 404 Not Found")

    # -------------------------------------------------------------------------
    # STEP 7: Authorized Approval & Audit Trail
    # -------------------------------------------------------------------------
    print_step("7", "Authorized Admin Approval & State Transition")

    approve_res = admin_client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        json={
            "expected_parameters_hash": canonical_hash,
            "comment": "Approved after reviewing Prometheus error rate spike",
        },
        headers={"x-csrf-token": admin_csrf},
    )
    assert approve_res.status_code == 200, approve_res.text
    approved_data = approve_res.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["approval"] is not None
    assert approved_data["approval"]["decision"] == "APPROVED"
    print(f" [✓] Proposal {proposal_id} transitioned to APPROVED")
    print(f" [✓] Approver User: {approved_data['approval']['approver_id']}")
    print(f" [✓] Verified immutable parameters preserved: {approved_data['immutable_parameters']}")

    # Verify atomic outbox event emitted for approval
    with TestingSession() as db:
        approval_event = (
            db.query(OutboxEvent)
            .filter(
                OutboxEvent.aggregate_id == proposal_id,
                OutboxEvent.event_type == "proposal.approved",
            )
            .first()
        )
        assert approval_event is not None
        print(f" [✓] Outbox event {approval_event.id} ('proposal.approved') queued atomically")

    # -------------------------------------------------------------------------
    # STEP 8: Zero-Execution Invariant Verification (DEC-312)
    # -------------------------------------------------------------------------
    print_step("8", "Zero-Execution Invariant Verification (Phase 6 Scope Barrier)")

    # 1. Action catalog execute_action strictly raises NotImplementedError
    try:
        execute_action("rollback_demo_release", validated_params)
        raise AssertionError("execute_action should have raised NotImplementedError!")
    except NotImplementedError as exc:
        print(f" [✓] Action executor invocation blocked: {exc}")

    # 2. Verify no remediation executor routes exist in API
    exec_res = client.post("/api/v1/actions/execute")
    assert exec_res.status_code == 404
    remed_res = client.post("/api/v1/actions/remediate")
    assert remed_res.status_code == 404
    print(" [✓] Nonexistent execution endpoints returned 404 (zero execution exposure)")

    # -------------------------------------------------------------------------
    # VERIFICATION COMPLETE
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 6 END-TO-END VERIFICATION: ALL CHECKS PASSED SUCCESSFULLY (100%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
