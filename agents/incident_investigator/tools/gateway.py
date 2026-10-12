import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
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

    def get_recent_deployments(
        self, repository: str | None = None, limit: int = 5
    ) -> dict[str, Any]:
        """Retrieve recent software deployments and commit metadata for authorized repository.

        Args:
            repository: Optional repository override (must match authorized service repository).
            limit: Maximum number of deployment/commit records to retrieve (1-5).
        """
        t0 = time.perf_counter()
        self._check_budget()
        args = {"repository": repository, "limit": limit}

        limit = max(1, min(limit, 5))

        # 1. Resolve authorized service repository
        authorized_repo = "AegisOps/shop-api"
        env = "staging"
        if self.db_session and self.scope.service_id:
            from apps.api.app.models import Service

            svc = self.db_session.get(Service, self.scope.service_id)
            if svc:
                if svc.github_repo:
                    authorized_repo = svc.github_repo
                env = svc.environment

        # 2. Enforce strict repository boundary (T7 Cross-tenant protection)
        if repository and repository.strip().lower() != authorized_repo.strip().lower():
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution(
                "get_recent_deployments", args, "error", latency, "UNAUTHORIZED_REPOSITORY"
            )
            return {
                "trust": "UNTRUSTED_SOURCE",
                "error": (
                    f"Access denied: repository '{repository}' is outside the authorized "
                    f"scope for service '{self.scope.service_id}'. Authorized: '{authorized_repo}'."
                ),
                "deployments": [],
            }

        try:
            from apps.api.app.integrations.github import ScopedGitHubClient

            client = ScopedGitHubClient()
            deployments = client.get_recent_deployments(
                authorized_repo, environment=env, limit=limit
            )

            snippet = json.dumps(deployments)
            if len(snippet) > MAX_PAYLOAD_BYTES:
                snippet = snippet[:MAX_PAYLOAD_BYTES]

            now_utc = datetime.now(UTC)
            ev_id = f"ev_deploy_{hashlib.sha256(snippet.encode('utf-8')).hexdigest()[:8]}"
            self._persist_evidence(
                evidence_id=ev_id,
                source="deployments",
                observed_at=now_utc,
                locator=f"github:repo:{authorized_repo}:deployments",
                redacted_snippet=snippet,
                query_metadata={"repository": authorized_repo, "environment": env, "limit": limit},
            )
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_recent_deployments", args, "success", latency)
            return {
                "trust": "UNTRUSTED_SOURCE",
                "repository": authorized_repo,
                "environment": env,
                "deployment_count": len(deployments),
                "deployments": deployments,
                "evidence_id": ev_id,
            }
        except Exception as err:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_recent_deployments", args, "error", latency, "GITHUB_ERROR")
            return {
                "trust": "UNTRUSTED_SOURCE",
                "error": f"Deployment context query failed: {err}",
                "deployments": [],
                "limitation": "Deployment metadata unavailable from upstream provider",
            }

    def retrieve_runbook(
        self, question: str, service_context: str | None = None, limit: int = 5
    ) -> dict[str, Any]:
        """Tenant-scoped hybrid retrieval of operational runbooks and troubleshooting documentation.

        Returns relevant document excerpts with citation evidence IDs (ev_runbook_...).
        Guidance in runbooks is OPERATIONAL CONTEXT, not proof of incident causality.
        """
        t0 = time.perf_counter()
        self._check_budget()
        bound_limit = max(1, min(limit, 5))
        safe_question = (question or "").strip()[:500]
        args: dict[str, Any] = {
            "question": safe_question,
            "service_context": service_context,
            "limit": bound_limit,
        }

        if not safe_question:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("retrieve_runbook", args, "error", latency, "EMPTY_QUERY")
            return {
                "trust": "UNTRUSTED_SOURCE",
                "query": "",
                "count": 0,
                "chunks": [],
                "note": "Question was empty; no runbook retrieved.",
            }

        try:
            if not self.db_session:
                latency = (time.perf_counter() - t0) * 1000
                self._record_execution("retrieve_runbook", args, "error", latency, "NO_DB_SESSION")
                return {
                    "trust": "UNTRUSTED_SOURCE",
                    "query": safe_question,
                    "count": 0,
                    "chunks": [],
                    "limitation": "Database session unavailable for runbook retrieval",
                }

            import asyncio
            import concurrent.futures

            from apps.api.app.rag.retrieval import HybridRetrievalService

            retrieval_service = HybridRetrievalService(self.db_session)

            # Resolve service_id if provided or default to scope service
            target_service_id = self.scope.service_id

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    res = pool.submit(
                        asyncio.run,
                        retrieval_service.search(
                            organization_id=self.scope.organization_id,
                            query=safe_question,
                            service_id=target_service_id,
                            limit=bound_limit,
                            mode="hybrid",
                        ),
                    ).result()
            else:
                res = asyncio.run(
                    retrieval_service.search(
                        organization_id=self.scope.organization_id,
                        query=safe_question,
                        service_id=target_service_id,
                        limit=bound_limit,
                        mode="hybrid",
                    )
                )

            chunk_outputs: list[dict[str, Any]] = []
            now_utc = datetime.now(UTC)

            for chunk in res.results:
                ev_id = chunk.evidence_id
                snippet = f"[{chunk.title} > {chunk.section_path}]\n{chunk.content}"
                if len(snippet) > MAX_PAYLOAD_BYTES:
                    snippet = snippet[:MAX_PAYLOAD_BYTES]

                self._persist_evidence(
                    evidence_id=ev_id,
                    source="runbooks",
                    observed_at=now_utc,
                    locator=f"runbook:{chunk.document_id}:{chunk.chunk_id}#{chunk.section_title}",
                    redacted_snippet=snippet,
                    query_metadata={
                        "query": safe_question,
                        "relevance_score": chunk.relevance_score,
                        "document_version": chunk.document_version,
                    },
                )
                chunk_outputs.append(
                    {
                        "evidence_id": ev_id,
                        "document_id": chunk.document_id,
                        "title": chunk.title,
                        "section": chunk.section_title,
                        "section_path": chunk.section_path,
                        "document_version": chunk.document_version,
                        "relevance_score": chunk.relevance_score,
                        "snippet": chunk.content[:2000],
                    }
                )

            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("retrieve_runbook", args, "success", latency)
            return {
                "trust": "UNTRUSTED_SOURCE",
                "query": safe_question,
                "retrieval_mode": res.mode,
                "count": len(chunk_outputs),
                "chunks": chunk_outputs,
                "usage_policy": (
                    "Operational guidance must be verified against current metrics, logs, "
                    "and traces. Precedence in documentation is not proof of causality."
                ),
            }

        except Exception as err:
            logger.exception(f"Runbook retrieval error: {err}")
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("retrieve_runbook", args, "error", latency, "RETRIEVAL_ERROR")
            return {
                "trust": "UNTRUSTED_SOURCE",
                "query": safe_question,
                "error": f"Runbook retrieval failed: {err}",
                "chunks": [],
                "limitation": "Runbook knowledge base unavailable during investigation",
            }

    def get_related_incidents(self, symptoms: str = "", limit: int = 5) -> dict[str, Any]:
        """Tenant-scoped search for historically resolved incidents matching symptom patterns.

        Returns prior incident summaries with evidence IDs (ev_hist_...).
        Prior resolution is correlation context, not proof of identical root cause.
        """
        t0 = time.perf_counter()
        self._check_budget()
        bound_limit = max(1, min(limit, 5))
        safe_symptoms = (symptoms or "").strip()[:500]
        args: dict[str, Any] = {"symptoms": safe_symptoms, "limit": bound_limit}

        if not self.db_session:
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_related_incidents", args, "error", latency, "NO_DB_SESSION")
            return {
                "trust": "UNTRUSTED_SOURCE",
                "count": 0,
                "incidents": [],
                "limitation": "Database session unavailable for historical incident lookup",
            }

        try:
            from apps.api.app.rag.related_incidents import RelatedIncidentService

            service = RelatedIncidentService(self.db_session)
            current_inc_id = self.incident.id if self.incident else None
            results = service.get_related_incidents(
                organization_id=self.scope.organization_id,
                service_id=self.scope.service_id,
                symptoms=safe_symptoms,
                exclude_incident_id=current_inc_id,
                limit=bound_limit,
            )

            now_utc = datetime.now(UTC)
            incident_outputs: list[dict[str, Any]] = []

            for inc in results:
                ev_id = inc.evidence_id
                snippet = (
                    f"[{inc.title} - Severity: {inc.severity} - Status: {inc.status}]\n"
                    f"Match Reason: {inc.match_reason}\n"
                    f"Resolved: {inc.resolved_at or 'N/A'}\n"
                    f"Outcome Summary: {inc.resolution_summary or 'No documented summary'}"
                )
                if len(snippet) > MAX_PAYLOAD_BYTES:
                    snippet = snippet[:MAX_PAYLOAD_BYTES]

                self._persist_evidence(
                    evidence_id=ev_id,
                    source="historical_incidents",
                    observed_at=now_utc,
                    locator=f"incident:{inc.incident_id}",
                    redacted_snippet=snippet,
                    query_metadata={"symptoms": safe_symptoms, "match_reason": inc.match_reason},
                )
                incident_outputs.append(
                    {
                        "evidence_id": ev_id,
                        "incident_id": inc.incident_id,
                        "title": inc.title,
                        "severity": inc.severity,
                        "status": inc.status,
                        "started_at": inc.started_at,
                        "resolved_at": inc.resolved_at,
                        "match_reason": inc.match_reason,
                        "resolution_summary": inc.resolution_summary,
                    }
                )

            latency = (time.perf_counter() - t0) * 1000
            self._record_execution("get_related_incidents", args, "success", latency)
            return {
                "trust": "UNTRUSTED_SOURCE",
                "count": len(incident_outputs),
                "incidents": incident_outputs,
                "note": (
                    "Historical similarities provide diagnostic hypotheses, not proof of causation."
                ),
            }

        except Exception as err:
            logger.exception(f"Related incidents lookup error: {err}")
            latency = (time.perf_counter() - t0) * 1000
            self._record_execution(
                "get_related_incidents", args, "error", latency, "INCIDENT_LOOKUP_ERROR"
            )
            return {
                "trust": "UNTRUSTED_SOURCE",
                "error": f"Related incident query failed: {err}",
                "incidents": [],
                "limitation": "Historical incident repository query failed",
            }

    def create_remediation_proposal(
        self,
        action_catalog_id: str,
        parameters: dict[str, Any],
        reason: str,
        expected_outcome: str,
        known_risks: str = "",
        supporting_evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Tool enabling ADK agent to propose an allowlisted remediation action (DEC-324).

        Security invariant:
        - Creates a proposal in PROPOSED state.
        - ZERO execution capability exists in this tool.
        """
        self._check_budget()
        start = time.perf_counter()

        from apps.api.app.actions.catalog import get_catalog_item, validate_proposal_parameters
        from apps.api.app.models import ActionProposal

        # Validate catalog item
        catalog_item = get_catalog_item(action_catalog_id)
        if not catalog_item:
            error_msg = f"Action '{action_catalog_id}' not allowed in catalog."
            self._record_execution(
                "create_remediation_proposal",
                {"action_catalog_id": action_catalog_id},
                "error",
                0.0,
                "VALIDATION_ERROR",
            )
            raise ValueError(error_msg)

        # Validate parameters against Pydantic schema
        canonical_params, param_hash = validate_proposal_parameters(action_catalog_id, parameters)

        # Verify supporting evidence IDs exist in evidence ledger
        valid_evidence_ids: list[str] = []
        if supporting_evidence_ids:
            for ev_id in supporting_evidence_ids:
                if ev_id in self.evidence_ledger:
                    valid_evidence_ids.append(ev_id)

        proposal_id = uuid.uuid4()
        if self.db_session and self.incident:
            proposal = ActionProposal(
                id=proposal_id,
                organization_id=self.scope.organization_id,
                service_id=self.scope.service_id,
                environment="staging",
                investigation_run_id=self.scope.run_id,
                action_catalog_id=action_catalog_id,
                immutable_parameters=canonical_params,
                parameters_hash=param_hash,
                reason=reason,
                expected_outcome=expected_outcome,
                known_risks=known_risks or "Standard bounded staging remediation operation",
                supporting_evidence_ids=valid_evidence_ids,
                status="PROPOSED",
                idempotency_key=f"agent_proposal:{self.scope.run_id}:{action_catalog_id}",
                expires_at=datetime.now(UTC)
                + timedelta(seconds=catalog_item.default_expiry_seconds),
            )
            self.db_session.add(proposal)
            self.db_session.flush()

        latency_ms = (time.perf_counter() - start) * 1000.0
        self._record_execution(
            "create_remediation_proposal",
            {"action_catalog_id": action_catalog_id, "parameters": canonical_params},
            "success",
            latency_ms,
        )

        return {
            "proposal_id": str(proposal_id),
            "status": "PROPOSED",
            "action_catalog_id": action_catalog_id,
            "parameters_hash": param_hash,
            "message": (
                "Remediation proposal submitted for human review. "
                "It will NOT execute until authorized by an administrator."
            ),
        }
