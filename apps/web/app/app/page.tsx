export default function Workspace() {
  return (
    <main id="main">
      <p className="eyebrow">Workspace / Overview</p>
      <div className="heading">
        <h1>Operational overview</h1>
        <span className="badge">Setup in progress</span>
      </div>
      <p className="intro">
        A place for signals, hypotheses, and the evidence behind them.
      </p>
      <section aria-labelledby="services-title" className="panel">
        <p className="eyebrow">Services</p>
        <h2 id="services-title">No services connected</h2>
        <p>
          Telemetry integration begins after the foundation exit gates pass.
          Service health is currently unknown.
        </p>
      </section>
      <div className="grid">
        <section aria-labelledby="investigations-title" className="panel">
          <p className="eyebrow">Investigations</p>
          <h2 id="investigations-title">No investigations yet</h2>
          <p>
            The Phase 0 ADK experiment uses explicitly synthetic log fixtures.
            It does not observe a real incident.
          </p>
        </section>
        <section aria-labelledby="evidence-title" className="panel">
          <p className="eyebrow">Evidence &amp; decisions</p>
          <h2 id="evidence-title">Every claim needs a source</h2>
          <p>
            Future reports will link supporting and contradicting evidence. An
            inconclusive result is a valid outcome.
          </p>
        </section>
      </div>
    </main>
  );
}
