import { Mark } from "./marketing/artwork";
export type Health =
  | "healthy"
  | "reachable"
  | "configured"
  | "degraded"
  | "critical"
  | "down"
  | "stale"
  | "unavailable"
  | "unknown";
type Project = {
  name: string;
  services: { id: string; name: string; health: Health }[];
};
export function AegisMark() {
  return <Mark width="28" height="30" />;
}
export function HealthStatus({ health }: { health: string }) {
  const norm = health.toLowerCase();
  const badgeClass =
    norm === "reachable" || norm === "healthy"
      ? "healthy"
      : norm === "degraded"
        ? "degraded"
        : norm === "down" || norm === "critical"
          ? "critical"
          : norm === "configured"
            ? "configured"
            : "unknown";
  const displayLabel = norm === "unknown" ? "Monitoring unknown" : health;
  return (
    <span
      className={`ws-health ws-health-${badgeClass}`}
      aria-label={`Health: ${displayLabel}`}
    >
      <i aria-hidden="true" />
      {displayLabel}
    </span>
  );
}
export function ServiceDrawing({ project }: { project: Project }) {
  const count = project.services.length;
  return (
    <svg
      className="ws-service-drawing"
      viewBox="0 0 360 130"
      role="img"
      aria-label={
        count
          ? `${project.name}: ${project.services.map((s) => s.name).join(", ")}. Registered service inventory diagram.`
          : "No services configured"
      }
    >
      <g
        className="ws-drawing-grid"
        stroke="currentColor"
        strokeWidth=".4"
        opacity=".18"
      >
        <path d="M0 25H360M0 65H360M0 105H360M20 0V130M100 0V130M180 0V130M260 0V130M340 0V130" />
      </g>
      <path
        d="M8 8h12M14 2v12M340 122h12M346 116v12"
        stroke="currentColor"
        opacity=".5"
      />
      <g fill="none" stroke="currentColor" strokeWidth=".8">
        <path d="M155 15h50v22h-50z" />
        <path
          className="ws-drawing-trace"
          pathLength="1"
          d={
            count
              ? `M180 37v18M${180 / count} 55H${360 - 180 / count}`
              : "M180 37v45"
          }
        />
        {project.services.map((s, i) => {
          const x = ((i + 0.5) * 360) / count;
          return (
            <g key={s.id}>
              <path
                className="ws-drawing-trace"
                pathLength="1"
                d={`M${x} 55v16`}
              />
              <path d={`M${x - 32} 71h64v28h-64zM${x - 28} 75h56v20h-56z`} />
              <circle
                className={`ws-node-${s.health}`}
                cx={x + 25}
                cy="85"
                r="2.5"
              />
            </g>
          );
        })}
      </g>
      <g
        fill="currentColor"
        fontSize="7"
        textAnchor="middle"
        fontFamily="var(--font-mono)"
      >
        <text x="180" y="29">
          APPLICATION
        </text>
        {project.services.map((s, i) => (
          <text key={s.id} x={((i + 0.5) * 360) / count} y="114">
            {s.name.toUpperCase()}
          </text>
        ))}
        {!count && (
          <text x="180" y="105">
            AWAITING SERVICE INVENTORY
          </text>
        )}
      </g>
    </svg>
  );
}
