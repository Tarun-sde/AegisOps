import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";
import Link from "next/link";

export type ButtonVariant =
  "primary" | "secondary" | "outline" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  href?: string;
  className?: string;
  style?: CSSProperties;
  loading?: boolean;
}

export function Button({
  children,
  variant = "primary",
  href,
  className = "",
  style,
  loading = false,
  disabled,
  ...rest
}: ButtonProps) {
  const variantStyles: Record<ButtonVariant, CSSProperties> = {
    primary: {
      background: "var(--accent-button-bg)",
      color: "var(--accent-button-text)",
      borderColor: "transparent",
    },
    secondary: {
      background: "var(--bg-surface-elevated)",
      color: "var(--text-primary)",
      borderColor: "var(--border-default)",
    },
    outline: {
      background: "transparent",
      color: "var(--text-primary)",
      borderColor: "var(--border-default)",
    },
    ghost: {
      background: "transparent",
      color: "var(--text-secondary)",
      borderColor: "transparent",
    },
    danger: {
      background: "var(--status-error-bg)",
      color: "var(--status-error-text)",
      borderColor: "var(--status-error-border)",
    },
  };

  const combinedStyle: CSSProperties = {
    ...variantStyles[variant],
    opacity: disabled || loading ? 0.6 : 1,
    cursor: disabled || loading ? "not-allowed" : "pointer",
    ...style,
  };

  if (href && !disabled && !loading) {
    return (
      <Link
        href={href}
        className={`button ${className}`.trim()}
        style={combinedStyle}
      >
        {children}
      </Link>
    );
  }

  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`button ${className}`.trim()}
      style={combinedStyle}
    >
      {loading ? (
        <>
          <span
            aria-hidden="true"
            style={{ animation: "spin 1s linear infinite" }}
          >
            ⟳
          </span>
          <span>{children}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
