# ADR-023: Phase 3 Foundation — Production-Oriented Authentication, Centralized RBAC, Multi-Tenant Scoping, SSRF-Guarded Connectors & Tempo Distributed Tracing

- **Status:** ACCEPTED — VERIFIED
- **Date:** 2026-10-11
- **Governing rules:** `docs/AGENTS_DECISION_LOG_RULES.md`, `AEGISOPS_MASTER_IMPLEMENTATION_PLAN.md` Phase 3.
- **Related decisions:** ADR-001, ADR-002, ADR-019, ADR-021, ADR-022, DEC-267–DEC-276.

## Context and Problem Statement

Phase 0–2 established incident ingestion, automated AI investigations with Google ADK, and rigorous telemetry verification. However, all endpoints operated under single-tenant implicit access without user authentication, role-based authorization, or distributed trace visibility.

To transition AegisOps into a multi-tenant, production-grade foundation, Phase 3 requires:
1. Durable, secure user authentication without unpinned third-party identity dependencies.
2. Centralized role-based access control (RBAC) enforcing least-privilege permissions across tenants.
3. Multi-tenant database schema and query scoping preventing data leakage between organizations.
4. Defense-in-depth SSRF protection for operator-configured service connectors.
5. Distributed trace ingestion and root-cause trace inspection via Grafana Tempo.
6. Integration of a bounded trace inspection tool into the Google ADK investigation agent.
7. Next.js user interfaces for authentication, service onboarding, and waterfall trace timeline visualization.

## Decisions

### 1. Authentication Architecture (DEC-267)
- **Password Security:** Standard library `hashlib.scrypt` with cryptographically random 16-byte salt (`secrets.token_hex(16)`), parameter values $N=16384$, $r=8$, $p=1$. Constant-time verification via `secrets.compare_digest`.
- **Session Tokens:** Server-side opaque 32-byte tokens (`secrets.token_urlsafe(32)`) stored SHA-256 hashed in `user_sessions`. Raw tokens are never stored in plaintext.
- **Cookie Transport:** Tokens transported via `HttpOnly`, `SameSite="lax"`, secure cookie (`aegisops_session`). Dual Bearer token extraction supported for automated testing and CLI clients.

### 2. CSRF Mitigation (DEC-268)
- Double-submit CSRF cookie pattern (`aegisops_csrf`) issued on login/registration.
- Mutating HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) authenticate cookie sessions only when `x-csrf-token` header matches the CSRF cookie value in constant time. Safe idempotent methods (`GET`, `HEAD`, `OPTIONS`) and programmatic Bearer token requests are exempt.

### 3. Centralized RBAC & Hierarchy (DEC-269)
- Structured role hierarchy: `owner` (4) > `admin` (3) > `member` (2) > `viewer` (1).
- Enforced at FastAPI dependency level via `TenantContext` and `require_role(min_role)`:
  - `owner` / `admin`: organization administration, member invitations, service registration, connector verification.
  - `member`: incident investigation initiation, investigation cancellation.
  - `viewer`: strictly read-only access to services, incidents, traces, and evidence ledgers. Mutation attempts return `403 Forbidden`.

### 4. Multi-Tenant Scoping (DEC-270)
- `TenantContext` automatically resolves active organization from session context or `X-Organization-ID` header.
- All service, incident, investigation, and member queries explicitly filter on `organization_id == context.organization.id`. Cross-tenant requests return `404 Not Found` (services/incidents) or `403 Forbidden` (members).

### 5. SSRF Guard for External Connectors (DEC-271)
- Operator-provided URLs for healthcheck and connector verification pass through `validate_connector_url`:
  - Enforces `http` and `https` schemes.
  - Prohibits cloud metadata addresses (`169.254.169.254`, `metadata.google.internal`, `instance-data`).
  - Prohibits loopback (`127.0.0.0/8`) and link-local ranges.
  - Prohibits private RFC 1918 networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) for external connectors.

### 6. Distributed Tracing with Grafana Tempo (DEC-272, DEC-273, DEC-274, DEC-275)
- **Tempo Integration:** Grafana Tempo added to observability stack on port 3200 (HTTP API) and 4317 (gRPC).
- **Collector Pipeline:** OpenTelemetry Collector updated with traces pipeline forwarding OTLP traces to `tempo:4317`.
- **Application Instrumentation:** Express `shop-api` extracts or generates W3C `traceparent`, propagates `trace_id` in logs and HTTP response headers (`x-trace-id`), and asynchronously exports OTLP spans.
- **Control Plane Endpoint:** `GET /api/v1/traces/{trace_id}` queries Tempo API, normalizes span trees, and bounds payload to top 20 spans.
- **Agent Tool:** `ReadOnlyToolGateway.get_trace_summary(trace_id)` bounds trace payloads to 32KB, registers spans into the evidence ledger (`ev_trace_...`), and persists to PostgreSQL `evidence_items`.

### 7. Database Migration & Backward Compatibility (DEC-276)
- Alembic migration `0005_phase3_auth_rbac_tracing.py` creates `users`, `user_sessions`, `memberships`, `audit_events`, and updates `services` and `investigation_runs`.
- Safe backfill creates default demo organization (`AegisOps Demo`) and demo account (`demo@aegisops.local`), ensuring existing Phase 1 and 2 tests and scripts execute without breakage.

## Consequences & Verification

- **Security Posture:** All endpoints authenticated. No plaintext passwords or tokens in database. CSRF and SSRF guards active.
- **Test Coverage:** Suite of 9 Phase 3 tests (`test_auth_rbac_tracing.py`) covers authentication lifecycles, CSRF validation, cross-tenant isolation, role permission gates, SSRF blocking, and distributed trace summarization.
- **Total Tests:** 98 non-integration Python tests pass; 1 shop-api test suite passes; Web ESLint, Prettier, and TypeScript typecheck pass with zero warnings.
