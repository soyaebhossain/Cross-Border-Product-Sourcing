"use client";

import { useState } from "react";
import { archiveAdminEntity } from "../lib/admin-api";
import { useLocale } from "../lib/locale-context";
import { AdminModal } from "./admin-modal";

type Entity = "categories" | "products" | "variants" | "suppliers" | "offers";

export function AdminArchiveAction({
  entity,
  id,
  isActive,
  reload,
  notify,
}: {
  entity: Entity;
  id: number;
  isActive: boolean;
  reload: () => Promise<void>;
  notify: (message: string, kind?: "success" | "error") => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const { locale } = useLocale();
  const bn = locale === "bn";
  const archive = isActive;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await archiveAdminEntity(entity, id, archive, note);
      notify(archive ? (bn ? "Record archive হয়েছে।" : "Record archived.") : (bn ? "Record restore হয়েছে।" : "Record restored."));
      setOpen(false);
      setNote("");
      await reload();
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : (bn ? "পরিবর্তন ব্যর্থ হয়েছে।" : "Change failed."), "error");
    } finally {
      setSaving(false);
    }
  };

  return <>
    <button className={archive ? "admin-row-button admin-row-button--danger" : "admin-row-button admin-row-button--approve"} type="button" onClick={() => setOpen(true)}>{archive ? (bn ? "Archive" : "Archive") : (bn ? "Restore" : "Restore")}</button>
    <AdminModal open={open} onClose={() => !saving && setOpen(false)} title={archive ? (bn ? "Record archive করবেন?" : "Archive record?") : (bn ? "Record restore করবেন?" : "Restore record?")} description={bn ? "Hard delete হবে না; public catalog থেকে archived record বাদ যাবে।" : "This is not a hard delete; archived records are excluded from the public catalog."}>
      <form className="admin-modal__form" onSubmit={submit}><label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} maxLength={1000} required rows={3} value={note} onChange={event => setNote(event.target.value)} /></label><div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setOpen(false)} disabled={saving}>{bn ? "বাতিল" : "Cancel"}</button><button className={archive ? "admin-button admin-button--danger" : "admin-button admin-button--primary"} disabled={saving || note.trim().length < 3}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "নিশ্চিত করুন" : "Confirm")}</button></div></form>
    </AdminModal>
  </>;
}
