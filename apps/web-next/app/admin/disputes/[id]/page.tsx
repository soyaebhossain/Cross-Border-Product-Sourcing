"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import {
  getAdminDispute,
  type CustomerDispute,
  updateAdminDispute,
} from "../../../../lib/customer-api";
import { formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";
import { useAdminAccess } from "../../../../lib/use-admin-access";

const transitions: Record<string, string[]> = {
  OPEN: ["UNDER_REVIEW", "RESOLVED", "REJECTED"],
  UNDER_REVIEW: ["RESOLVED", "REJECTED"],
  RESOLVED: [],
  REJECTED: [],
  CANCELLED: [],
};

export default function AdminDisputeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [dispute, setDispute] = useState<CustomerDispute | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [pendingStatus, setPendingStatus] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const { locale, intlLocale } = useLocale();
  const { isAdmin } = useAdminAccess();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDispute(await getAdminDispute(id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "বিরোধের তথ্য লোড করা যায়নি।" : "Dispute could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, id]);
  useEffect(() => { void load(); }, [load]);

  const submitDecision = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!dispute || !pendingStatus || note.trim().length < 3) return;
    setSaving(true);
    setError("");
    try {
      const result = await updateAdminDispute(dispute.id, pendingStatus, note.trim());
      setDispute(result);
      setPendingStatus(null);
      setNote("");
      setToast(bn ? "সিদ্ধান্ত সংরক্ষিত, audit log তৈরি এবং customer notification queue করা হয়েছে।" : "Decision saved, audited and queued for customer notification.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "সিদ্ধান্ত সংরক্ষণ করা যায়নি।" : "Decision could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "বিরোধের তথ্য লোড হচ্ছে…" : "Loading dispute…"}</div>;
  if (!dispute) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "রেকর্ড পাওয়া যায়নি" : "Dispute unavailable"}</strong><span>{error}</span><button type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div></div>;

  const allowed = transitions[dispute.status] || [];
  return <div className="admin-page">
    <header className="admin-page-header">
      <div>
        <Link className="account-back-link" href="/admin/disputes">← {bn ? "বিরোধ তালিকা" : "Dispute queue"}</Link>
        <p className="admin-eyebrow">{dispute.public_id}</p>
        <h1>{dispute.type.replaceAll("_", " ")}</h1>
        <p>{bn ? "অর্ডার" : "Order"} #{dispute.order_id} · {bn ? "তৈরি" : "Created"} {formatDateTime(dispute.created_at, intlLocale)}</p>
      </div>
      <div className="admin-toolbar"><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></div>
    </header>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "অ্যাকশন ব্যর্থ" : "Action failed"}</strong><span>{error}</span><button type="button" onClick={() => setError("")}>{bn ? "বন্ধ করুন" : "Dismiss"}</button></div> : null}
    {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}

    <section className="admin-detail-grid">
      <article className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "বিরোধের তথ্য" : "Dispute information"}</h2><p>{bn ? "কাস্টমার ও order context" : "Customer and order context"}</p></div><span className={`admin-status admin-status--${dispute.status.toLowerCase()}`}>{dispute.status.replaceAll("_", " ")}</span></div>
        <dl className="account-definition-list">
          <div><dt>{bn ? "কাস্টমার" : "Customer"}</dt><dd>{isAdmin ? <Link href={`/admin/users/${dispute.user_id}`}>User #{dispute.user_id}</Link> : `User #${dispute.user_id}`}</dd></div>
          <div><dt>{bn ? "অর্ডার" : "Order"}</dt><dd><Link href={`/admin/orders/${dispute.order_id}`}>Order #{dispute.order_id}</Link></dd></div>
          <div><dt>{bn ? "ধরন" : "Type"}</dt><dd>{dispute.type.replaceAll("_", " ")}</dd></div>
          <div><dt>{bn ? "সর্বশেষ আপডেট" : "Last updated"}</dt><dd>{formatDateTime(dispute.updated_at, intlLocale)}</dd></div>
          <div><dt>{bn ? "সিদ্ধান্তের সময়" : "Decided at"}</dt><dd>{formatDateTime(dispute.decided_at, intlLocale)}</dd></div>
          <div><dt>{bn ? "সিদ্ধান্ত নিয়েছেন" : "Decision by"}</dt><dd>{dispute.decided_by_user_id ? (isAdmin ? <Link href={`/admin/users/${dispute.decided_by_user_id}`}>User #{dispute.decided_by_user_id}</Link> : `User #${dispute.decided_by_user_id}`) : "—"}</dd></div>
          <div><dt>Request ID</dt><dd>{dispute.request_id || "—"}</dd></div>
        </dl>
      </article>

      <article className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "সিদ্ধান্ত" : "Resolution"}</h2><p>{bn ? "শুধু অনুমোদিত transition দেখানো হচ্ছে" : "Only valid state transitions are available"}</p></div></div>
        {allowed.length ? <div className="admin-action-grid">{allowed.map(status => <button className={status === "REJECTED" ? "admin-button admin-button--danger" : "admin-button admin-button--secondary"} type="button" key={status} onClick={() => { setPendingStatus(status); setNote(""); }}>{status.replaceAll("_", " ")}</button>)}</div> : <div className="admin-empty"><strong>{bn ? "চূড়ান্ত স্ট্যাটাস" : "Terminal status"}</strong><span>{bn ? "এই বিরোধে আর কোনো state transition অনুমোদিত নয়।" : "No further state transition is allowed for this dispute."}</span></div>}
      </article>
    </section>

    <section className="admin-detail-grid">
      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "কাস্টমারের অভিযোগ" : "Customer complaint"}</h2></div></div><p className="admin-policy-copy">{dispute.description}</p></article>
      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "প্রত্যাশিত সমাধান" : "Requested resolution"}</h2></div></div><p className="admin-policy-copy">{dispute.requested_resolution}</p></article>
    </section>

    {dispute.resolution_note ? <section className="admin-card admin-ops-section"><div className="admin-card__header"><div><h2>{bn ? "সর্বশেষ সিদ্ধান্তের note" : "Latest resolution note"}</h2><p>{formatDateTime(dispute.decided_at || dispute.updated_at, intlLocale)}</p></div></div><p className="admin-policy-copy">{dispute.resolution_note}</p></section> : null}

    <AdminModal open={pendingStatus !== null} onClose={() => !saving && setPendingStatus(null)} title={bn ? "বিরোধের সিদ্ধান্ত নিশ্চিত করুন" : "Confirm dispute decision"} description={`${dispute.public_id} · ${dispute.status.replaceAll("_", " ")} → ${pendingStatus?.replaceAll("_", " ") || ""}`}>
      <form className="admin-modal__form" onSubmit={submitDecision}>
        <label><span>{pendingStatus === "REJECTED" ? (bn ? "প্রত্যাখ্যানের কারণ (আবশ্যিক)" : "Rejection reason (required)") : (bn ? "সিদ্ধান্তের note (আবশ্যিক)" : "Decision note (required)")}</span><textarea rows={5} minLength={3} maxLength={2000} required value={note} onChange={event => setNote(event.target.value)} /></label>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setPendingStatus(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className={pendingStatus === "REJECTED" ? "admin-button admin-button--danger" : "admin-button admin-button--primary"} type="submit" disabled={saving || note.trim().length < 3}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সিদ্ধান্ত সংরক্ষণ" : "Save decision")}</button></div>
      </form>
    </AdminModal>
  </div>;
}
