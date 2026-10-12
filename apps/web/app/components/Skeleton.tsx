import type { CSSProperties } from "react";

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  className?: string;
  style?: CSSProperties;
}

export function Skeleton({
  width = "100%",
  height = "20px",
  borderRadius = "var(--radius-sm)",
  className = "",
  style,
}: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={className}
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: "var(--bg-surface-elevated)",
        opacity: 0.7,
        ...style,
      }}
    />
  );
}
