from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.incident_investigator.tools.gateway import ReadOnlyToolGateway
from agents.incident_investigator.validator import validate_evidence
from apps.api.app.auth import create_user_session, hash_password
from apps.api.app.db import get_db
from apps.api.app.main import app
from apps.api.app.models import (
    Base,
    Incident,
    InvestigationRun,
    Membership,
    Organization,
    Service,
    User,
)
from apps.api.app.rag.chunking import SemanticChunker
from apps.api.app.rag.embeddings import DeterministicHashEmbeddingProvider
from apps.api.app.rag.models import Document, DocumentChunk
from apps.api.app.rag.redaction import redact_document_text
from apps.api.app.rag.related_incidents import RelatedIncidentService
from apps.api.app.rag.retrieval import HybridRetrievalService
from apps.api.app.rag.service import DocumentIngestionService, ValidationError
from apps.api.app.schemas import Evidence, EvidenceRef, Hypothesis, InvestigationResult, Scope

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


def create_tenant(
    db: Any, org_name: str = "Acme Corp", email: str = "alice@example.com", role: str = "owner"
) -> tuple[User, Organization, str]:
    pwd_hash, salt = hash_password("password123")
    user = User(
        email=email,
        hashed_password=pwd_hash,
        salt=salt,
        name="Alice",
    )
    db.add(user)
    db.flush()

    org = Organization(name=org_name)
    db.add(org)
    db.flush()

    membership = Membership(user_id=user.id, organization_id=org.id, role=role)
    db.add(membership)
    db.commit()

    raw_token, _session = create_user_session(db, user.id)
    return user, org, raw_token


# =========================================================================
# 1. UNIT TESTS: SECRET REDACTION
# =========================================================================


def test_redact_private_keys_and_tokens() -> None:
    raw = """
# Runbook: DB Recovery
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0m4w4...secret...
-----END RSA PRIVATE KEY-----

Connect using: postgresql://admin:SuperSecretPass123!@db.internal:5432/orders
Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummysecret
AWS key: AKIAIOSFODNN7EXAMPLE and secret: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwxyzAB
Password: password = "hunter2"

Safe technical identifiers:
Error: ECONNRESET, PGRES_FATAL_ERROR
Connection pool parameter: MAX_POOL_SIZE=20
Query: SELECT * FROM orders WHERE status = 'pending'
"""
    redacted, count = redact_document_text(raw)
    assert count >= 4
    assert "-----BEGIN RSA PRIVATE KEY-----" not in redacted
    assert "[REDACTED_PRIVATE_KEY]" in redacted
    assert "SuperSecretPass123!" not in redacted
    assert "[REDACTED]" in redacted
    assert "ghp_1234567890" not in redacted
    assert "hunter2" not in redacted

    # Verify technical identifiers are preserved
    assert "ECONNRESET" in redacted
    assert "PGRES_FATAL_ERROR" in redacted
    assert "MAX_POOL_SIZE=20" in redacted
    assert "SELECT * FROM orders WHERE status = 'pending'" in redacted


# =========================================================================
# 2. UNIT TESTS: SEMANTIC CHUNKING
# =========================================================================


def test_semantic_chunker_hierarchical_sections() -> None:
    doc = """# Runbook: Postgres Connection Pool Exhaustion

Operational procedures for troubleshooting pool saturation.

## Symptoms and Indicators
When active connections reach `max_connections`, services report:
- `FATAL: remaining connection slots are reserved for non-replication superuser connections`
- HTTP 500 downstream errors with timeout traces.

### Metrics to Inspect
Look at Prometheus metric `pg_stat_activity_count` grouped by state.

## Immediate Remediation Steps
1. Scale up read replicas.
2. Restart non-essential background worker pools.

```bash
# Emergency drain
pg_cancel_backend(pid);
```
"""
    chunker = SemanticChunker(target_tokens=150, max_tokens=300)
    chunks = chunker.chunk_document(doc, "Postgres Connection Pool Exhaustion")

    assert len(chunks) >= 3
    # Check section paths
    titles = [c.section_title for c in chunks]
    paths = [c.section_path for c in chunks]

    assert any("Symptoms and Indicators" in t for t in titles)
    assert any("Immediate Remediation Steps" in t for t in titles)
    assert any("Postgres Connection Pool Exhaustion" in p for p in paths)
    assert any("Symptoms and Indicators" in p for p in paths)

    # Check token counts and chunk indexing
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i
        assert chunk.token_count > 0
        assert len(chunk.content_hash) == 64


def test_semantic_chunker_empty_and_short_text() -> None:
    chunker = SemanticChunker()
    assert chunker.chunk_document("", "Empty") == []
    assert chunker.chunk_document("   \n\n  ", "Whitespace") == []

    single = chunker.chunk_document("Single brief note without headings.", "Brief")
    assert len(single) == 1
    assert single[0].section_title == "Brief"
    assert "Single brief note" in single[0].content


