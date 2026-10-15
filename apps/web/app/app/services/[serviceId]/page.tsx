import Link from "next/link";
import { notFound } from "next/navigation";
import { getServices, getIncidents } from "../../../lib/api";
import { ServiceAnalytics } from "../../../components/service-analytics";
import { ServiceDrawing } from "../../../components/project-visuals";
import { DeploymentContext } from "../../incidents/[incidentId]/deployment-context";
export const dynamic = "force-dynamic";
export default async function ServicePage({
  params,
}: {
  params: Promise<{ serviceId: string }>;
}) {
  const { serviceId } = await params;
  const { data, error } = await getServices();
  if (error)
    return (
      <main id="main" className="ws-content">
        <h1>Service unavailable</h1>
        <p role="alert">{error}</p>
        <Link href="/app">Back to applications</Link>
      </main>
    );
  const service = data?.find((s) => s.id === serviceId);
  if (!service) notFound();
  const incidents = await getIncidents();
  return (
    <main id="main" className="ws-content">
      <div className="ws-project-context">
        <Link href="/app">← All applications</Link>
        <span className="mono">{service.id}</span>
      </div>
      <div id="overview" className="ws-page-heading ws-detail-heading">
        <div>
          <span className="mono ws-eyebrow">
            REGISTERED APPLICATION / {service.environment}
          </span>
          <h1 tabIndex={-1}>{service.name}</h1>
          <p>{service.description || "No description provided."}</p>
          <span className="ws-tech mono">Service / {service.id}</span>
        </div>
      </div>
      <div className="ws-project-badges">
        <span className="ws-tag mono">{service.environment}</span>
        <span>Registration: {service.status}</span>
        <span>Health unknown · Connection not reported</span>
      </div>
      <nav className="ws-project-tabs" aria-label="Application sections">
        <a href="#overview">Overview 01</a>
        <a href="#analytics">Analytics 02</a>
        <a href="#services">Services 01</a>
        <a href="#incidents">Incidents & Intelligence</a>
        <a href="#activity">Activity</a>
      </nav>
      <ServiceAnalytics
        service={service}
        incidents={incidents.data}
        error={incidents.error}
      />
      <section className="ws-detail-panel">
        <div className="ws-panel-heading">
          <h2>Service schematic</h2>
          <span className="mono">REGISTERED INVENTORY</span>
        </div>
        <ServiceDrawing
          project={{
            name: service.name,
            services: [
              { id: service.id, name: service.name, health: "unknown" },
            ],
          }}
        />
      </section>
      <div id="activity" />
      <DeploymentContext
        serviceId={service.id}
        incidentEnvironment={service.environment}
      />
      <section className="panel">
        <h2>Investigate an incident</h2>
        <p>
          The incident register contains authorized organization records with
          service IDs. Select an incident to inspect its timeline, trace and
          persisted investigations.
        </p>
        <Link className="button" href="/app/incidents">
          Open incident register ↗
        </Link>
      </section>
    </main>
  );
}
