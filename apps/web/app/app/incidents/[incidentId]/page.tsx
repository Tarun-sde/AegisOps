import Link from "next/link";
import { notFound } from "next/navigation";
import { getIncident, getIncidentEvents } from "../../../lib/api";
import { InvestigationPanel } from "./investigation-panel";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ incidentId: string }>;
}

export default async function IncidentDetailPage({ params }: PageProps) {
  const { incidentId } = await params;
  const {
    data: incident,
    error,
    notFound: is404,
  } = await getIncident(incidentId);

  if (is404) {
    notFound();
  }

  if (error || !incident) {
    return (
      <main id="main">
        <p className="eyebrow">Workspace / Incidents</p>
        <div className="panel" style={{ borderColor: "#8c3b3b" }}>
          <h2>Incident Load Error</h2>
          <p>{error || "Unable to retrieve incident."}</p>
          <Link href="/app/incidents" className="button">
            &larr; Back to Incidents
          </Link>
        </div>
      </main>
    );
  }

  const { data: events } = await getIncidentEvents(incidentId);

  const isCritical = incident.severity.toLowerCase() === "critical";
  const isOpen = incident.status.toLowerCase() === "open";

  return (
    <main id="main">
      <p className="eyebrow">
        <Link
          href="/app/incidents"
          style={{ color: "#b9d391", textDecoration: "none" }}
        >
          &larr; Incidents
        </Link>{" "}
        / {incident.id}
      </p>

      <div className="heading">
        <h1>{incident.title}</h1>
        <div>
          <span
            className="badge"
            style={{
              background: isOpen
                ? isCritical
                  ? "#471818"
                  : "#3d2c14"
                : "#1b2420",
              borderColor: isOpen
                ? isCritical
                  ? "#8a2f2f"
                  : "#805c24"
                : "#3a5746",
              color: isOpen ? (isCritical ? "#f59e9e" : "#edd098") : "#a3d9b8",
              marginRight: "8px",
            }}
          >
            {incident.status.toUpperCase()}
          </span>
          <span
            className="badge"
            style={{
              borderColor: isCritical ? "#8a2f2f" : "#805c24",
              color: isCritical ? "#f59e9e" : "#edd098",
            }}
          >
            {incident.severity.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="grid" style={{ marginTop: "24px" }}>
        <section aria-labelledby="meta-title" className="panel">
          <p className="eyebrow">Operational Scope</p>
          <h2 id="meta-title">Incident Metadata</h2>
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              lineHeight: 2,
              color: "#b7c3c6",
            }}
          >
            <li>
              <strong>Incident ID:</strong> <code>{incident.id}</code>
            </li>
            <li>
              <strong>Fingerprint:</strong> <code>{incident.fingerprint}</code>
            </li>
            <li>
              <strong>Started:</strong>{" "}
              {new Date(incident.started_at).toLocaleString()}
            </li>
            {incident.resolved_at && (
              <li>
                <strong>Resolved:</strong>{" "}
                {new Date(incident.resolved_at).toLocaleString()}
              </li>
            )}
            <li>
              <strong>Source Provider:</strong> Prometheus &bull; Alertmanager
            </li>
          </ul>
        </section>

        <section aria-labelledby="ai-title" className="panel">
          <p className="eyebrow">Phase 2 AI Runtime</p>
          <h2 id="ai-title">Google ADK Runtime</h2>
          <p style={{ color: "#9eaeb2", fontSize: "0.9rem", lineHeight: 1.6 }}>
            Autonomous incident diagnosis using official Google ADK 2.11.0
            runtime, bounded read-only tool gateway, and deterministic evidence
            verification.
          </p>
          <div
            style={{
              marginTop: "12px",
              display: "flex",
              gap: "8px",
              flexWrap: "wrap",
            }}
          >
            <span
              className="badge"
              style={{
                background: "#1c261e",
                borderColor: "#3d5742",
                color: "#9ee0a9",
              }}
            >
              Google ADK 2.11.0
            </span>
            <span
              className="badge"
              style={{
                background: "#172733",
                borderColor: "#2f5c80",
                color: "#8ec4f5",
              }}
            >
              Celery + Redis Worker
            </span>
          </div>
        </section>
      </div>

      <InvestigationPanel incidentId={incident.id} />

      <section
        aria-labelledby="timeline-title"
        className="panel"
        style={{ marginTop: "24px" }}
      >
        <p className="eyebrow">Durable Audit Trail</p>
        <h2 id="timeline-title">Incident Timeline Events</h2>

        {!events || events.length === 0 ? (
          <p>No timeline events recorded for this incident.</p>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              marginTop: "16px",
            }}
          >
            {events.map((ev) => (
              <div
                key={ev.id}
                style={{
                  borderLeft: "2px solid #506047",
                  paddingLeft: "16px",
                  paddingBottom: "8px",
                }}
              >
                <div
                  style={{ display: "flex", gap: "12px", alignItems: "center" }}
                >
                  <span className="badge" style={{ padding: "4px 8px" }}>
                    {ev.event_type}
                  </span>
                  <span style={{ fontSize: "0.85rem", color: "#9eaeb2" }}>
                    {new Date(ev.occurred_at).toLocaleString()} by{" "}
                    <code>{ev.actor}</code>
                  </span>
                </div>
                {ev.payload && Object.keys(ev.payload).length > 0 && (
                  <pre
                    style={{
                      background: "#101416",
                      padding: "8px 12px",
                      borderRadius: "4px",
                      marginTop: "8px",
                      fontSize: "0.8rem",
                      overflowX: "auto",
                    }}
                  >
                    {JSON.stringify(ev.payload, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
