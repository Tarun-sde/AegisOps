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
          <nav aria-label="Main navigation">
            <Link href="/app">Workspace</Link>
            <Link href="/app/incidents">Incidents</Link>
            <Link href="/app/runbooks">Runbooks</Link>
            <Link href="/app/proposals">Proposals</Link>
            <Link href="/onboarding">Onboarding</Link>
            <Link href="/login">Sign in</Link>
          </nav>
          <span className="badge">Phase 6 · Outbox & Approvals</span>
        </header>
        {children}
        <footer>
          Read-only foundation · No production connections or automated actions
        </footer>
      </body>
    </html>
  );
}
