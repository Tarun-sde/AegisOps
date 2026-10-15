import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getServices,
  getIncidents,
  getIncident,
  getIncidentEvents,
  listIncidentInvestigations,
  getInvestigation,
} from "../../../lib/api";
import { ServiceAnalytics } from "../../../components/service-analytics";
import { ApplicationActions } from "../../../components/application-actions";
import { StatusBadge } from "../../../components/status-badge";
import { EvidenceExplorer } from "../../../components/evidence-explorer";
import { InvestigationPanel } from "../../incidents/[incidentId]/investigation-panel";
import { DeploymentContext } from "../../incidents/[incidentId]/deployment-context";
export const dynamic = "force-dynamic";
const views = [
  "overview",
  "analytics",
  "incidents",
  "investigations",
  "evidence",
  "activity",
];
const utc = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
export default async function ServicePage({
  params,
  searchParams,
}: {
  params: Promise<{ serviceId: string }>;
  searchParams: Promise<{
    view?: string;
    page?: string;
    incident?: string;
    run?: string;
  }>;
}) {
  const { serviceId } = await params;
  const query = await searchParams;
  const view = views.includes(query.view ?? "") ? query.view! : "overview";
  const page = /^\d+$/.test(query.page ?? "")
    ? Math.max(1, Math.min(Number(query.page), 1000000))
    : 1;
  const { data, error } = await getServices();
  if (error)
    return (
      <main id="main" className="ws-content">
        <h1>Application unavailable</h1>
        <p role="alert">{error}</p>
        <Link href="/app">Back to applications</Link>
      </main>
    );
  const service = data?.find((s) => s.id === serviceId);
  if (!service) notFound();
  const base = `/app/services/${service.id}`;
  const href = (tab: string, extra: Record<string, string> = {}) =>
    `${base}?${new URLSearchParams({ view: tab, ...extra })}`;
  const incidents = await getIncidents(undefined, page, undefined, service.id);
  let selected = incidents.data?.items[0];
  if (query.incident) {
    const result = await getIncident(query.incident);
    if (
      !result.data ||
      result.data.service_id !== service.id ||
      result.data.organization_id !== service.organization_id
    )
      notFound();
    selected = result.data;
  }
  const contextual = ["investigations", "evidence", "activity"].includes(view);
  const runs =
    selected && ["overview", "evidence"].includes(view)
      ? await listIncidentInvestigations(selected.id)
      : null;
  const authorizedRuns =
    runs?.data?.filter(
      (r) =>
        r.service_id === service.id &&
        r.organization_id === service.organization_id &&
        r.incident_id === selected?.id,
    ) ?? [];
  const runId = query.run ?? authorizedRuns[0]?.id;
  if (
    view === "evidence" &&
    query.run &&
    !authorizedRuns.some((r) => r.id === query.run)
  )
    notFound();
  const detail =
    view === "evidence" && runId ? await getInvestigation(runId) : null;
  const run = detail?.data;
  if (
    run &&
    (run.service_id !== service.id ||
      run.organization_id !== service.organization_id ||
      run.incident_id !== selected?.id)
  )
    notFound();
  const events =
    selected && view === "activity"
      ? await getIncidentEvents(selected.id)
      : null;
  const rows = incidents.data?.items ?? [];
  const paging =
    incidents.data && incidents.data.total > incidents.data.size ? (
      <nav
        className="application-pagination"
        aria-label="Application incident pages"
      >
        {page > 1 && (
          <Link
            className="ws-button"
            href={href(view, { page: String(page - 1) })}
          >
            ← Previous
          </Link>
        )}
        <span>
          Page {page} · {incidents.data.total} incidents
        </span>
        {page * incidents.data.size < incidents.data.total && (
          <Link
            className="ws-button"
            href={href(view, { page: String(page + 1) })}
          >
            Next →
          </Link>
        )}
      </nav>
    ) : null;
  const incidentTable = (limit?: number) => (
    <>
      {incidents.error ? (
        <p role="alert">Incident records unavailable: {incidents.error}</p>
      ) : !rows.length ? (
        <div className="application-empty">
          <h3>No incidents recorded.</h3>
          <p>
            No records for this application on this page. Monitoring health
            remains unknown.
          </p>
        </div>
      ) : (
        <div
          className="an-table-scroll"
          role="region"
          aria-label="Application incidents"
          // Scrollable table region must support keyboard panning.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
        >
          <table className="an-service-table">
            <thead>
              <tr>
                <th>Incident</th>
                <th>Status</th>
                <th>Started / updated</th>
                <th>Application</th>
                <th>Investigation</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((i) => (
                <tr key={i.id}>
                  <th>
                    <StatusBadge value={i.severity} />
                    <Link href={`/app/incidents/${i.id}`}>{i.title} ↗</Link>
                  </th>
                  <td>
                    <StatusBadge value={i.status} />
                  </td>
                  <td>
                    <time dateTime={i.started_at}>{utc(i.started_at)}</time>
                    <small>Updated {utc(i.updated_at)}</small>
                  </td>
                  <td>{service.name}</td>
                  <td>
                    <Link href={href("investigations", { incident: i.id })}>
                      Review runs →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
  return (
    <main id="main" className="ws-content application-detail">
      <div className="ws-project-context">
        <Link href="/app">← All applications</Link>
        <span className="mono">{service.id}</span>
      </div>
      <div className="ws-page-heading ws-detail-heading">
        <div>
          <span className="mono ws-eyebrow">
            APPLICATION / {service.environment}
          </span>
          <h1 tabIndex={-1}>{service.name}</h1>
          <p>{service.description || "No description provided."}</p>
        </div>
        <ApplicationActions service={service} />
      </div>
      <div className="ws-project-badges">
        <span className="ws-tag">{service.environment}</span>
        <span className="ws-health ws-health-unknown">
          <i aria-hidden="true" />
          Monitoring unknown
        </span>
        <span>Updated {utc(service.updated_at)}</span>
        {service.current_version && (
          <span>Version {service.current_version}</span>
        )}
      </div>
      <nav className="ws-project-tabs" aria-label="Application sections">
        {views.map((v) => (
          <Link
            key={v}
            href={href(v)}
            aria-current={view === v ? "page" : undefined}
          >
            {v[0].toUpperCase() + v.slice(1)}
          </Link>
        ))}
      </nav>
      {view === "overview" && (service.active_incident_count ?? 0) > 0 && (
        <div className="an-alert">
          <StatusBadge value="open" />
          <div>
            <strong>
              {service.active_incident_count} active{" "}
              {service.active_incident_count === 1
                ? "incident needs"
                : "incidents need"}{" "}
              attention
            </strong>
            <p>
              Review the incident context and supporting evidence before taking
              action.
            </p>
          </div>
          <Link className="ws-button" href={href("incidents")}>
            Review incidents →
          </Link>
        </div>
      )}
      {["overview", "analytics"].includes(view) && (
        <ServiceAnalytics service={service} />
      )}
      {["overview", "incidents"].includes(view) && (
        <section className="an-panel application-section">
          <div className="an-section-heading">
            <div>
              <span className="an-eyebrow">Service-scoped records</span>
              <h2>{view === "overview" ? "Recent incidents" : "Incidents"}</h2>
            </div>
            {view === "overview" && (
              <Link className="ws-button" href={href("incidents")}>
                All incidents →
              </Link>
            )}
          </div>
          {incidentTable(view === "overview" ? 3 : undefined)}
          {view === "incidents" && paging}
        </section>
      )}
      {contextual && (
        <section className="application-context-picker">
          <div>
            <span className="an-eyebrow">Incident context</span>
            <h2>{view[0].toUpperCase() + view.slice(1)}</h2>
            <p>
              Select an incident to review its{" "}
              {view === "activity" ? "persisted events" : view}. Only this
              application’s incidents are listed.
            </p>
          </div>
          {incidents.error && <p role="alert">{incidents.error}</p>}
          <nav
            aria-label="Select incident"
            className="application-incident-picker"
          >
            {rows.map((i) => (
              <Link
                key={i.id}
                className="ws-button"
                href={href(view, { incident: i.id, page: String(page) })}
                aria-current={selected?.id === i.id ? "page" : undefined}
              >
                {i.title}
              </Link>
            ))}
          </nav>
          {paging}
          {!selected && (
            <p>
              No incident context available. Evidence and investigations appear
              after an incident is recorded.
            </p>
          )}
          {selected && (
            <p>
              Selected: <strong>{selected.title}</strong> ·{" "}
              <Link href={`/app/incidents/${selected.id}`}>
                Open full incident →
              </Link>
            </p>
          )}
        </section>
      )}
      {view === "investigations" && selected && (
        <InvestigationPanel key={selected.id} incidentId={selected.id} />
      )}
      {view === "evidence" && selected && (
        <section className="application-section">
          {runs?.error || detail?.error ? (
            <p role="alert">{runs?.error || detail?.error}</p>
          ) : (
            <>
              <nav
                className="application-incident-picker"
                aria-label="Select evidence run"
              >
                {authorizedRuns.map((r) => (
                  <Link
                    key={r.id}
                    className="ws-button"
                    href={href("evidence", {
                      incident: selected.id,
                      run: r.id,
                    })}
                    aria-current={run?.id === r.id ? "page" : undefined}
                  >
                    {r.status} · {utc(r.created_at)}
                  </Link>
                ))}
              </nav>
              {run ? (
                <>
                  <div className="an-alert">
                    <StatusBadge value={run.status} />
                    <div>
                      <strong>
                        {run.execution_mode === "offline"
                          ? "Offline investigation · synthetic provider responses"
                          : "Persisted investigation"}
                      </strong>
                      <p>{run.summary || "No summary recorded."}</p>
                      <p>
                        Missing evidence:{" "}
                        {run.missing_evidence.join("; ") || "None reported"}
                      </p>
                      <p>
                        Limitations:{" "}
                        {run.limitations.join("; ") || "None reported"}
                      </p>
                    </div>
                  </div>
                  <EvidenceExplorer key={run.id} run={run} />
                </>
              ) : (
                <div className="application-empty">
                  <h3>No persisted evidence yet.</h3>
                  <p>Review or start an investigation for this incident.</p>
                  <Link
                    className="ws-button"
                    href={href("investigations", { incident: selected.id })}
                  >
                    Open investigations →
                  </Link>
                </div>
              )}
            </>
          )}
        </section>
      )}
      {view === "overview" && (
        <div className="application-overview-bottom">
          <section className="an-panel">
            <div className="an-section-heading">
              <div>
                <span className="an-eyebrow">
                  {selected
                    ? "Latest incident context"
                    : "Investigation history"}
                </span>
                <h2>Recent investigations</h2>
              </div>
            </div>
            {runs?.error ? (
              <p role="alert">{runs.error}</p>
            ) : authorizedRuns.length ? (
              authorizedRuns.slice(0, 3).map((r) => (
                <article className="application-run" key={r.id}>
                  <StatusBadge value={r.status} />
                  <p>{r.summary || "No summary recorded."}</p>
                  <small>
                    {utc(r.created_at)} ·{" "}
                    {r.execution_mode ?? "Mode not reported"}
                  </small>
                  <Link
                    href={href("evidence", {
                      incident: r.incident_id,
                      run: r.id,
                    })}
                  >
                    Review evidence →
                  </Link>
                </article>
              ))
            ) : (
              <p>No investigation recorded for the latest incident.</p>
            )}
            <Link className="ws-button" href={href("investigations")}>
              Open investigations →
            </Link>
          </section>
          <section className="an-panel">
            <span className="an-eyebrow">Persisted application history</span>
            <h2>Recent activity</h2>
            <ol className="ws-activity-list">
              <li>
                <span className="ws-event-mark" aria-hidden="true" />
                <div>
                  <p>Application registered</p>
                  <time dateTime={service.created_at}>
                    {utc(service.created_at)}
                  </time>
                </div>
              </li>
              {service.last_incident_at && (
                <li>
                  <span
                    className="ws-event-mark ws-event-incident"
                    aria-hidden="true"
                  />
                  <div>
                    <p>Latest incident record updated</p>
                    <time dateTime={service.last_incident_at}>
                      {utc(service.last_incident_at)}
                    </time>
                  </div>
                </li>
              )}
            </ol>
            <Link className="ws-button" href={href("activity")}>
              Explore activity →
            </Link>
          </section>
        </div>
      )}
      {view === "activity" && (
        <section className="an-panel application-section">
          <h2>Operational history</h2>
          <p>
            Application registration and events for the selected incident. Times
            are shown in UTC.
          </p>
          {events?.error && <p role="alert">{events.error}</p>}
          <ol className="ws-activity-list">
            {events?.data
              ?.filter((e) => e.incident_id === selected?.id)
              .map((e) => (
                <li key={e.id}>
                  <span className="ws-event-mark" aria-hidden="true" />
                  <div>
                    <span className="mono">
                      {e.event_type.replaceAll("_", " ")}
                    </span>
                    <p>Actor: {e.actor}</p>
                    <time dateTime={e.occurred_at}>{utc(e.occurred_at)}</time>
                  </div>
                </li>
              ))}
            <li>
              <span className="ws-event-mark" aria-hidden="true" />
              <div>
                <p>Application registered</p>
                <time dateTime={service.created_at}>
                  {utc(service.created_at)}
                </time>
              </div>
            </li>
          </ol>
          <DeploymentContext
            serviceId={service.id}
            incidentEnvironment={service.environment}
          />
        </section>
      )}
    </main>
  );
}
