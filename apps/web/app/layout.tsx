import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AegisOps · Foundation",
  description:
    "Evidence-led incident investigation. Phase 0 development shell.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header>
          <Link className="brand" href="/">
            AEGIS<span>OPS</span>
          </Link>
          <nav
            aria-label="Main navigation"
            style={{ display: "flex", gap: "20px" }}
          >
            <Link href="/app">Workspace</Link>
            <Link href="/app/incidents">Incidents</Link>
          </nav>
          <span className="badge">Phase 1 · Telemetry &amp; Ingestion</span>
        </header>
        {children}
        <footer>
          Read-only foundation · No production connections or automated actions
        </footer>
      </body>
    </html>
  );
}
