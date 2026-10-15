import Link from "next/link";
import { getServices, getMe } from "../lib/api";
import { ServiceCollection } from "../components/service-collection";
export const dynamic = "force-dynamic";
export default async function OperationalOverviewPage() {
  const [services, session] = await Promise.all([getServices(), getMe()]);
  return (
    <main id="main" className="ws-content">
      <div className="ws-page-heading">
        <div>
          <span className="mono ws-eyebrow">
            WORKSPACE / APPLICATION OVERSIGHT
          </span>
          <h1 tabIndex={-1} aria-label="Your Applications">
            Your Applications
            <span className="ws-title-count">
              {services.data
                ? String(services.data.length).padStart(2, "0")
                : "—"}
            </span>
          </h1>
          <p>
            Monitor your connected services, investigate incidents and review
            operational activity from one workspace.
          </p>
        </div>
        <Link className="ws-button ws-primary" href="/onboarding">
          Connect Application <span aria-hidden="true">＋</span>
        </Link>
      </div>
      <div className="ws-summary">
        <div>
          <span className="mono">WORKSPACE</span>
          <strong>
            {session.data?.active_organization?.name ?? "Session required"}
          </strong>
          <small>{session.data?.role ?? "No active membership"}</small>
        </div>
        <div>
          <span className="mono">APPLICATIONS</span>
          <strong>
            {services.data
              ? String(services.data.length).padStart(2, "0")
              : "—"}
          </strong>
          <small>Connection health not reported</small>
        </div>
        <div>
          <span className="mono">ACTIVE INCIDENTS</span>
          <strong>
            {services.data?.every((s) => s.active_incident_count != null)
              ? services.data.reduce((n, s) => n + s.active_incident_count!, 0)
              : "—"}
          </strong>
          <small>Open, acknowledged, mitigating or reopened</small>
        </div>
        <div className="ws-summary-note">
          <span className="mono">AUTHORIZED DATA / TELEMETRY BOUNDARY</span>
          <p>
            {services.data?.filter((s) => (s.active_incident_count ?? 0) > 0)
              .length ?? "—"}{" "}
            applications with active incidents.
            <br />
            Monitoring health remains unknown.
          </p>
        </div>
      </div>
      {services.error ? (
        <section className="panel" role="alert">
          <h2>Services unavailable</h2>
          <p>{services.error}</p>
          <Link href="/login">Sign in to access your organization</Link>
        </section>
      ) : (
        <ServiceCollection services={services.data ?? []} />
      )}
    </main>
  );
}
