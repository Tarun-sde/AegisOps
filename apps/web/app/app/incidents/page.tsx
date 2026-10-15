import Link from "next/link";
import { getIncidents, getServices } from "../../lib/api";
import { StatusBadge } from "../../components/status-badge";
export const dynamic = "force-dynamic";
export default async function IncidentsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; status?: string; severity?: string }>;
}) {
  const q = await searchParams;
  const page = Math.max(1, Math.floor(Number(q.page) || 1));
  const [result, services] = await Promise.all([
    getIncidents(q.status, page, q.severity),
    getServices(),
  ]);
  const { data, error } = result;
  const pageLink = (p: number) =>
    `/app/incidents?${new URLSearchParams({ page: String(p), status: q.status ?? "", severity: q.severity ?? "" })}`;
  return (
    <main id="main" className="ws-content">
      <p className="eyebrow">Workspace / Incident register</p>
      <div className="heading">
        <h1>Incident Feed</h1>
        <span className="badge badge-info">Persisted records</span>
      </div>
      <p className="intro">
        Follow the signal from an alert to a hypothesis and its supporting
        evidence.
      </p>
      <form className="collection-controls" action="/app/incidents">
        <label>
          Lifecycle
          <select name="status" defaultValue={q.status ?? ""}>
            <option value="">All states</option>
            {[
              "open",
              "acknowledged",
              "mitigating",
              "resolved",
              "closed",
              "reopened",
            ].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Severity
          <select name="severity" defaultValue={q.severity ?? ""}>
            <option value="">All severities</option>
            {["critical", "warning", "info"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <button type="submit">Apply filters</button>
        <Link href="/app/incidents">Reset</Link>
      </form>
      {error ? (
        <section className="panel" role="alert">
          <h2>Incidents unavailable</h2>
          <p>{error}</p>
          <Link href="/login">Sign in</Link>
        </section>
      ) : !data?.items.length ? (
        <section className="panel">
          <h2>No Incidents Recorded</h2>
          <p>
            No records match this page and filter. This is not a measurement of
            service health.
          </p>
        </section>
      ) : (
        <>
          <p>
            {data.total} matching records · Page {data.page}
          </p>
          <div className="incident-register">
            {data.items.map((inc) => (
              <article className="incident-row" key={inc.id}>
                <div className="incident-meta">
                  <StatusBadge value={inc.status} />
                  <StatusBadge value={inc.severity} />
                  <span>
                    {services.data?.find((s) => s.id === inc.service_id)
                      ?.name ?? inc.service_id}
                  </span>
                  <span>{inc.environment ?? "Environment not reported"}</span>
                </div>
                <h2>
                  <Link href={`/app/incidents/${inc.id}`}>{inc.title}</Link>
                </h2>
                <div className="incident-meta">
                  <time dateTime={inc.started_at}>
                    {new Date(inc.started_at)
                      .toISOString()
                      .replace("T", " ")
                      .slice(0, 19)}{" "}
                    UTC
                  </time>
                  <span>
                    {inc.correlated_alert_count ?? "Unknown"} correlated alerts
                  </span>
                </div>
                <small>
                  Incident <code>{inc.id}</code>
                </small>
              </article>
            ))}
          </div>
        </>
      )}
      {data && (
        <nav aria-label="Incident pages" className="pagination">
          {page > 1 && <Link href={pageLink(page - 1)}>Previous page</Link>}
          <span>
            Page {page} · {data.total} records
          </span>
          {page * data.size < data.total && (
            <Link href={pageLink(page + 1)}>Next page</Link>
          )}
        </nav>
      )}
    </main>
  );
}
