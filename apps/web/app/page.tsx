import Link from "next/link";

export default function Home() {
  return (
    <main id="main">
      <p className="eyebrow">Incident intelligence / Foundation</p>
      <h1>Investigate with evidence.</h1>
      <p className="intro">
        AegisOps is being built to connect operational signals to auditable
        hypotheses and human decisions.
      </p>
      <p>
        Deterministic monitoring, Prometheus alerts, auditable Google ADK tool
        investigations, and sandboxed remediation workflows.
      </p>
      <Link className="button" href="/app">
        Open workspace <span aria-hidden="true">↗</span>
      </Link>
    </main>
  );
}
