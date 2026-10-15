import Link from "next/link";
import { notFound } from "next/navigation";
import { getIncident, getIncidentEvents, getServices } from "../../../lib/api";
import { StatusBadge } from "../../../components/status-badge";
import { InvestigationPanel } from "./investigation-panel";
import { LifecycleControls } from "./lifecycle-controls";
import { DeploymentContext } from "./deployment-context";
import { TraceViewer } from "./trace-viewer";
export const dynamic = "force-dynamic";
const utc = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ incidentId: string }>;
}) {
  const { incidentId } = await params;
  const {
    data: incident,
    error,
    notFound: missing,
  } = await getIncident(incidentId);
  if (missing) notFound();
  if (error || !incident)
    return (
      <main id="main" className="ws-content an-investigation">
        <h1>Incident Load Error</h1>
        <p role="alert">{error || "Incident unavailable"}</p>
        <Link href="/app/incidents">Back to Incidents</Link>
      </main>
    );
  const [events, services] = await Promise.all([
    getIncidentEvents(incidentId),
    getServices(),
  ]);
  const service = services.data?.find((s) => s.id === incident.service_id);
  const duration = Math.max(
    0,
    Math.floor(
      ((incident.resolved_at
        ? new Date(incident.resolved_at).getTime()
        : Date.now()) -
        new Date(incident.started_at).getTime()) /
        60000,
    ),
  );
  return (
    <main id="main" className="ws-content an-investigation">
      <p className="an-eyebrow">
        <Link href="/app/incidents">← Incidents</Link> / {incident.id}
      </p>
      <div className="an-investigation-header">
        <h1>{incident.title}</h1>
        <div className="citations">
          <StatusBadge value={incident.severity} />
          <StatusBadge value={incident.status} />
        </div>
      </div>
      <div className="an-inline incident-meta">
        <Link href={`/app/services/${incident.service_id}`}>
          {service?.name ?? incident.service_id}
        </Link>
        <span>{incident.environment ?? "Environment not reported"}</span>
        <span>Started {utc(incident.started_at)}</span>
        <span>
          {duration} minutes{" "}
          {incident.resolved_at ? "to resolution" : "at page load"}
        </span>
        <span>
          {incident.correlated_alert_count ?? "Unknown"} correlated alerts
        </span>
      </div>
      <nav className="ws-project-tabs" aria-label="Incident sections">
        <a href="#investigation">Investigation & evidence</a>
        <a href="#timeline">Timeline</a>
        <a href="#deployment-context-title">Deployments</a>
        <a href="#trace-section">Trace viewer</a>
        <Link href="/app/proposals">Action proposals</Link>
      </nav>
      <LifecycleControls
        incidentId={incident.id}
        currentStatus={incident.status}
        currentVersion={incident.version ?? 1}
      />
      <InvestigationPanel
        key={incident.id}
        incidentId={incident.id}
        timeline={
          <section
            id="timeline"
            aria-labelledby="timeline-title"
            className="an-panel an-timeline"
          >
            <p className="an-eyebrow">Durable audit trail</p>
            <h2 id="timeline-title">Incident Timeline Events</h2>
            {events.error ? (
              <p role="alert">{events.error}</p>
            ) : !events.data?.length ? (
              <p>No timeline events recorded.</p>
            ) : (
              events.data.map((ev) => (
                <details key={ev.id} className="timeline-event">
                  <summary>
                    <StatusBadge value={ev.event_type} /> {utc(ev.occurred_at)}{" "}
                    · {ev.actor}
                  </summary>
                  <pre>{JSON.stringify(ev.payload, null, 2)}</pre>
                </details>
              ))
            )}
          </section>
        }
      />
      <section className="an-panel an-actions" aria-labelledby="actions-title">
        <div className="an-section-heading">
          <div>
            <span className="an-eyebrow">04 / Governed next steps</span>
            <h2 id="actions-title">Review before acting.</h2>
          </div>
          <span className="an-demo">Human review required</span>
        </div>
        <div className="an-action-grid">
          <article>
            <span>01 · Diagnose</span>
            <h3>Inspect the evidence</h3>
            <p>
              Review supporting records, contradictions and missing context.
            </p>
            <a className="ws-button" href="#investigation">
              Review investigation ↗
            </a>
          </article>
          <article>
            <span>02 · Review</span>
            <h3>Review exact parameters</h3>
            <p>
              Approval binds to an immutable payload. It does not execute an
              action.
            </p>
            <Link className="ws-button ws-primary" href="/app/proposals">
              Open proposals ↗
            </Link>
          </article>
          <article>
            <span>03 · Verify</span>
            <h3>Observe recovery</h3>
            <p>
              Allowlisted staging execution and recovery verification remain
              separate.
            </p>
            <Link className="ws-button" href="/app/simulation-lab">
              Open Simulation Lab ↗
            </Link>
          </article>
        </div>
      </section>
      <DeploymentContext
        serviceId={incident.service_id}
        incidentEnvironment={incident.environment}
      />
      <div id="trace-section">
        <TraceViewer />
      </div>
      <section className="an-panel">
        <h2>Incident metadata</h2>
        <p>
          Fingerprint: <code>{incident.fingerprint}</code>
        </p>
        <p>
          State version: {incident.version ?? "Not reported"} · Service:{" "}
          <code>{incident.service_id}</code>
        </p>
        {incident.resolved_at && <p>Resolved {utc(incident.resolved_at)}</p>}
      </section>
    </main>
  );
}
