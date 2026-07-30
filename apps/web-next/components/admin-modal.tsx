"use client";

import { useEffect, useRef } from "react";

export function AdminModal({
  open,
  title,
  description,
  children,
  onClose,
}: {
  open: boolean;
  title: string;
  description?: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog ref={dialogRef} className="admin-modal" onCancel={onClose} onClose={onClose} aria-labelledby="admin-modal-title" aria-describedby={description ? "admin-modal-description" : undefined}>
      <div className="admin-modal__header"><div><h2 id="admin-modal-title">{title}</h2>{description ? <p id="admin-modal-description">{description}</p> : null}</div><button type="button" onClick={onClose} aria-label="Close dialog">×</button></div>
      {children}
    </dialog>
  );
}
