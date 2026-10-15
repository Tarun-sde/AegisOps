import Link from "next/link";
import { getServices, getIncidents, getMe } from "../../lib/api";
import { ServiceCollection } from "../../components/service-collection";

export const dynamic = "force-dynamic";

export default async function ServicesPage() {
  const [services, incidents, session] = await Promise.all([
    getServices(),
    getIncidents(),
    getMe(),
  ]);

  const serviceCount = services.data?.length ?? 0;

  return (
    <main id="main" className="ws-content">
      <div className="ws-page-heading">
        <div>
          <span className="mono ws-eyebrow">WORKSPACE / SERVICES CATALOG</span>
          <h1 tabIndex={-1}>
            Monitored Services{" "}
            <span className="ws-title-count">
              {String(serviceCount).padStart(2, "0")}
            </span>
          </h1>
          <p>
            Complete inventory of registered services with telemetry
            integration.
          </p>
        </div>
        <Link className="ws-button ws-primary" href="/onboarding">
          Register service +
        </Link>
      </div>

      <div className="ws-summary">
        <div>
          <span className="mono">ORGANIZATION</span>
          <strong>
            {session.data?.active_organization?.name ?? "Session required"}
          </strong>
          <small>{session.data?.role ?? "No active membership"}</small>
        </div>
        <div>
          <span className="mono">REGISTERED SERVICES</span>
          <strong>{serviceCount}</strong>
          <small>Active endpoints</small>
        </div>
        <div>
          <span className="mono">PERSISTED INCIDENTS</span>
          <strong>{incidents.data?.total ?? "—"}</strong>
          <small>Incident records</small>
        </div>
        <div className="ws-summary-note">
          <span className="mono">TELEMETRY BOUNDARY</span>
          <p>
            Service registration defines telemetry scoping. Absence of open
            incidents does not certify runtime health.
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
