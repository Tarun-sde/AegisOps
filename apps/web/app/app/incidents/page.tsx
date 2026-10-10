import Link from "next/link";
import { getIncidents } from "../../lib/api";

export const dynamic = "force-dynamic";

export default async function IncidentsPage() {
  const { data, error } = await getIncidents();

  return (
    <main id="main">
      <p className="eyebrow">Workspace / Incidents</p>
      <div className="heading">
        <h1>Incident Feed</h1>
        <span className="badge">Phase 1 · Real Ingestion</span>
      </div>
      <p className="intro">
        Real alert-driven incidents ingested from Alertmanager via authenticated
        webhooks.
      </p>

      {error ? (
        <section
          aria-labelledby="error-title"
          className="panel"
          style={{ borderColor: "#8c3b3b" }}
        >
          <p className="eyebrow" style={{ color: "#e88080" }}>
            Connection Error
          </p>
          <h2 id="error-title">Control Plane API Unavailable</h2>
          <p>
            Could not retrieve incidents from the backend: {error}. Verify that
            the FastAPI service is running and accessible.
          </p>
        </section>
      ) : !data || data.items.length === 0 ? (
        <section aria-labelledby="empty-title" className="panel">
          <p className="eyebrow">Zero Signals</p>
          <h2 id="empty-title">No Incidents Recorded</h2>
          <p>
            No active or resolved incidents found in the database. Trigger a
            controlled fault scenario (such as <code>S01_CHECKOUT_500</code>) to
            generate real telemetry and alert delivery.
          </p>
        </section>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            marginTop: "24px",
          }}
        >
          {data.items.map((inc) => {
            const isCritical = inc.severity.toLowerCase() === "critical";
            const isOpen = inc.status.toLowerCase() === "open";
            return (
              <section
                key={inc.id}
                className="panel"
                style={{
                  borderColor: isOpen
                    ? isCritical
                      ? "#a63a3a"
                      : "#b38234"
                    : "#343e40",
                  marginTop: 0,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    flexWrap: "wrap",
                    gap: "12px",
                  }}
                >
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
                        color: isOpen
                          ? isCritical
                            ? "#f59e9e"
                            : "#edd098"
                          : "#a3d9b8",
                        marginRight: "8px",
                      }}
                    >
                      {inc.status.toUpperCase()}
                    </span>
                    <span
                      className="badge"
                      style={{
                        borderColor: isCritical ? "#8a2f2f" : "#805c24",
                        color: isCritical ? "#f59e9e" : "#edd098",
                      }}
                    >
                      {inc.severity.toUpperCase()}
                    </span>
                  </div>
                  <span className="eyebrow">
                    Fingerprint: {inc.fingerprint}
                  </span>
                </div>

                <h2 style={{ marginTop: "14px", marginBottom: "8px" }}>
                  <Link
                    href={`/app/incidents/${inc.id}`}
                    style={{ color: "#edf1f2", textDecoration: "none" }}
                  >
                    {inc.title}
                  </Link>
                </h2>

                <p style={{ margin: "4px 0", fontSize: "0.95rem" }}>
                  <strong>Started:</strong>{" "}
                  {new Date(inc.started_at).toLocaleString()}
                  {inc.resolved_at && (
                    <>
                      {" "}
                      &bull; <strong>Resolved:</strong>{" "}
                      {new Date(inc.resolved_at).toLocaleString()}
                    </>
                  )}
                </p>

                <div style={{ marginTop: "16px" }}>
                  <Link
                    href={`/app/incidents/${inc.id}`}
                    className="button"
                    style={{ padding: "8px 16px", fontSize: "0.9rem" }}
                  >
                    View Incident Details &rarr;
                  </Link>
                </div>
              </section>
            );
          })}
        </div>
      )}
    </main>
  );
}
