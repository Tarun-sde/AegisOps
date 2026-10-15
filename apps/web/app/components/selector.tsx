"use client";
import { useEffect, useId, useRef, useState } from "react";
type Option = {
  id: string;
  label: string;
  description?: string;
  selected?: boolean;
  action: () => void;
};
export function Selector({
  label,
  value,
  options,
  menu = false,
  compact = false,
}: {
  label: string;
  value: string;
  options: Option[];
  menu?: boolean;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null),
    trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const close = (restore = false) => {
    setOpen(false);
    if (restore) trigger.current?.focus();
  };
  useEffect(() => {
    if (!open) return;
    const buttons =
      root.current?.querySelectorAll<HTMLButtonElement>("[data-option]");
    buttons?.[
      Math.max(
        0,
        options.findIndex((o) => o.selected),
      )
    ]?.focus();
    const outside = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
    // Options can be freshly derived while the selector remains open.
  }, [open]);
  return (
    // Selector delegates arrow/Escape navigation to its native buttons.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      className={`ws-selector ${compact ? "ws-selector-compact" : ""}`}
      ref={root}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) close();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          close(true);
        }
        if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
          e.preventDefault();
          if (!open) {
            setOpen(true);
            return;
          }
          const items = Array.from(
            root.current!.querySelectorAll<HTMLButtonElement>("[data-option]"),
          );
          const current = items.indexOf(
            document.activeElement as HTMLButtonElement,
          );
          const next =
            e.key === "Home"
              ? 0
              : e.key === "End"
                ? items.length - 1
                : (current + (e.key === "ArrowDown" ? 1 : -1) + items.length) %
                  items.length;
          items[next]?.focus();
        }
      }}
    >
      <button
        className="ws-selector-trigger"
        ref={trigger}
        aria-label={label}
        role={menu ? undefined : "combobox"}
        aria-haspopup={menu ? "menu" : "listbox"}
        aria-controls={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        title={label}
      >
        <span>{value}</span>
        <span aria-hidden="true">{menu ? "" : "↕"}</span>
      </button>
      {open && (
        <div
          id={id}
          role={menu ? "menu" : "listbox"}
          aria-label={label}
          className="ws-popover"
          data-lenis-prevent
        >
          <div className="ws-popover-label mono">{label}</div>
          {options.map((option) => (
            <button
              key={option.id}
              data-option
              role={menu ? "menuitem" : "option"}
              aria-selected={menu ? undefined : !!option.selected}
              tabIndex={-1}
              onClick={() => {
                close(true);
                option.action();
              }}
            >
              <span>
                <strong>{option.label}</strong>
                {option.description && <small>{option.description}</small>}
              </span>
              <span aria-hidden="true">{option.selected ? "✓" : "↗"}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
