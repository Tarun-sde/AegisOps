import { Badge } from "./Badge";
export function StatusBadge({ value }: { value: string }) {
  const v = value.toLowerCase();
  const variant = ["critical", "failed", "error", "p1"].includes(v)
    ? "error"
    : [
          "open",
          "reopened",
          "mitigating",
          "warning",
          "inconclusive",
          "p2",
        ].includes(v)
      ? "warning"
      : ["resolved", "complete", "succeeded"].includes(v)
        ? "success"
        : "neutral";
  return <Badge variant={variant}>{value.replaceAll("_", " ")}</Badge>;
}
