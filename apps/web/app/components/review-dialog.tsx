"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { keepDialogFocus } from "./dialog-focus";
export function ReviewDialog({
  children,
  onClose,
  busy,
}: {
  children: ReactNode;
  onClose: () => void;
  busy: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current!;
    const trigger = document.activeElement as HTMLElement | null;
    node.showModal();
    return () => {
      node.close();
      trigger?.focus();
    };
  }, []);
  return (
    <dialog
      className="ws-modal an-dialog"
      data-lenis-prevent
      ref={dialog}
      aria-label="Review remediation proposal"
      onKeyDown={keepDialogFocus}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
    >
      {children}
    </dialog>
  );
}
