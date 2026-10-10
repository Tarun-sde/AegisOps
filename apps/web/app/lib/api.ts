export interface Incident {
  id: string;
  organization_id: string;
  service_id: string;
  title: string;
  severity: string;
  status: string;
  fingerprint: string;
  started_at: string;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentEvent {
  id: string;
  incident_id: string;
  event_type: string;
  actor: string;
  occurred_at: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  page: number;
  size: number;
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "http://127.0.0.1:8000";

export async function getIncidents(
  statusFilter?: string,
): Promise<{ data: IncidentListResponse | null; error: string | null }> {
  try {
    const url = new URL(`${API_BASE}/api/v1/incidents`);
    if (statusFilter) {
      url.searchParams.set("status", statusFilter);
    }
    const res = await fetch(url.toString(), {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as IncidentListResponse;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}

export async function getIncident(incidentId: string): Promise<{
  data: Incident | null;
  error: string | null;
  notFound?: boolean;
}> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (res.status === 404) {
      return { data: null, error: "Incident not found", notFound: true };
    }
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as Incident;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}

export async function getIncidentEvents(
  incidentId: string,
): Promise<{ data: IncidentEvent[] | null; error: string | null }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/incidents/${incidentId}/events`,
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as IncidentEvent[];
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}

export interface Hypothesis {
  id: string;
  run_id: string;
  cause: string;
  confidence: "low" | "medium" | "high";
  supporting_evidence: { evidence_id: string; supports: string }[];
  contradicting_evidence_ids: string[];
  next_check: string | null;
  created_at: string;
}

export interface EvidenceItem {
  id: string;
  evidence_id: string;
  run_id: string;
  organization_id: string;
  service_id: string;
  source: string;
  observed_at: string;
  locator: string;
  redacted_snippet: string;
  content_hash: string;
  query_metadata: Record<string, unknown>;
  created_at: string;
}

export interface ToolExecution {
  id: string;
  run_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: string;
  latency_ms: number;
  error_category: string | null;
  created_at: string;
}

export interface InvestigationRun {
  id: string;
  incident_id: string;
  organization_id: string;
  service_id: string;
  status:
    | "QUEUED"
    | "COLLECTING_CONTEXT"
    | "INVESTIGATING"
    | "VALIDATING"
    | "COMPLETE"
    | "INCONCLUSIVE"
    | "FAILED"
    | "CANCELLED";
  model: string;
  prompt_version: string;
  summary: string | null;
  missing_evidence: string[];
  limitations: string[];
  suggested_actions: string[];
  tool_call_count: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestigationRunDetail extends InvestigationRun {
  hypotheses: Hypothesis[];
  evidence_items: EvidenceItem[];
}

export async function listIncidentInvestigations(
  incidentId: string,
): Promise<{ data: InvestigationRun[] | null; error: string | null }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/incidents/${incidentId}/investigations`,
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as InvestigationRun[];
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}

export async function startInvestigation(
  incidentId: string,
): Promise<{ data: InvestigationRun | null; error: string | null }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/incidents/${incidentId}/investigations`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({}),
      },
    );
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as InvestigationRun;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}

export async function getInvestigation(
  investigationId: string,
): Promise<{ data: InvestigationRunDetail | null; error: string | null }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/investigations/${investigationId}`,
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as InvestigationRunDetail;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}

export async function getInvestigationEvents(
  investigationId: string,
): Promise<{ data: ToolExecution[] | null; error: string | null }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/investigations/${investigationId}/events`,
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as ToolExecution[];
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}

export async function cancelInvestigation(
  investigationId: string,
): Promise<{ data: InvestigationRun | null; error: string | null }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/investigations/${investigationId}/cancel`,
      {
        method: "POST",
        headers: { Accept: "application/json" },
      },
    );
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as InvestigationRun;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to control plane API",
    };
  }
}
