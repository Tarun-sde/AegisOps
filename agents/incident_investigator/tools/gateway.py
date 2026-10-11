import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from agents.incident_investigator.tools.redaction import redact_sensitive_text
from apps.api.app.models import EvidenceItem, Incident, InvestigationRun, ToolExecution
from apps.api.app.schemas import Evidence, Scope

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 12
MAX_LOG_RECORDS = 50
MAX_PAYLOAD_BYTES = 32768
DEFAULT_HTTP_TIMEOUT = 5.0

ALLOWED_METRICS = {
    "http_5xx_error_rate": (
        'sum(rate(http_requests_total{status_code=~"5.."}[1m])) / '
        "sum(rate(http_requests_total[1m]))"
    ),
    "http_requests_total": (
        'sum(rate(http_requests_total{route="/checkout"}[1m])) by (status_code, route)'
    ),
    "http_request_duration_p95": (
        "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le))"
    ),
}


class BudgetExceededError(ValueError):
    """Raised when tool call budget is exhausted."""


class ReadOnlyToolGateway:
    """Deterministic read-only tool gateway enforcing boundaries, budgets, and evidence tracking."""

    def __init__(
        self,
        scope: Scope,
        incident: Incident | None = None,
        run_record: InvestigationRun | None = None,
        db_session: Any = None,
        prom_url: str | None = None,
        loki_url: str | None = None,
    ) -> None:
        self.scope = scope
        self.incident = incident
        self.run_record = run_record
        self.db_session = db_session
        self.prom_url = prom_url or os.environ.get(
            "AEGISOPS_PROM_URL",
            "http://prometheus:9090" if os.environ.get("IN_DOCKER") else "http://127.0.0.1:9090",
        )
        self.loki_url = loki_url or os.environ.get(
            "AEGISOPS_LOKI_URL",
            "http://loki:3100" if os.environ.get("IN_DOCKER") else "http://127.0.0.1:3100",
        )
        self.evidence_ledger: dict[str, Evidence] = {}
        self.tool_call_count = 0

    def _check_budget(self) -> None:
        if self.tool_call_count >= MAX_TOOL_CALLS:
            raise BudgetExceededError(f"Tool budget exhausted (maximum {MAX_TOOL_CALLS} calls)")
        self.tool_call_count += 1
        if self.run_record:
            self.run_record.tool_call_count = self.tool_call_count

    def _record_execution(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        status: str,
        latency_ms: float,
        error_category: str | None = None,
    ) -> None:
        if self.db_session and self.run_record:
            execution = ToolExecution(
                run_id=self.scope.run_id,
                tool_name=tool_name,
                arguments=arguments,
                status=status,
                latency_ms=latency_ms,
                error_category=error_category,
            )
            self.db_session.add(execution)
            self.db_session.flush()

    def _persist_evidence(
        self,
        evidence_id: str,
        source: str,
        observed_at: datetime,
        locator: str,
        redacted_snippet: str,
        query_metadata: dict[str, Any],
    ) -> Evidence:
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        evidence = Evidence(
            organization_id=self.scope.organization_id,
            service_id=self.scope.service_id,
            run_id=self.scope.run_id,
            evidence_id=evidence_id,
            source=source,  # type: ignore[arg-type]
            observed_at=observed_at,
            locator=locator,
            redacted_snippet=redacted_snippet,
        )
        self.evidence_ledger[evidence_id] = evidence

        if self.db_session and self.run_record:
            content_hash = hashlib.sha256(redacted_snippet.encode("utf-8")).hexdigest()
            item = EvidenceItem(
                evidence_id=evidence_id,
                run_id=self.scope.run_id,
                organization_id=self.scope.organization_id,
                service_id=self.scope.service_id,
                source=source,
                observed_at=observed_at,
                locator=locator,
                redacted_snippet=redacted_snippet,
                content_hash=content_hash,
                query_metadata=query_metadata,
            )
            self.db_session.add(item)
            self.db_session.flush()

        return evidence

    def get_incident_snapshot(self) -> dict[str, Any]:
        """Retrieve bounded incident context and triggering alert information. No arguments."""
        t0 = time.perf_counter()
        self._check_budget()
        try:
            observed_at = (
                self.incident.started_at
                if (self.incident and self.incident.started_at)
                else datetime.now(UTC)
            )
            inc_id = str(self.incident.id) if self.incident else "mock-incident-id"
            title = self.incident.title if self.incident else "Incident snapshot"
            severity = self.incident.severity if self.incident else "critical"
            status = self.incident.status if self.incident else "firing"
            fingerprint = self.incident.fingerprint if self.incident else "fp_snapshot"
            service_id = (
                str(self.incident.service_id) if self.incident else str(self.scope.service_id)
            )
            content = (
                f"Incident '{title}' on service {service_id}. "
                f"Severity: {severity}. Status: {status}. "
                f"Fingerprint: {fingerprint}. Started at: {observed_at.isoformat()}."
            )
            ev_id = f"ev_alert_{hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]}"
            self._persist_evidence(
                evidence_id=ev_id,
                source="alert",
                observed_at=observed_at,
                locator=f"incident:{inc_id}",
                redacted_snippet=content,
                query_metadata={"incident_id": inc_id},
            )
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_incident_snapshot", {}, "success", latency)
            return {
                "trust": "UNTRUSTED_SOURCE",
                "incident_id": inc_id,
                "title": title,
                "severity": severity,
                "status": status,
                "started_at": observed_at.isoformat(),
                "evidence_id": ev_id,
            }
        except Exception:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_incident_snapshot", {}, "error", latency, "SYSTEM_ERROR")
            raise

    def query_service_metrics(self, metric_name: str, window_minutes: int = 15) -> dict[str, Any]:
        """Query bounded HTTP service metrics.

        metric_name must be one of:
        - 'http_5xx_error_rate': 5xx error ratio over 1m rate
        - 'http_requests_total': request rate breakdown by status code and route
        - 'http_request_duration_p95': 95th percentile latency
        """
        t0 = time.perf_counter()
        self._check_budget()
        args = {"metric_name": metric_name, "window_minutes": window_minutes}

        if metric_name not in ALLOWED_METRICS:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("query_service_metrics", args, "error", latency, "BAD_ARGUMENT")
            return {
                "trust": "UNTRUSTED_SOURCE",
                "error": f"Invalid metric '{metric_name}'. Allowed: {list(ALLOWED_METRICS.keys())}",
            }

        window_minutes = max(1, min(window_minutes, 30))
        promql = ALLOWED_METRICS[metric_name]

        try:
            encoded_query = urllib.parse.urlencode({"query": promql})
            url = f"{self.prom_url}/api/v1/query?{encoded_query}"
            req = urllib.request.Request(url, headers={"User-Agent": "AegisOps-Investigator/1.0"})
            with urllib.request.urlopen(req, timeout=DEFAULT_HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = data.get("data", {}).get("result", [])
            normalized = []
            for r in results:
                metric_labels = r.get("metric", {})
                val = r.get("value", [0, "0"])[1]
                normalized.append({"labels": metric_labels, "value": float(val)})

            snippet = json.dumps(normalized)
            if len(snippet) > MAX_PAYLOAD_BYTES:
                snippet = snippet[:MAX_PAYLOAD_BYTES]

            now_utc = datetime.now(UTC)
            ev_id = f"ev_metric_{hashlib.sha256(snippet.encode('utf-8')).hexdigest()[:8]}"
            self._persist_evidence(
                evidence_id=ev_id,
                source="metrics",
                observed_at=now_utc,
                locator=f"promql:{metric_name}",
                redacted_snippet=snippet,
                query_metadata={"promql": promql, "window_minutes": window_minutes},
            )
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("query_service_metrics", args, "success", latency)
            return {
                "trust": "UNTRUSTED_SOURCE",
                "metric_name": metric_name,
                "series": normalized,
                "evidence_id": ev_id,
            }
        except Exception as err:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution(
                "query_service_metrics", args, "error", latency, "PROMETHEUS_UNAVAILABLE"
            )
            return {
                "trust": "UNTRUSTED_SOURCE",
                "error": f"Prometheus query failed: {err}",
                "series": [],
            }

    def search_service_logs(self, query: str = "", limit: int = 20) -> dict[str, Any]:
        """Search application logs for the authorized service with optional filter substring."""
        t0 = time.perf_counter()
        self._check_budget()
        args = {"query": query, "limit": limit}

        limit = max(1, min(limit, MAX_LOG_RECORDS))
        clean_query = query.replace('"', "").replace("\\", "").strip()
        logql = '{service_name="shop-api"}'
        if clean_query:
            logql += f' |= "{clean_query}"'

        try:
            encoded_query = urllib.parse.urlencode({"query": logql, "limit": limit})
            url = f"{self.loki_url}/loki/api/v1/query_range?{encoded_query}"
            req = urllib.request.Request(url, headers={"User-Agent": "AegisOps-Investigator/1.0"})
            with urllib.request.urlopen(req, timeout=DEFAULT_HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            streams = data.get("data", {}).get("result", [])
            lines = []
            for stream in streams:
                values = stream.get("values", [])
                for ts_ns, line_text in values:
                    redacted = redact_sensitive_text(line_text)
                    lines.append({"timestamp_ns": ts_ns, "message": redacted})
                    if len(lines) >= limit:
                        break
                if len(lines) >= limit:
                    break

            snippet = json.dumps(lines)
            if len(snippet) > MAX_PAYLOAD_BYTES:
                snippet = snippet[:MAX_PAYLOAD_BYTES]

            now_utc = datetime.now(UTC)
            ev_id = f"ev_log_{hashlib.sha256(snippet.encode('utf-8')).hexdigest()[:8]}"
            self._persist_evidence(
                evidence_id=ev_id,
                source="logs",
                observed_at=now_utc,
                locator=f"loki:{logql}",
                redacted_snippet=snippet,
                query_metadata={"logql": logql, "limit": limit},
            )
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("search_service_logs", args, "success", latency)
            return {
                "trust": "UNTRUSTED_SOURCE",
                "record_count": len(lines),
                "records": lines[:10],  # return top 10 to keep prompt bounded
                "evidence_id": ev_id,
            }
        except Exception as err:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution(
                "search_service_logs", args, "error", latency, "LOKI_UNAVAILABLE"
            )
            return {
                "trust": "UNTRUSTED_SOURCE",
                "error": f"Loki query failed: {err}",
                "records": [],
            }

    def get_trace_summary(self, trace_id: str) -> dict[str, Any]:
        """Retrieve bounded distributed trace spans for the specified trace ID from Tempo."""
        t0 = time.perf_counter()
        self._check_budget()
        args = {"trace_id": trace_id}
        try:
            from apps.api.app.telemetry.tempo import TempoClient, validate_trace_id

            clean_id = validate_trace_id(trace_id)
            client = TempoClient()
            summary = client.get_trace_summary(clean_id)

            if not summary:
                latency = (time.perf_counter() - t0) * 1000
                self._record_execution(
                    "get_trace_summary", args, "error", latency, "TRACE_NOT_FOUND"
                )
                return {
                    "trust": "UNTRUSTED_SOURCE",
                    "error": f"Trace '{clean_id}' not found in Tempo",
                    "trace_id": clean_id,
                }

            spans_data = [
                {
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "name": s.name,
                    "service": s.service_name,
                    "duration_ms": s.duration_ms,
                    "status_code": s.status_code,
                    "attributes": redact_sensitive_text(json.dumps(s.attributes)),
                }
                for s in summary.spans[:20]
            ]
            snippet = json.dumps(spans_data)
            if len(snippet) > MAX_PAYLOAD_BYTES:
                snippet = snippet[:MAX_PAYLOAD_BYTES]

            now_utc = datetime.now(UTC)
            ev_id = f"ev_trace_{hashlib.sha256(snippet.encode('utf-8')).hexdigest()[:8]}"
            self._persist_evidence(
                evidence_id=ev_id,
                source="traces",
                observed_at=now_utc,
                locator=f"tempo:trace:{clean_id}",
                redacted_snippet=snippet,
                query_metadata={"trace_id": clean_id, "span_count": summary.span_count},
            )
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_trace_summary", args, "success", latency)
            return {
                "trust": "UNTRUSTED_SOURCE",
                "trace_id": clean_id,
                "service_name": summary.service_name,
                "root_operation": summary.root_operation,
                "duration_ms": summary.duration_ms,
                "span_count": summary.span_count,
                "error_span_count": summary.error_span_count,
                "spans": spans_data,
                "evidence_id": ev_id,
            }
        except Exception as err:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_trace_summary", args, "error", latency, "TEMPO_ERROR")
            return {
                "trust": "UNTRUSTED_SOURCE",
                "error": f"Trace query failed: {err}",
                "trace_id": trace_id,
            }
