from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

from apps.api.app.schemas import SpanRead, TraceSummaryRead

logger = logging.getLogger(__name__)

HEX_TRACE_ID_PATTERN = re.compile(r"^[a-fA-F0-9]{32}$")
DEFAULT_TEMPO_TIMEOUT = 5.0


def validate_trace_id(trace_id: str) -> str:
    """Validate 128-bit hex trace ID format."""
    clean = trace_id.strip()
    if not HEX_TRACE_ID_PATTERN.match(clean):
        raise ValueError(
            f"Invalid trace ID '{trace_id}'. Must be a 32-character hexadecimal string."
        )
    return clean.lower()


class TempoClient:
    """Deterministic read-only HTTP adapter for Grafana Tempo distributed tracing."""

    def __init__(
        self, tempo_url: str | None = None, timeout: float = DEFAULT_TEMPO_TIMEOUT
    ) -> None:
        self.tempo_url = (
            tempo_url
            or os.environ.get(
                "AEGISOPS_TEMPO_URL",
                "http://tempo:3200" if os.environ.get("IN_DOCKER") else "http://127.0.0.1:3200",
            )
        ).rstrip("/")
        self.timeout = timeout

    def get_raw_trace(self, trace_id: str) -> dict[str, Any] | None:
        """Fetch raw trace representation from Tempo API."""
        valid_id = validate_trace_id(trace_id)
        url = f"{self.tempo_url}/api/traces/{valid_id}"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    data = response.read()
                    parsed = json.loads(data.decode("utf-8"))
                    if isinstance(parsed, dict):
                        return parsed
                    return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.info(f"Trace '{valid_id}' not found in Tempo.")
                return None
            logger.warning(f"Tempo HTTP error {e.code} querying trace '{valid_id}': {e.reason}")
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning(f"Tempo connection failure querying trace '{valid_id}': {e}")
            return None
        return None

    def get_trace_summary(self, trace_id: str) -> TraceSummaryRead | None:
        """Parse raw Tempo OTLP trace batch into structured, validated trace summary."""
        raw = self.get_raw_trace(trace_id)
        if not raw:
            return None
        return self.normalize_trace(raw, trace_id)

    def normalize_trace(self, raw_data: dict[str, Any], trace_id: str) -> TraceSummaryRead | None:
        """Normalize Tempo batches / resourceSpans into standardized SpanRead hierarchy."""
        spans: list[SpanRead] = []
        primary_service = "unknown"
        root_op = "unknown"
        total_duration_ms = 0.0

        # Handle both OTLP JSON formats: 'batches' or 'resourceSpans'
        batches = raw_data.get("batches") or raw_data.get("resourceSpans") or []
        for batch in batches:
            resource = batch.get("resource") or {}
            res_attrs = {
                attr.get("key"): (
                    attr.get("value", {}).get("stringValue")
                    or attr.get("value", {}).get("intValue")
                    or attr.get("value")
                )
                for attr in resource.get("attributes", [])
            }
            service_name = res_attrs.get("service.name") or "unknown"
            if primary_service == "unknown" and service_name != "unknown":
                primary_service = service_name

            scope_spans = batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []
            for scope in scope_spans:
                for span in scope.get("spans", []):
                    s_id = span.get("spanId") or span.get("span_id") or ""
                    p_id = span.get("parentSpanId") or span.get("parent_span_id") or None
                    name = span.get("name") or "operation"

                    start_nano = int(
                        span.get("startTimeUnixNano") or span.get("start_time_unix_nano") or 0
                    )
                    end_nano = int(
                        span.get("endTimeUnixNano") or span.get("end_time_unix_nano") or 0
                    )
                    duration_ms = max(0.0, (end_nano - start_nano) / 1_000_000)

                    # Extract attributes, combining resource-level provenance
                    # with span-level attributes
                    span_attrs: dict[str, Any] = dict(res_attrs)
                    for attr in span.get("attributes", []):
                        val_obj = attr.get("value", {})
                        if isinstance(val_obj, dict):
                            val = (
                                val_obj.get("stringValue")
                                or val_obj.get("intValue")
                                or val_obj.get("doubleValue")
                                or val_obj.get("boolValue")
                            )
                        else:
                            val = val_obj
                        span_attrs[attr.get("key", "")] = val

                    # Extract status code
                    status_obj = span.get("status") or {}
                    status_code = "UNSET"
                    code_val = status_obj.get("code")
                    if code_val in (2, "STATUS_CODE_ERROR", "ERROR"):
                        status_code = "ERROR"
                    elif code_val in (1, "STATUS_CODE_OK", "OK"):
                        status_code = "OK"

                    if span_attrs.get("http.status_code", 0) >= 500:
                        status_code = "ERROR"

                    if not p_id and root_op == "unknown":
                        root_op = name

                    spans.append(
                        SpanRead(
                            span_id=s_id,
                            trace_id=trace_id,
                            parent_span_id=p_id,
                            name=name,
                            service_name=service_name,
                            start_time_unix_nano=start_nano,
                            end_time_unix_nano=end_nano,
                            duration_ms=round(duration_ms, 2),
                            status_code=status_code,
                            attributes=span_attrs,
                        )
                    )

        if not spans:
            return None

        # Sort spans by start time
        spans.sort(key=lambda s: s.start_time_unix_nano)
        if spans:
            earliest = spans[0].start_time_unix_nano
            latest = max(s.end_time_unix_nano for s in spans)
            total_duration_ms = max(0.0, (latest - earliest) / 1_000_000)
            if root_op == "unknown":
                root_op = spans[0].name

        error_spans = sum(1 for s in spans if s.status_code == "ERROR")

        return TraceSummaryRead(
            trace_id=trace_id,
            service_name=primary_service,
            root_operation=root_op,
            duration_ms=round(total_duration_ms, 2),
            span_count=len(spans),
            error_span_count=error_spans,
            spans=spans,
        )
