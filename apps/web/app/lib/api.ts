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