# =========================================================================
# 3. UNIT TESTS: DETERMINISTIC HASH EMBEDDINGS
# =========================================================================


@pytest.mark.asyncio
async def test_deterministic_embedding_provider() -> None:
    provider = DeterministicHashEmbeddingProvider(dimension=768)

    # Query embedding
    q_vec = await provider.embed_query("Postgres connection pool recovery")
    assert len(q_vec) == 768
    # Norm should be approximately 1.0 (unit vector)
    norm = sum(x * x for x in q_vec) ** 0.5
    assert abs(norm - 1.0) < 1e-4

    # Determinism: identical text yields identical embedding
    q_vec2 = await provider.embed_query("Postgres connection pool recovery")
    assert q_vec == q_vec2

    # Different text yields distinct vector
    diff_vec = await provider.embed_query("Completely unrelated topic about CSS styling")
    assert q_vec != diff_vec

    # Documents batch embedding
    doc_vecs = await provider.embed_documents(["First doc", "Second doc"])
    assert len(doc_vecs) == 2
    assert len(doc_vecs[0]) == 768
    assert len(doc_vecs[1]) == 768


# =========================================================================
# 4. INTEGRATION TESTS: DOCUMENT INGESTION SERVICE LIFECYCLE
# =========================================================================


@pytest.mark.asyncio
async def test_document_ingestion_lifecycle_success() -> None:
    db = TestingSessionLocal()
    try:
        user, org, _ = create_tenant(db)
        service = DocumentIngestionService(db)

        content = """# Redis Cache Saturation Runbook

## Overview
Procedures when Redis hits maxmemory-eviction limit.

## Diagnostic Steps
Inspect `redis_connected_clients` and `used_memory_rss_bytes`.
"""
        doc = service.create_pending_document(
            organization_id=org.id,
            filename="redis_runbook.md",
            content=content,
            created_by=user.id,
            title="Redis Cache Saturation Runbook",
        )
        assert doc.status == "PENDING"
        assert doc.version == 1

        # Run full ingestion
        processed_doc = await service.ingest_document(doc.id)
        assert processed_doc.status == "READY"
        assert processed_doc.indexed_at is not None
        assert processed_doc.error_code is None

        # Verify chunks created in DB
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == processed_doc.id).all()
        assert len(chunks) >= 2
        for ch in chunks:
            assert ch.organization_id == org.id
            assert len(ch.embedding) == 768
    finally:
        db.close()


@pytest.mark.asyncio
async def test_document_validation_errors() -> None:
    db = TestingSessionLocal()
    try:
        user, org, _ = create_tenant(db)
        service = DocumentIngestionService(db)

        # 1. Invalid extension
        with pytest.raises(ValidationError, match="Unsupported file format"):
            service.create_pending_document(
                organization_id=org.id,
                filename="script.sh",
                content="echo 1",
                created_by=user.id,
            )

        # 2. Empty content
        with pytest.raises(ValidationError, match="cannot be empty"):
            service.create_pending_document(
                organization_id=org.id,
                filename="empty.md",
                content="   ",
                created_by=user.id,
            )

        # 3. Path traversal sanitized in filename
        doc = service.create_pending_document(
            organization_id=org.id,
            filename="../../etc/passwd.md",
            content="# Safe content",
            created_by=user.id,
        )
        assert ".." not in doc.filename
        assert doc.filename == "passwd.md"
    finally:
        db.close()


# =========================================================================
# 5. INTEGRATION TESTS: VERSIONING, SOFT DELETION, AND REINDEXING
# =========================================================================


@pytest.mark.asyncio
async def test_document_versioning_and_soft_delete() -> None:
    db = TestingSessionLocal()
    try:
        user, org, _ = create_tenant(db)
        service = DocumentIngestionService(db)

        # Upload v1
        doc_v1 = service.create_pending_document(
            organization_id=org.id,
            filename="runbook.md",
            content="# Version 1 Content\n\nInitial guidelines.",
            created_by=user.id,
        )
        await service.ingest_document(doc_v1.id)
        assert doc_v1.version == 1
        assert doc_v1.status == "READY"

        # Upload revised version (same filename) -> increments version to 2
        doc_v2 = service.create_pending_document(
            organization_id=org.id,
            filename="runbook.md",
            content="# Version 2 Content\n\nUpdated and revised guidelines.",
            created_by=user.id,
        )
        await service.ingest_document(doc_v2.id)
        assert doc_v2.version == 2
        assert doc_v2.status == "READY"

        # Search should find v2 chunks
        retrieval = HybridRetrievalService(db)
        results = await retrieval.search(
            organization_id=org.id,
            query="revised guidelines",
            limit=5,
        )
        assert len(results.results) > 0
        assert results.results[0].document_id == str(doc_v2.id)
        assert results.results[0].document_version == 2

        # Soft delete doc_v2
        deleted = service.soft_delete_document(doc_v2.id, org.id)
        assert deleted is True

        # Subsequent search must NOT return deleted doc
        post_del_results = await retrieval.search(
            organization_id=org.id,
            query="revised guidelines",
            limit=5,
        )
        matching_ids = [r.document_id for r in post_del_results.results]
        assert str(doc_v2.id) not in matching_ids
    finally:
        db.close()


