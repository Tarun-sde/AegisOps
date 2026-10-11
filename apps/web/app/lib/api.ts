export interface Incident {
  id: string;
  organization_id: string;
  service_id: string;
  title: string;
  severity: string;
  status: string;
  version?: number;
  environment?: string;
  correlated_alert_count?: number;
  fingerprint: string;
  started_at: string;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeploymentRecord {
  deployment_id: string;
  repository: string;
  commit_sha: string;
  version?: string | null;
  environment: string;
  deployed_at: string;
  source: string;
  is_deployment: boolean;
  message?: string | null;
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
  unverified_assumptions?: string[];
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
  execution_mode?: "offline" | "live";
  provider?: string;
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
        credentials: "include",
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

// --- Phase 3: Auth, RBAC, Services, and Distributed Tracing ---

export interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  active_organization: Organization | null;
  role: string | null;
  organizations: Organization[];
  csrf_token?: string;
}

export interface Service {
  id: string;
  organization_id: string;
  name: string;
  environment: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceVerifyResponse {
  success: boolean;
  message: string;
  status_code?: number;
  latency_ms?: number;
}

export interface Span {
  span_id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  service_name: string;
  start_time_unix_nano: number;
  end_time_unix_nano: number;
  duration_ms: number;
  status_code: string;
  attributes: Record<string, unknown>;
}

export interface TraceSummary {
  trace_id: string;
  service_name: string;
  root_operation: string;
  duration_ms: number;
  span_count: number;
  error_span_count: number;
  spans: Span[];
}

function getCsrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.match(/(?:^|;\s*)aegisops_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : undefined;
}

export async function loginUser(
  email: string,
  password: string,
): Promise<{ data: AuthResponse | null; error: string | null }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ email, password }),
      credentials: "include",
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      return {
        data: null,
        error: errJson.detail || `Login failed (${res.status})`,
      };
    }
    const data = (await res.json()) as AuthResponse;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to auth service",
    };
  }
}

export async function registerUser(
  email: string,
  password: string,
  name?: string,
): Promise<{ data: AuthResponse | null; error: string | null }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ email, password, name }),
      credentials: "include",
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      return {
        data: null,
        error: errJson.detail || `Registration failed (${res.status})`,
      };
    }
    const data = (await res.json()) as AuthResponse;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to connect to auth service",
    };
  }
}

export async function logoutUser(): Promise<{ error: string | null }> {
  try {
    const csrf = getCsrfToken();
    const headers: Record<string, string> = { Accept: "application/json" };
    if (csrf) headers["x-csrf-token"] = csrf;
    await fetch(`${API_BASE}/api/v1/auth/logout`, {
      method: "POST",
      headers,
      credentials: "include",
    });
    return { error: null };
  } catch (err) {
    return {
      error: err instanceof Error ? err.message : "Failed to logout",
    };
  }
}

export async function getMe(): Promise<{
  data: AuthResponse | null;
  error: string | null;
}> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/me`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      credentials: "include",
    });
    if (!res.ok) {
      return { data: null, error: `Authentication required (${res.status})` };
    }
    const data = (await res.json()) as AuthResponse;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error ? err.message : "Failed to fetch user context",
    };
  }
}

export async function getServices(): Promise<{
  data: Service[] | null;
  error: string | null;
}> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/services`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      credentials: "include",
    });
    if (!res.ok) {
      return { data: null, error: `Failed to load services (${res.status})` };
    }
    const data = (await res.json()) as Service[];
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Failed to fetch services",
    };
  }
}

export async function createService(payload: {
  name: string;
  environment?: string;
  description?: string;
}): Promise<{ data: Service | null; error: string | null }> {
  try {
    const csrf = getCsrfToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (csrf) headers["x-csrf-token"] = csrf;

    const res = await fetch(`${API_BASE}/api/v1/services`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      credentials: "include",
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      return {
        data: null,
        error: errJson.detail || `Failed to create service (${res.status})`,
      };
    }
    const data = (await res.json()) as Service;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Failed to create service",
    };
  }
}

export async function verifyServiceConnection(
  serviceId: string,
  url: string,
): Promise<{ data: ServiceVerifyResponse | null; error: string | null }> {
  try {
    const csrf = getCsrfToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (csrf) headers["x-csrf-token"] = csrf;

    const res = await fetch(
      `${API_BASE}/api/v1/services/${serviceId}/verify-connection`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ url }),
        credentials: "include",
      },
    );
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      return {
        data: null,
        error:
          errJson.detail || `Connector verification rejected (${res.status})`,
      };
    }
    const data = (await res.json()) as ServiceVerifyResponse;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error: err instanceof Error ? err.message : "Failed to connect",
    };
  }
}

export async function getTrace(
  traceId: string,
): Promise<{ data: TraceSummary | null; error: string | null }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/traces/${traceId}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      credentials: "include",
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      return {
        data: null,
        error: errJson.detail || `Trace not found (${res.status})`,
      };
    }
    const data = (await res.json()) as TraceSummary;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error ? err.message : "Failed to fetch trace from Tempo",
    };
  }
}

export async function getServiceDeployments(
  serviceId: string,
  limit: number = 5,
): Promise<{ data: DeploymentRecord[] | null; error: string | null }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/services/${serviceId}/deployments?limit=${limit}`,
      {
        cache: "no-store",
        headers: { Accept: "application/json" },
        credentials: "include",
      },
    );
    if (!res.ok) {
      return {
        data: null,
        error: `API error ${res.status}: ${res.statusText}`,
      };
    }
    const data = (await res.json()) as DeploymentRecord[];
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

export async function updateIncidentStatus(
  incidentId: string,
  status: string,
  expectedVersion?: number,
  reason?: string,
): Promise<{ data: Incident | null; error: string | null }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/incidents/${incidentId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      credentials: "include",
      body: JSON.stringify({
        status,
        expected_version: expectedVersion,
        reason,
      }),
    });
    if (!res.ok) {
      const errJson = await res.json().catch(() => null);
      const detail =
        errJson?.detail || `API error ${res.status}: ${res.statusText}`;
      return { data: null, error: detail };
    }
    const data = (await res.json()) as Incident;
    return { data, error: null };
  } catch (err) {
    return {
      data: null,
      error:
        err instanceof Error
          ? err.message
          : "Failed to update incident status",
    };
  }
}
