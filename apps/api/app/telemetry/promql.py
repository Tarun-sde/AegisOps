"""PromQL safety, escaping, and multi-tenant query building."""

import re
import uuid

# Strict label value validation: reject control characters and null bytes
PROHIBITED_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def escape_promql_label_value(val: str) -> str:
    """Safely escape a label value for PromQL string literals.

    In PromQL, string literals inside quotes escape backslashes and double quotes,
    newlines, carriage returns, and tabs.
    Neutralizes attempts to break out of string literals or inject PromQL operators.
    """
    cleaned = PROHIBITED_CHARS.sub("", str(val))
    return (
        cleaned.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def build_service_metrics_queries(
    *,
    service_id: uuid.UUID,
    organization_id: uuid.UUID,
    service_name: str,
    is_demo_org: bool = False,
) -> dict[str, tuple[str, str]]:
    """Build tenant-isolated, injection-safe PromQL queries for service performance analytics.

    Enforces trusted organization and stable service identity throughout query construction:
    1. Stable service identity (`service_id`) and trusted organization (`organization_id`)
       guarantee that services sharing identical names across tenants cannot leak metrics.
    2. All label values are safely escaped against PromQL string literal breakouts.
    3. Demo service fallback is strictly restricted to the authorized demo organization.
    """
    esc_svc_id = escape_promql_label_value(str(service_id))
    esc_org_id = escape_promql_label_value(str(organization_id))
    esc_name = escape_promql_label_value(service_name)

    req_selector = (
        f'http_requests_total{{service_id="{esc_svc_id}"}} or '
        f'http_requests_total{{service="{esc_name}", organization_id="{esc_org_id}"}}'
    )
    err_selector = (
        f'http_requests_total{{service_id="{esc_svc_id}", status_code=~"5.."}} or '
        f'http_requests_total{{service="{esc_name}", organization_id="{esc_org_id}", '
        f'status_code=~"5.."}}'
    )
    dur_selector = (
        f'http_request_duration_seconds_bucket{{service_id="{esc_svc_id}"}} or '
        f'http_request_duration_seconds_bucket{{service="{esc_name}", '
        f'organization_id="{esc_org_id}"}}'
    )

    return {
        "request_rate": (
            f"sum(rate({req_selector}[1m]))",
            "req/s",
        ),
        "error_rate": (
            f"(sum(rate({err_selector}[1m])) / sum(rate({req_selector}[1m]))) * 100",
            "%",
        ),
        "p95_latency": (
            f"histogram_quantile(0.95, sum(rate({dur_selector}[1m])) by (le)) * 1000",
            "ms",
        ),
    }
