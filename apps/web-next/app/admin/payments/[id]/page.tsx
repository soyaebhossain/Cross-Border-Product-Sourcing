"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import { PaymentProofPreview } from "../../../../components/payment-proof-preview";
import { getAdminPaymentDetail, reverseAdminPayment, type AdminOrderDetail } from "../../../../lib/admin-api";
import { resolveImageUrl } from "../../../../lib/api";
import { formatCurrency, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

export default function AdminPaymentDetailPage() {
  const params = useParams<{ id: string }>();
  const [order, setOrder] = useState<AdminOrderDetail | null>(null);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setOrder((await getAdminPaymentDetail(params.id)).order); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Payment could not be loaded."); }
    finally { setLoading(false); }
  }, [params.id]);
  useEffect(() => { void load(); }, [load]);

  const reverse = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!order?.payment) return;
    setSaving(true); setError("");
    try { await reverseAdminPayment(order.payment.id, note); setOpen(false); setNote(""); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Payment could not be reversed."); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="admin-auth-check"><span className="admin-spinner" />{bn ? "পেমেন্ট লোড হচ্ছে…" : "Loading payment…"}</div>;
  if (!order?.payment) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert">{error || (bn ? "পেমেন্ট পাওয়া যায়নি।" : "Payment not found.")}</div></div>;
  const payment = order.payment;
  const proofUrl = resolveImageUrl(payment.proof_url);
  const canReverse = payment.decision === "APPROVED" && ["PENDING", "CONFIRMED", "CANCELLED"].includes(order.status);
  return <div className="admin-page">
    <header className="admin-page-header"><div><Link className="account-back-link" href="/admin/payments">← {bn ? "পেমেন্ট তালিকা" : "Payment list"}</Link><p className="admin-eyebrow">{bn ? "Payment proof detail" : "Payment proof detail"}</p><h1>{bn ? "পেমেন্ট" : "Payment"} #{payment.id}</h1><p>{bn ? "অর্ডার" : "Order"} #{order.id} · {payment.channel} · {payment.transaction_id}</p></div><div className="admin-toolbar"><Link className="admin-button admin-button--secondary" href={`/admin/orders/${order.id}`}>{bn ? "অর্ডার detail" : "Order detail"}</Link>{canReverse ? <button className="admin-button admin-button--danger" type="button" onClick={() => setOpen(true)}>{bn ? "Verification reverse" : "Reverse verification"}</button> : null}</div></header>
    {error ? <div className="admin-alert admin-alert--error" role="alert"><span>{error}</span><button onClick={() => setError("")}>{bn ? "বন্ধ" : "Dismiss"}</button></div> : null}
    <section className="admin-detail-grid">
      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "Verification" : "Verification"}</h2><p>{bn ? "সিদ্ধান্তের সম্পূর্ণ provenance" : "Complete decision provenance"}</p></div><span className={`admin-status admin-status--${payment.decision.toLowerCase()}`}>{payment.decision}</span></div><dl className="account-definition-list">
        <div><dt>Transaction ID</dt><dd>{payment.transaction_id}</dd></div><div><dt>{bn ? "Submitted" : "Submitted"}</dt><dd>{formatDateTime(payment.submitted_at, intlLocale)}</dd></div><div><dt>{bn ? "সিদ্ধান্তের সময়" : "Decision time"}</dt><dd>{formatDateTime(payment.decided_at, intlLocale)}</dd></div><div><dt>{bn ? "Verifier" : "Verifier"}</dt><dd>{payment.verifier?.username || payment.verifier?.email || (payment.verifier?.id ? `User #${payment.verifier.id}` : "—")}</dd></div><div><dt>{bn ? "কারণ" : "Reason"}</dt><dd>{payment.reason || "—"}</dd></div>
      </dl><PaymentProofPreview src={proofUrl} label={`${bn ? "Payment proof" : "Payment proof"} #${payment.id}`} /></article>
      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "Financial effect" : "Financial effect"}</h2><p>{bn ? "Recomputed order ledger" : "Recomputed order ledger"}</p></div></div><dl className="account-definition-list">
        <div><dt>{bn ? "অগ্রিম" : "Advance"}</dt><dd>{formatCurrency(order.advance_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Gross collected" : "Gross collected"}</dt><dd>{formatCurrency(order.financials?.gross_collected_bdt as string, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Refunds" : "Refunds"}</dt><dd>{formatCurrency(order.financials?.refunds_bdt as string, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Net verified" : "Net verified"}</dt><dd>{formatCurrency(order.financials?.net_verified_cash_bdt as string, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Outstanding" : "Outstanding"}</dt><dd>{formatCurrency(order.financials?.outstanding_bdt as string, "BDT", intlLocale)}</dd></div>
      </dl></article>
    </section>
    <AdminModal open={open} onClose={() => !saving && setOpen(false)} title={bn ? "Payment verification reverse করবেন?" : "Reverse payment verification?"} description={bn ? "শুধু pending/confirmed/cancelled order-এ বৈধ; purchased order-এ refund ব্যবহার করুন।" : "Valid only for pending, confirmed or cancelled orders; use a refund after purchase."}><form className="admin-modal__form" onSubmit={reverse}><label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} required rows={3} value={note} onChange={event => setNote(event.target.value)} /></label><div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setOpen(false)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--danger" disabled={saving || note.trim().length < 3}>{saving ? (bn ? "Reverse হচ্ছে…" : "Reversing…") : (bn ? "Reverse নিশ্চিত করুন" : "Confirm reversal")}</button></div></form></AdminModal>
  </div>;
}
