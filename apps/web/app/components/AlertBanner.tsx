import type { CSSProperties, ReactNode } from "react";

export type AlertType = "error" | "warning" | "success" | "info";

export interface AlertBannerProps {
  children: ReactNode;
  type?: AlertType;
  title?: string;
  onDismiss?: () => void;
  className?: string;
  style?: CSSProperties;
}

export function AlertBanner({
  children,
  type = "info",
  title,
  onDismiss,
  className = "",
  style,
}: AlertBannerProps) {
  const isStatus = type === "success" || type === "info";
  const role = isStatus ? "status" : "alert";

  const typeStyles: Record<
    AlertType,
    { background: string; border: string; color: string }
  > = {
    error: {
      background: "var(--status-error-bg)",
      border: "1px solid var(--status-error-border)",
      color: "var(--status-error-text)",
    },
    warning: {
      background: "var(--status-warning-bg)",
      border: "1px solid var(--status-warning-border)",
      color: "var(--status-warning-text)",
    },
    success: {
      background: "var(--status-success-bg)",
      border: "1px solid var(--status-success-border)",
      color: "var(--status-success-text)",
    },
    info: {
      background: "var(--status-info-bg)",
      border: "1px solid var(--status-info-border)",
      color: "var(--status-info-text)",
    },
  };

  return (
    <div
      role={role}
      className={className}
      style={{
        padding: "16px 20px",
        marginBottom: "20px",
        borderRadius: "var(--radius-md)",
        fontSize: "0.95rem",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: "12px",
        ...typeStyles[type],
        ...style,
      }}
    >
      <div style={{ flex: 1 }}>
        {title && (
          <strong style={{ display: "block", marginBottom: "4px" }}>
            {title}
          </strong>
        )}
        <div>{children}</div>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss alert"
          style={{
            background: "transparent",
            border: "none",
            color: "inherit",
            cursor: "pointer",
            fontSize: "1.1rem",
            padding: "0 4px",
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      )}
    </div>
  );
}
