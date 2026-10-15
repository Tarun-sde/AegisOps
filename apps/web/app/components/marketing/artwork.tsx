import type { SVGProps } from "react";

export function Mark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 64 64" fill="none" aria-hidden="true" {...props}>
      <path
        d="M24 8H10v48h14M40 8h14v48H40M10 32h12m20 0h12"
        stroke="currentColor"
        strokeWidth="4"
      />
      <rect x="23" y="23" width="18" height="18" rx="3" fill="currentColor" />
      <path d="M32 4v13m0 30v13" stroke="currentColor" strokeWidth="3" />
    </svg>
  );
}

export { SystemDrawing as TopologyDrawing } from "./system-artwork";
import { SystemDrawing as TopologyDrawing } from "./system-artwork";

export function ServiceTopology({
  className = "",
  inspected = false,
}: {
  className?: string;
  inspected?: boolean;
}) {
  return (
    <svg
      className={`service-topology ${className}`}
      viewBox="0 0 1000 620"
      role="img"
      aria-label="Illustrative request topology connecting clients, API gateway, Shop API, auth, PostgreSQL, worker, Redis and payment gateway"
    >
      <TopologyDrawing inspected={inspected} />
    </svg>
  );
}
