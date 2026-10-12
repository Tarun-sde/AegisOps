import Link from "next/link";
import { getIncidents } from "../lib/api";

export const dynamic = "force-dynamic";

export default async function Workspace() {
  const { data } = await getIncidents();
  const openCount =
    data?.items.filter((i) => i.status.toLowerCase() === "open").length || 0;

  return (
    <main id="main">
      <p className="eyebrow">Workspace / Overview</p>
      <div className="heading">
        <h1>Operational overview</h1>
        <span className="badge">Phase 7 · Simulation & Remediation</span>
      </div>
      <p className="intro">
        Continuous application telemetry, Prometheus alerts, and durable
        incident ingestion.
      </p>

      <div className="grid">
        <section aria-labelledby="services-title" className="panel">
          <p className="eyebrow">Services</p>
          <h2 id="services-title">Connected Services (1)</h2>
          <p>
            <strong>shop-api</strong> · Express microservice instrumented with
            Prometheus RED metrics and structured JSON logs.
          </p>
          <div style={{ marginTop: "12px" }}>
            <span
              className="badge"
              style={{
                background: "#1b2420",
                borderColor: "#3a5746",
                color: "#a3d9b8",
              }}
            >
              HEALTHY · SCRAPED
            </span>
          </div>
        </section>

        <section aria-labelledby="incidents-panel-title" className="panel">
          <p className="eyebrow">Incidents</p>
          <h2 id="incidents-panel-title">
            {openCount > 0
              ? `${openCount} Active Incident(s)`
              : "All Systems Normal"}
          </h2>
          <p>
            {openCount > 0
              ? "Open alerts received from Alertmanager via authenticated webhook."
              : "No firing alerts detected. Real incident records persist across restarts."}
          </p>
          <div style={{ marginTop: "16px" }}>
            <Link
              href="/app/incidents"
              className="button"
              style={{ padding: "8px 16px", fontSize: "0.9rem" }}
            >
              Open Incident Feed ({data?.total || 0}) &rarr;
            </Link>
          </div>
        </section>
      </div>

      <div className="grid" style={{ marginTop: "24px" }}>
        <section aria-labelledby="investigations-title" className="panel">
          <p className="eyebrow">Investigations</p>
          <h2 id="investigations-title">AI Incident Investigation</h2>
          <p>
            Autonomous root-cause analysis with Google ADK queries real metrics,
            logs, traces, and runbooks with strict evidence verification.
          </p>
        </section>

        <section aria-labelledby="evidence-title" className="panel">
          <p className="eyebrow">Observability Pipeline</p>
          <h2 id="evidence-title">Telemetry Stack</h2>
          <p>
            Prometheus scrapes RED metrics every 5s; logs export to Loki via
            OpenTelemetry Collector.
          </p>
        </section>
      </div>
    </main>
  );
}
