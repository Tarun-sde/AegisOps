import type { CSSProperties, ReactNode } from "react";

export type BadgeVariant =
  "default" | "success" | "warning" | "error" | "info" | "neutral";

export interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
  style?: CSSProperties;
}

export function Badge({
  children,
  variant = "default",
  className = "",
  style,
}: BadgeProps) {
  const variantClass = `badge badge-${variant}`;
  return (
    <span className={`${variantClass} ${className}`.trim()} style={style}>
      {children}
    </span>
  );
}