# =========================================================================
# 6. SECURITY TESTS: CROSS-TENANT ISOLATION
# =========================================================================


@pytest.mark.asyncio
async def test_cross_tenant_isolation_retrieval(test_client: TestClient) -> None:
    db = TestingSessionLocal()
    try:
        # Tenant A
        user_a, org_a, token_a = create_tenant(db, "Org Alpha", "alpha@example.com")
        # Tenant B
        user_b, org_b, token_b = create_tenant(db, "Org Beta", "beta@example.com")

        service = DocumentIngestionService(db)

        # Org Alpha uploads confidential runbook
        doc_a = service.create_pending_document(
            organization_id=org_a.id,
            filename="alpha_secret_runbook.md",
            content=(
                "# Alpha Proprietary Secret\n\n"
                "Credentials and internal procedures for Alpha service."
            ),
            created_by=user_a.id,
            title="Alpha Proprietary Secret",
        )
        await service.ingest_document(doc_a.id)

        # Org Beta searches via API
        search_res = test_client.post(
            "/api/v1/runbooks/search",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"query": "Alpha Proprietary Secret credentials", "limit": 10},
        )
        assert search_res.status_code == 200
        data = search_res.json()
        # Zero items from Alpha may leak to Beta
        assert len(data["results"]) == 0

        # Direct metadata lookup across tenants
        get_res = test_client.get(
            f"/api/v1/runbooks/{doc_a.id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert get_res.status_code == 404

        # Delete attempt across tenants
        del_res = test_client.delete(
            f"/api/v1/runbooks/{doc_a.id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert del_res.status_code == 404
    finally:
        db.close()


@pytest.mark.asyncio
async def test_cross_tenant_historical_incidents_isolation() -> None:
    db = TestingSessionLocal()
    try:
        _, org_a, _ = create_tenant(db, "Org Alpha", "alpha@example.com")
        _, org_b, _ = create_tenant(db, "Org Beta", "beta@example.com")

        # Service for Org Alpha
        svc_a = Service(name="checkout", organization_id=org_a.id)
        db.add(svc_a)
        db.flush()

        # Create historical resolved incident for Org Alpha
        inc_a = Incident(
            organization_id=org_a.id,
            service_id=svc_a.id,
            fingerprint="fp_alpha_checkout_db_pool",
            title="Database Connection Pool Exhaustion on Alpha Checkout",
            severity="critical",
            status="resolved",
            started_at=datetime.now(UTC) - timedelta(hours=2),
            resolved_at=datetime.now(UTC),
        )
        db.add(inc_a)
        db.commit()

        # Related incident lookup for Org Beta
        svc = RelatedIncidentService(db)
        results = svc.get_related_incidents(
            organization_id=org_b.id,
            symptoms="database connection pool exhaustion billing",
            limit=5,
        )
        # Beta must find 0 incidents
        assert len(results) == 0

        # Org Alpha should find its incident
        alpha_results = svc.get_related_incidents(
            organization_id=org_a.id,
            symptoms="database connection pool exhaustion billing",
            limit=5,
        )
        assert len(alpha_results) == 1
        assert alpha_results[0].incident_id == str(inc_a.id)
    finally:
        db.close()


# =========================================================================
# 7. SECURITY TESTS: EVIDENCE VALIDATION & CITATION INTEGRITY
# =========================================================================


def test_fake_evidence_id_rejected_by_validator() -> None:
    # Model fabricates an invented evidence ID
    res = InvestigationResult(
        status="complete",
        summary="Database pool exhaustion diagnosed.",
        hypotheses=[
            Hypothesis(
                cause="Database connection pool contention",
                confidence="medium",
                supporting_evidence=[
                    EvidenceRef(
                        evidence_id="ev_runbook_fake_invented_9999",
                        supports="Fake runbook recommendation",
                    )
                ],
            )
        ],
    )
    scope = Scope(
        organization_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
    )
    now = datetime.now(UTC)
    returned_ledger = {
        "ev_metric_001": Evidence(
            organization_id=scope.organization_id,
            service_id=scope.service_id,
            run_id=scope.run_id,
            evidence_id="ev_metric_001",
            source="metrics",
            observed_at=now,
            redacted_snippet="Metric error spike",
            locator="prometheus:metric_spike",
        ),
        "ev_log_002": Evidence(
            organization_id=scope.organization_id,
            service_id=scope.service_id,
            run_id=scope.run_id,
            evidence_id="ev_log_002",
            source="logs",
            observed_at=now,
            redacted_snippet="500 Connection timeout",
            locator="loki:checkout:10",
        ),
    }
    with pytest.raises(ValueError, match="Unknown evidence reference"):
        validate_evidence(res, scope=scope, returned_ledger=returned_ledger)


def test_high_confidence_claim_rejected_without_runtime_telemetry() -> None:
    # High confidence claiming root cause based solely on runbook guidance
    res = InvestigationResult(
        status="complete",
        summary="Payment gateway degradation diagnosed solely from runbook.",
        hypotheses=[
            Hypothesis(
                cause="External payment API degradation causing cascading gateway timeouts",
                confidence="high",
                supporting_evidence=[
                    EvidenceRef(
                        evidence_id="ev_runbook_valid_123",
                        supports="Runbook matches error pattern",
                    )
                ],
            )
        ],
    )
    scope = Scope(
        organization_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
    )
    now = datetime.now(UTC)
    returned_ledger = {
        "ev_runbook_valid_123": Evidence(
            organization_id=scope.organization_id,
            service_id=scope.service_id,
            run_id=scope.run_id,
            evidence_id="ev_runbook_valid_123",
            source="runbooks",
            observed_at=now,
            redacted_snippet="Pool recovery procedures",
            locator="runbook:postgres_pool.md:section1",
        )
    }
    with pytest.raises(
        ValueError,
        match="High confidence causal claim cannot rely solely on runbook documentation",
    ):
        validate_evidence(
            res,
            scope=scope,
            returned_ledger=returned_ledger,
        )


# =========================================================================
# 8. ADK TOOL GATEWAY TESTS: RETRIEVE RUNBOOK & RELATED INCIDENTS
# =========================================================================


def test_gateway_retrieve_runbook_and_register_evidence() -> None:
    db = TestingSessionLocal()
    try:
        user, org, _ = create_tenant(db)
        svc = Service(name="checkout", organization_id=org.id)
        db.add(svc)
        db.flush()

        # Seed runbook
        doc = Document(
            organization_id=org.id,
            service_id=svc.id,
            filename="postgres_pool.md",
            title="Postgres Connection Pool Runbook",
            checksum="abc123hash",
            status="READY",
            created_by=user.id,
            version=1,
            indexed_at=datetime.now(UTC),
        )
        db.add(doc)
        db.flush()

        chunk = DocumentChunk(
            document_id=doc.id,
            organization_id=org.id,
            service_id=svc.id,
            chunk_index=0,
            section_title="Pool Recovery Procedures",
            section_path="Postgres Runbook > Pool Recovery Procedures",
            content="When connection pool saturates, scale up pooler and drain idle connections.",
            content_hash="chunkhash123",
            token_count=18,
            embedding=[0.05] * 768,
        )
        db.add(chunk)

        inc = Incident(
            organization_id=org.id,
            service_id=svc.id,
            fingerprint="fp_checkout_pool_exhaustion",
            title="Elevated 500s on checkout",
            severity="high",
            status="investigating",
            started_at=datetime.now(UTC),
        )
        db.add(inc)
        db.flush()

        run = InvestigationRun(
            incident_id=inc.id,
            organization_id=org.id,
            service_id=svc.id,
            status="RUNNING",
        )
        db.add(run)
        db.commit()

        # Initialize Gateway with Scope and db session
        scope = Scope(
            organization_id=org.id,
            service_id=svc.id,
            run_id=run.id,
        )
        gateway = ReadOnlyToolGateway(
            scope=scope,
            incident=inc,
            run_record=run,
            db_session=db,
        )

        # Call retrieve_runbook
        tool_res = gateway.retrieve_runbook(
            question="How to fix postgres connection pool exhaustion?",
            limit=3,
        )
        assert tool_res["trust"] == "UNTRUSTED_SOURCE"
        assert tool_res["count"] >= 1
        first_chunk = tool_res["chunks"][0]
        assert first_chunk["evidence_id"].startswith("ev_runbook_")
        assert "Pool Recovery Procedures" in first_chunk["section"]
        assert first_chunk["document_version"] == 1

        # Check evidence registered in gateway ledger
        assert first_chunk["evidence_id"] in gateway.evidence_ledger
        assert gateway.evidence_ledger[first_chunk["evidence_id"]].source == "runbooks"

        # Call get_related_incidents
        inc_res = gateway.get_related_incidents(
            symptoms="checkout pool exhaustion 500",
            limit=3,
        )
        assert inc_res["trust"] == "UNTRUSTED_SOURCE"
        assert "incidents" in inc_res
    finally:
        db.close()
