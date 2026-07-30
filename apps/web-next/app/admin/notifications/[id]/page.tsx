"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import {
  getAdminOutbox,
  type NotificationDelivery,
  requeueAdminOutbox,
} from "../../../../lib/customer-api";
import { formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";
import { useAdminAccess } from "../../../../lib/use-admin-access";

export default function AdminNotificationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [delivery, setDelivery] = useState<NotificationDelivery | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const { isAdmin, loading: accessLoading } = useAdminAccess();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDelivery(await getAdminOutbox(id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "Delivery record লোড করা যায়নি।" : "Delivery record could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, id]);
  useEffect(() => { void load(); }, [load]);

  const requeue = async () => {
    if (!delivery) return;
    setSaving(true);
    setError("");
    try {
      const result = await requeueAdminOutbox(delivery.id);
      setDelivery(result);
      setConfirming(false);
      setToast(bn ? "Delivery আবার queue করা হয়েছে; নতুন worker attempt-এর অপেক্ষায় আছে।" : "Delivery was requeued and is waiting for a new worker attempt.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "Delivery requeue করা যায়নি।" : "Delivery could not be requeued."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "Delivery লোড হচ্ছে…" : "Loading delivery…"}</div>;
  if (!delivery) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "Delivery পাওয়া যায়নি" : "Delivery unavailable"}</strong><span>{error}</span><button type="button" onClick={() => void load()}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div></div>;

  return <div className="admin-page">
    <header className="admin-page-header">
      <div>
        <Link className="account-back-link" href="/admin/notifications">← {bn ? "Notification outbox" : "Notification outbox"}</Link>
        <p className="admin-eyebrow">{bn ? "Delivery record" : "Delivery record"}</p>
        <h1>Delivery #{delivery.id}</h1>
        <p>{delivery.channel.toUpperCase()} · {delivery.destination_masked || (bn ? "গন্তব্য নেই" : "No destination")} · {formatDateTime(delivery.created_at, intlLocale)}</p>
      </div>
      <div className="admin-toolbar">
        {isAdmin && delivery.status === "FAILED" ? <button className="admin-button admin-button--primary" type="button" onClick={() => setConfirming(true)}>{bn ? "পুনরায় queue" : "Requeue delivery"}</button> : null}
        {!isAdmin && !accessLoading ? <span className="admin-read-only">{bn ? "Operator · শুধু পর্যবেক্ষণ" : "Operator · monitoring only"}</span> : null}
        <button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button>
      </div>
    </header>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "অ্যাকশন ব্যর্থ" : "Action failed"}</strong><span>{error}</span><button type="button" onClick={() => setError("")}>{bn ? "বন্ধ করুন" : "Dismiss"}</button></div> : null}
    {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}

    <section className="admin-detail-grid">
      <article className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "Delivery state" : "Delivery state"}</h2><p>{bn ? "Queue ও retry lifecycle" : "Queue and retry lifecycle"}</p></div><span className={`admin-status admin-status--${delivery.status.toLowerCase()}`}>{delivery.status}</span></div>
        <dl className="account-definition-list">
          <div><dt>{bn ? "চ্যানেল" : "Channel"}</dt><dd>{delivery.channel.toUpperCase()}</dd></div>
          <div><dt>{bn ? "Masked destination" : "Masked destination"}</dt><dd>{delivery.destination_masked || "—"}</dd></div>
          <div><dt>{bn ? "চেষ্টা" : "Attempts"}</dt><dd>{new Intl.NumberFormat(intlLocale).format(delivery.attempts)}</dd></div>
          <div><dt>{bn ? "তৈরি" : "Created"}</dt><dd>{formatDateTime(delivery.created_at, intlLocale)}</dd></div>
          <div><dt>{bn ? "সর্বশেষ চেষ্টা" : "Last attempt"}</dt><dd>{formatDateTime(delivery.last_attempt_at, intlLocale)}</dd></div>
          <div><dt>{bn ? "পরবর্তী চেষ্টা" : "Next attempt"}</dt><dd>{formatDateTime(delivery.next_attempt_at, intlLocale)}</dd></div>
          <div><dt>{bn ? "পাঠানো হয়েছে" : "Sent at"}</dt><dd>{formatDateTime(delivery.sent_at, intlLocale)}</dd></div>
        </dl>
      </article>

      <article className="admin-card">
        <div className="admin-card__header"><div><h2>{bn ? "Provider ফলাফল" : "Provider result"}</h2><p>{bn ? "Credential-safe operational diagnostics" : "Credential-safe operational diagnostics"}</p></div></div>
        <dl className="account-definition-list">
          <div><dt>Provider message ID</dt><dd>{delivery.provider_message_id || "—"}</dd></div>
          <div><dt>Error code</dt><dd>{delivery.error_code || "—"}</dd></div>
          <div><dt>{bn ? "নিরাপদ error detail" : "Safe error detail"}</dt><dd>{delivery.error_detail || "—"}</dd></div>
        </dl>
        {delivery.status === "FAILED" && !isAdmin && !accessLoading ? <div className="admin-ops-note">{bn ? "Requeue শুধু administrator করতে পারবেন।" : "Only an administrator can requeue failed deliveries."}</div> : null}
      </article>
    </section>

    <AdminModal open={confirming} onClose={() => !saving && setConfirming(false)} title={bn ? "ব্যর্থ delivery পুনরায় queue করবেন?" : "Requeue failed delivery?"} description={`#${delivery.id} · ${delivery.channel} · ${delivery.destination_masked || "No destination"}`}>
      <div className="admin-modal__form">
        <div className="admin-decision-summary"><strong>{delivery.error_code || "FAILED"}</strong><span>{bn ? "আগের attempt সংরক্ষিত থাকবে; delivery নতুন worker attempt-এর জন্য QUEUED হবে।" : "Prior attempts remain recorded; the delivery returns to QUEUED for a new worker attempt."}</span></div>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setConfirming(false)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" type="button" disabled={saving} onClick={() => void requeue()}>{saving ? (bn ? "Queue হচ্ছে…" : "Requeuing…") : (bn ? "নিশ্চিত করুন" : "Confirm requeue")}</button></div>
      </div>
    </AdminModal>
  </div>;
}
