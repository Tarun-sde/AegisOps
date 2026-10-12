"""Predefined incident simulation scenario catalog (Phase 7).

Security invariant:
- All scenario definitions are version-controlled in code.
- No arbitrary chaos scripts or shell execution.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioItem:
    scenario_id: str
    name: str
    description: str
    affected_service: str
    allowed_environment: str
    fault_type: str
    expected_cause_category: str
    expected_signal_types: tuple[str, ...]
    permitted_actions: tuple[str, ...]
    maximum_duration_seconds: int
    risk_level: str  # LOW | MEDIUM | HIGH
    enabled: bool = True


SCENARIO_CATALOG: dict[str, ScenarioItem] = {
    "S01_CHECKOUT_500": ScenarioItem(
        scenario_id="S01_CHECKOUT_500",
        name="Checkout HTTP 500 Failure",
        description=(
            "Controlled feature flag causing payment gateway timeout exceptions on POST /checkout "
            "with increased 5xx error ratio."
        ),
        affected_service="shop-api",
        allowed_environment="staging",
        fault_type="APPLICATION_EXCEPTION",
        expected_cause_category="PAYMENT_GATEWAY_TIMEOUT",
        expected_signal_types=(
            "http_5xx_rate",
            "error_logs",
            "request_traces",
            "alertmanager_alert",
        ),
        permitted_actions=("restart_demo_service", "reset_demo_fault"),
        maximum_duration_seconds=300,
        risk_level="LOW",
    ),
    "S02_SLOW_DB_QUERIES": ScenarioItem(
        scenario_id="S02_SLOW_DB_QUERIES",
        name="Slow Database Queries",
        description=(
            "Deliberately introduces bounded latency (800ms) into shop-api database "
            "query operations, spiking p95 response time."
        ),
        affected_service="shop-api",
        allowed_environment="staging",
        fault_type="DATABASE_LATENCY",
        expected_cause_category="SLOW_DATABASE_DEPENDENCY",
        expected_signal_types=("p95_latency_spike", "database_trace_spans", "slow_query_logs"),
        permitted_actions=("restart_demo_service", "reset_demo_fault"),
        maximum_duration_seconds=300,
        risk_level="LOW",
    ),
    "S03_DB_POOL_EXHAUSTION": ScenarioItem(
        scenario_id="S03_DB_POOL_EXHAUSTION",
        name="Database Connection Pool Exhaustion",
        description=(
            "Saturates database connection pool, causing connection timeouts, 503 errors, "
            "and queue backlog signals."
        ),
        affected_service="shop-api",
        allowed_environment="staging",
        fault_type="POOL_EXHAUSTION",
        expected_cause_category="CONNECTION_POOL_SATURATION",
        expected_signal_types=("pool_wait_queue", "connection_timeout_logs", "http_503_errors"),
        permitted_actions=("restart_demo_service", "reset_demo_fault"),
        maximum_duration_seconds=300,
        risk_level="LOW",
    ),
    "S04_BROKEN_RELEASE": ScenarioItem(
        scenario_id="S04_BROKEN_RELEASE",
        name="Broken Application Release Regression",
        description=(
            "Switches shop-api to a known broken release v0.1.1-buggy with behavioral regression "
            "and deployment metadata correlation."
        ),
        affected_service="shop-api",
        allowed_environment="staging",
        fault_type="RELEASE_REGRESSION",
        expected_cause_category="DEPLOYMENT_REGRESSION",
        expected_signal_types=(
            "build_info_gauge",
            "deploy_timestamp",
            "checkout_errors",
            "commit_sha_timeline",
        ),
        permitted_actions=("rollback_demo_release", "restart_demo_service"),
        maximum_duration_seconds=300,
        risk_level="MEDIUM",
    ),
    "S05_SERVICE_UNAVAILABLE": ScenarioItem(
        scenario_id="S05_SERVICE_UNAVAILABLE",
        name="Service Unavailable / Probe Failure",
        description=(
            "Simulates service container unavailability by failing /healthz probes "
            "and rejecting HTTP connections."
        ),
        affected_service="shop-api",
        allowed_environment="staging",
        fault_type="CONTAINER_UNAVAILABLE",
        expected_cause_category="SERVICE_UNAVAILABLE",
        expected_signal_types=("healthz_503", "prometheus_up_zero", "failed_readiness_probe"),
        permitted_actions=("restart_demo_service", "reset_demo_fault"),
        maximum_duration_seconds=300,
        risk_level="LOW",
    ),
    "S06_SLOW_DOWNSTREAM": ScenarioItem(
        scenario_id="S06_SLOW_DOWNSTREAM",
        name="Slow Downstream Dependency",
        description=(
            "Introduces bounded 1200ms latency into downstream inventory dependency "
            "with propagated W3C trace context."
        ),
        affected_service="shop-api",
        allowed_environment="staging",
        fault_type="DOWNSTREAM_LATENCY",
        expected_cause_category="DOWNSTREAM_DEPENDENCY_LATENCY",
        expected_signal_types=(
            "distributed_trace_hierarchy",
            "downstream_span_delay",
            "timeout_warning_logs",
        ),
        permitted_actions=("restart_demo_service", "reset_demo_fault"),
        maximum_duration_seconds=300,
        risk_level="LOW",
    ),
}


def get_scenario(scenario_id: str) -> ScenarioItem | None:
    return SCENARIO_CATALOG.get(scenario_id)


def list_scenarios() -> list[ScenarioItem]:
    return list(SCENARIO_CATALOG.values())
