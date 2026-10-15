import Link from "next/link";
import { getServices, getIncidents, getMe } from "../lib/api";
import { ServiceCollection } from "../components/service-collection";
export const dynamic = "force-dynamic";
export default async function OperationalOverviewPage() {
  const [services, incidents, session] = await Promise.all([
    getServices(),
    getIncidents(),
    getMe(),
  ]);
  return (
    <main id="main" className="ws-content">
      <div className="ws-page-heading">
        <div>
          <span className="mono ws-eyebrow">
            WORKSPACE / APPLICATION OVERSIGHT
          </span>
          <h1 tabIndex={-1} aria-label="Operational Overview">
            Operational Overview
            <span className="ws-title-count">
              {services.data
                ? String(services.data.length).padStart(2, "0")
                : "—"}
            </span>
          </h1>
          <p>One place to oversee every registered service.</p>
        </div>
        <Link className="ws-button ws-primary" href="/onboarding">
          Register service <span aria-hidden="true">＋</span>
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
          <span className="mono">REGISTERED SERVICES</span>
          <strong>
            {services.data
              ? String(services.data.length).padStart(2, "0")
              : "—"}
          </strong>
          <small>Connection health not reported</small>
        </div>
        <div>
          <span className="mono">PERSISTED INCIDENTS</span>
          <strong>{incidents.data?.total ?? "—"}</strong>
          <small>Authorized incident records</small>
        </div>
        <div className="ws-summary-note">
          <span className="mono">AUTHORIZED DATA / TELEMETRY BOUNDARY</span>
          <p>
            Registration is not a health signal.
            <br />
            Review evidence before taking action.
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
        <ServiceCollection
          services={services.data ?? []}
          incidents={incidents.data}
        />
      )}
    </main>
  );
}
