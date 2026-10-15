"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { keepDialogFocus } from "./dialog-focus";
export function DetailDialog({
  title,
  open,
  onClose,
  children,
  drawer = false,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  drawer?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const trigger = document.activeElement as HTMLElement | null;
    dialog.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = overflow;
      trigger?.focus({ preventScroll: true });
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`ws-modal an-dialog ${drawer ? "an-drawer" : ""}`}
      aria-label={title}
      onCancel={onClose}
      onClose={onClose}
      onKeyDown={keepDialogFocus}
      data-lenis-prevent
    >
      <div className="ws-modal-top">
        <span>Authorized service · read-only details</span>
        <button onClick={onClose} aria-label="Close details">
          ×
        </button>
      </div>
      <h2>{title}</h2>
      {children}
    </dialog>
  );
}
