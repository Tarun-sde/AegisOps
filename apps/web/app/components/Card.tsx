import type { CSSProperties, ReactNode } from "react";

export interface CardProps {
  children: ReactNode;
  title?: ReactNode;
  eyebrow?: string;
  badge?: ReactNode;
  description?: string;
  className?: string;
  style?: CSSProperties;
  footer?: ReactNode;
}

export function Card({
  children,
  title,
  eyebrow,
  badge,
  description,
  className = "",
  style,
  footer,
}: CardProps) {
  return (
    <section className={`panel ${className}`.trim()} style={style}>
      {(eyebrow || badge) && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "10px",
          }}
        >
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          {badge && <div>{badge}</div>}
        </div>
      )}
      {title && (
        <h2
          style={{
            marginTop: eyebrow ? "0" : undefined,
            color: "var(--text-primary)",
          }}
        >
          {title}
        </h2>
      )}
      {description && (
        <p style={{ marginTop: "4px", color: "var(--text-secondary)" }}>
          {description}
        </p>
      )}
      <div style={{ marginTop: title || description ? "16px" : undefined }}>
        {children}
      </div>
      {footer && (
        <div
          style={{
            marginTop: "20px",
            paddingTop: "16px",
            borderTop: "1px solid var(--border-default)",
          }}
        >
          {footer}
        </div>
      )}
    </section>
  );
}
