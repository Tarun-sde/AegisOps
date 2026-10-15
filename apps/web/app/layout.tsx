import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "./components/app-shell";
import "./globals.css";
import "./workspace.css";
import "./analytics.css";
import "./integration.css";
import "./brand.css";

export const metadata: Metadata = {
  openGraph: {
    title: "AegisOps · Evidence before action",
    description:
      "Application monitoring, scoped AI investigation and human-controlled staging response.",
    images: [
      {
        url: "/aegisops-social.png",
        width: 1200,
        height: 630,
        alt: "AegisOps service node mark and incident evidence workflow",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AegisOps · Evidence before action",
    images: ["/aegisops-social.png"],
  },
  title: "AegisOps · Incident Intelligence & Response",
  description:
    "Evidence-led incident investigation, deterministic monitoring, and human-approved staging response.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
