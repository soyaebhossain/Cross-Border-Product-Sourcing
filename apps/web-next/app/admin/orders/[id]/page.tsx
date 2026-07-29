"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import { PaymentProofPreview } from "../../../../components/payment-proof-preview";
import {
  createAdminRefund,
  getAdminOrderDetail,
  reverseAdminPayment,
  reverseAdminRefund,
  updateAdminSettlement,
  type AdminOrderDetail,
} from "../../../../lib/admin-api";
import { resolveImageUrl, updateOrderStatus } from "../../../../lib/api";
import { formatCurrency, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

const statusTransitions: Record<string, string[]> = {
  PENDING: ["CONFIRMED", "CANCELLED"],
  CONFIRMED: ["PURCHASED", "CANCELLED"],
  PURCHASED: ["IN_TRANSIT", "CANCELLED"],
  IN_TRANSIT: ["CUSTOMS", "CANCELLED"],
  CUSTOMS: ["LOCAL_DISPATCH", "CANCELLED"],
  LOCAL_DISPATCH: ["DELIVERED", "CANCELLED"],
  DELIVERED: [],
  CANCELLED: [],
};
type Action = "status" | "settlement" | "refund" | "reverse-payment" | { refundId: number } | null;

function localTimestamp(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

function dhakaTimestamp(value: string) {
  return value ? `${value}:00+06:00` : undefined;
}

export default function AdminOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const [order, setOrder] = useState<AdminOrderDetail | null>(null);
  const [action, setAction] = useState<Action>(null);
  const [status, setStatus] = useState("");
  const [tracking, setTracking] = useState("");
  const [note, setNote] = useState("");
  const [actualCost, setActualCost] = useState("");
  const [promisedAt, setPromisedAt] = useState("");
  const [deliveredAt, setDeliveredAt] = useState("");
  const [defect, setDefect] = useState(false);
  const [refundAmount, setRefundAmount] = useState("");
  const [transactionId, setTransactionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getAdminOrderDetail(params.id);
      setOrder(result);
      setStatus(result.status);
      setTracking(result.shipment?.tracking_number || "");
      setActualCost(result.actual_cost_bdt || "");
      setPromisedAt(localTimestamp(result.promised_delivery_at));
      setDeliveredAt(localTimestamp(result.delivered_at));
      setDefect(Boolean(result.quality_defect_reported));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "অর্ডার লোড করা যায়নি।" : "Order could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [params.id, bn]);

  useEffect(() => { void load(); }, [load]);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3500);
  };

  const close = () => {
    if (saving) return;
    setAction(null);
    setNote("");
    setRefundAmount("");
    setTransactionId("");
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!order || !action) return;
    setSaving(true);
    setError("");
    try {
      if (action === "status") {
        await updateOrderStatus(order.id, status, note, tracking, note);
      } else if (action === "settlement") {
        await updateAdminSettlement(order.id, {
          actual_cost_bdt: actualCost === "" ? undefined : Number(actualCost),
          promised_delivery_at: dhakaTimestamp(promisedAt),
          delivered_at: dhakaTimestamp(deliveredAt),
          quality_defect_reported: defect,
          note,
        });
      } else if (action === "refund") {
        await createAdminRefund(order.id, { amount_bdt: Number(refundAmount), transaction_id: transactionId.trim() || undefined, reason: note });
      } else if (action === "reverse-payment" && order.payment) {
        await reverseAdminPayment(order.payment.id, note);
      } else if (typeof action === "object") {
        await reverseAdminRefund(action.refundId, note);
      }
      notify(bn ? "পরিবর্তন audit log-সহ সংরক্ষিত হয়েছে।" : "Change saved with an audit record.");
      setAction(null);
      setNote("");
      setRefundAmount("");
      setTransactionId("");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "পরিবর্তন সংরক্ষণ করা যায়নি।" : "Change could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "অর্ডার লোড হচ্ছে…" : "Loading order…"}</div>;
  if (!order) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "অর্ডার পাওয়া যায়নি" : "Order unavailable"}</strong><span>{error}</span><button type="button" onClick={load}>{bn ? "আবার চেষ্টা" : "Retry"}</button></div></div>;

  const paymentDecision = order.payment?.decision || "NO PROOF";
  const canReversePayment = order.payment?.decision === "APPROVED" && ["PENDING", "CONFIRMED", "CANCELLED"].includes(order.status);
  const canRefund = order.payment?.decision === "APPROVED" && order.payment.verified;
  const paymentApproved = order.payment?.decision === "APPROVED" && order.payment.verified;
  const nextStatuses = (statusTransitions[order.status] || []).filter(value => value !== "CONFIRMED" || paymentApproved);
  const terminalStatus = ["DELIVERED", "CANCELLED"].includes(order.status);
  const statusOptions = [order.status, ...nextStatuses];
  const trackingRequired = action === "status" && status === "IN_TRANSIT" && !tracking.trim();
  return <div className="admin-page">
    <header className="admin-page-header">
      <div><Link className="account-back-link" href="/admin/orders">← {bn ? "অর্ডার তালিকা" : "Order list"}</Link><p className="admin-eyebrow">{bn ? "Dedicated admin detail" : "Dedicated admin detail"}</p><h1>{bn ? "অর্ডার" : "Order"} #{order.id}</h1><p>{formatDateTime(order.created_at, intlLocale)} · {order.country} · {order.mode} · {order.delivery_type}</p></div>
      <div className="admin-toolbar"><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button><button className="admin-button admin-button--secondary" type="button" onClick={() => setAction("settlement")}>{bn ? "Settlement / SLA" : "Settlement / SLA"}</button><button className="admin-button admin-button--primary" type="button" disabled={terminalStatus} title={terminalStatus ? (bn ? "Terminal order status আর পরিবর্তন করা যায় না।" : "A terminal order status cannot be changed.") : undefined} onClick={() => { setStatus(order.status); setAction("status"); }}>{bn ? "Status আপডেট" : "Update status"}</button></div>
    </header>
    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "Action ব্যর্থ" : "Action failed"}</strong><span>{error}</span><button onClick={() => setError("")}>{bn ? "বন্ধ" : "Dismiss"}</button></div> : null}

    <section className="admin-detail-grid">
      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "অর্ডার ও customer" : "Order and customer"}</h2><p>{bn ? "Customer route নয়; admin-only detail endpoint" : "Admin-only detail endpoint; not the customer route"}</p></div><span className={`admin-status admin-status--${order.status.toLowerCase()}`}>{order.status.replaceAll("_", " ")}</span></div><dl className="account-definition-list">
        <div><dt>{bn ? "Customer" : "Customer"}</dt><dd><Link href={`/admin/users/${order.customer.id}`}>{order.customer.username || order.customer.email || `User #${order.customer.id}`}</Link></dd></div>
        <div><dt>{bn ? "সেভড কোট" : "Saved quote"}</dt><dd>{order.saved_quote_id ? <Link href={`/admin/quotes/${order.saved_quote_id}`}>#{order.saved_quote_id}</Link> : "—"}</dd></div>
        <div><dt>{bn ? "Tracking" : "Tracking"}</dt><dd>{order.shipment?.tracking_number || "—"}</dd></div>
        <div><dt>{bn ? "Promised delivery" : "Promised delivery"}</dt><dd>{formatDateTime(order.promised_delivery_at, intlLocale)}</dd></div>
        <div><dt>{bn ? "Delivered" : "Delivered"}</dt><dd>{formatDateTime(order.delivered_at, intlLocale)}</dd></div>
        <div><dt>{bn ? "Quality defect" : "Quality defect"}</dt><dd>{order.quality_defect_reported === null || order.quality_defect_reported === undefined ? "N/A" : order.quality_defect_reported ? (bn ? "রিপোর্ট হয়েছে" : "Reported") : (bn ? "রিপোর্ট নেই" : "Not reported")}</dd></div>
      </dl></article>

      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "Payment verification" : "Payment verification"}</h2><p>{bn ? "Verifier, সময় ও proof" : "Verifier, time and proof"}</p></div><span className={`admin-status admin-status--${paymentDecision.toLowerCase().replaceAll(" ", "_")}`}>{paymentDecision}</span></div>{order.payment ? <dl className="account-definition-list">
        <div><dt>{bn ? "Transaction" : "Transaction"}</dt><dd>{order.payment.transaction_id}</dd></div><div><dt>{bn ? "চ্যানেল" : "Channel"}</dt><dd>{order.payment.channel}</dd></div><div><dt>{bn ? "Verifier" : "Verifier"}</dt><dd>{order.payment.verifier?.username || (order.payment.verifier?.id ? `User #${order.payment.verifier.id}` : "—")}</dd></div><div><dt>{bn ? "সিদ্ধান্তের সময়" : "Decision time"}</dt><dd>{formatDateTime(order.payment.decided_at, intlLocale)}</dd></div><div><dt>{bn ? "কারণ" : "Reason"}</dt><dd>{order.payment.reason || "—"}</dd></div><div><dt>{bn ? "Proof" : "Proof"}</dt><dd>{order.payment.proof_url ? <a href={resolveImageUrl(order.payment.proof_url) || "#"} target="_blank" rel="noreferrer">{bn ? "নতুন tab-এ খুলুন" : "Open proof"}</a> : "—"}</dd></div>
      </dl> : null}<PaymentProofPreview src={resolveImageUrl(order.payment?.proof_url)} label={`${bn ? "Payment proof" : "Payment proof"} · ${bn ? "অর্ডার" : "order"} #${order.id}`} /><div className="admin-detail-actions">{canReversePayment ? <button className="admin-button admin-button--danger" type="button" onClick={() => setAction("reverse-payment")}>{bn ? "Verification reverse" : "Reverse verification"}</button> : null}{canRefund ? <button className="admin-button admin-button--secondary" type="button" onClick={() => setAction("refund")}>{bn ? "Refund দিন" : "Issue refund"}</button> : null}</div></article>
    </section>

    <section className="admin-detail-grid">
      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "Financial ledger" : "Financial ledger"}</h2><p>{bn ? "বর্তমান recomputed snapshot" : "Current recomputed snapshot"}</p></div></div><dl className="account-definition-list">
        <div><dt>{bn ? "অর্ডার মূল্য" : "Order value"}</dt><dd>{formatCurrency(order.total_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "অগ্রিম" : "Advance"}</dt><dd>{formatCurrency(order.advance_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Gross collected" : "Gross collected"}</dt><dd>{formatCurrency(order.financials?.gross_collected_bdt as string, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Refunds" : "Refunds"}</dt><dd>{formatCurrency(order.financials?.refunds_bdt as string, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Net verified cash" : "Net verified cash"}</dt><dd>{formatCurrency(order.financials?.net_verified_cash_bdt as string, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Outstanding" : "Outstanding"}</dt><dd>{formatCurrency(order.financials?.outstanding_bdt as string, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Actual cost" : "Actual cost"}</dt><dd>{formatCurrency(order.actual_cost_bdt, "BDT", intlLocale)}</dd></div>
      </dl></article>
      <article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "Refund ও reversal" : "Refunds and reversals"}</h2><p>{bn ? "Unique transaction ও audit state" : "Unique transaction and audit state"}</p></div></div>{order.adjustments?.length ? <div className="admin-adjustment-list">{order.adjustments.map(item => <div key={item.id}><div><strong>{item.type || item.adjustment_type}</strong><span className={`admin-status admin-status--${(item.status || "posted").toLowerCase()}`}>{item.status}</span></div><span>{formatCurrency(item.amount_bdt, "BDT", intlLocale)} · {item.transaction_id || "—"}</span><small>{item.reason || item.note || "—"} · {formatDateTime(item.created_at, intlLocale)}</small>{(item.type || item.adjustment_type) === "REFUND" && item.status === "POSTED" ? <button className="admin-row-button admin-row-button--danger" type="button" onClick={() => setAction({ refundId: item.id })}>{bn ? "Refund reverse" : "Reverse refund"}</button> : null}</div>)}</div> : <div className="admin-empty">{bn ? "কোনো adjustment নেই।" : "No adjustments."}</div>}</article>
    </section>

    <section className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "অর্ডারের item" : "Order items"}</h2><p>{bn ? "Locked quote snapshot থেকে" : "From the locked quote snapshot"}</p></div></div><div className="admin-table-wrap"><table className="admin-data-table"><thead><tr><th>{bn ? "পণ্য" : "Product"}</th><th>{bn ? "ভ্যারিয়েন্ট" : "Variant"}</th><th>{bn ? "পরিমাণ" : "Quantity"}</th><th>Offer</th></tr></thead><tbody>{order.items.map(item => <tr key={item.id}><td>{item.product_name || "—"}</td><td>{item.variant_name || `#${item.variant_id}`}</td><td>{item.qty}</td><td>{item.offer_id ? `#${item.offer_id}` : "—"}</td></tr>)}</tbody></table></div></section>

    <section className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "সম্পূর্ণ audit timeline" : "Complete order timeline"}</h2><p>{bn ? "Actor, note ও request ID" : "Actor, note and request ID"}</p></div></div><ol className="admin-audit-timeline">{order.history?.map(item => <li key={item.id}><span aria-hidden /><div><strong>{item.status.replaceAll("_", " ")}</strong><p>{item.note || "—"}</p><small>{formatDateTime(item.created_at, intlLocale)} · {item.actor_role || "system"} {item.actor_user_id ? `#${item.actor_user_id}` : ""} · {item.request_id || "no request ID"}</small></div></li>)}</ol></section>

    <AdminModal open={action !== null} onClose={close} title={action === "status" ? (bn ? "অর্ডার status আপডেট" : "Update order status") : action === "settlement" ? (bn ? "Settlement ও SLA data" : "Settlement and SLA data") : action === "refund" ? (bn ? "Refund তৈরি করুন" : "Create refund") : action === "reverse-payment" ? (bn ? "Payment verification reverse" : "Reverse payment verification") : (bn ? "Refund reverse" : "Reverse refund")} description={bn ? "প্রতিটি পরিবর্তন audit log-এ actor ও সময়সহ থাকবে।" : "Every change is recorded with actor and time in the audit log."}>
      <form className="admin-modal__form" onSubmit={submit}>
        {action === "status" ? <><label><span>{bn ? "অনুমোদিত পরবর্তী status" : "Allowed next status"}</span><select value={status} onChange={event => setStatus(event.target.value)}>{statusOptions.map(value => <option key={value} value={value}>{value === order.status ? `${value} · ${bn ? "শুধু logistics update" : "logistics update only"}` : value}</option>)}</select></label>{order.status === "PENDING" && !paymentApproved ? <div className="admin-alert"><span>{bn ? "Payment approve না হওয়া পর্যন্ত CONFIRMED নির্বাচন করা যাবে না।" : "CONFIRMED becomes available only after payment approval."}</span></div> : null}<label><span>{status === "IN_TRANSIT" ? (bn ? "Tracking নম্বর (আবশ্যিক)" : "Tracking number (required)") : (bn ? "Tracking নম্বর" : "Tracking number")}</span><input required={status === "IN_TRANSIT"} maxLength={120} value={tracking} onChange={event => setTracking(event.target.value)} /></label></> : null}
        {action === "settlement" ? <><label><span>{bn ? "Actual cost (BDT)" : "Actual cost (BDT)"}</span><input type="number" min="0" step=".01" value={actualCost} onChange={event => setActualCost(event.target.value)} /></label><label><span>{bn ? "Promised delivery (Dhaka time)" : "Promised delivery (Dhaka time)"}</span><input type="datetime-local" value={promisedAt} onChange={event => setPromisedAt(event.target.value)} /></label><label><span>{bn ? "Delivered at (শুধু DELIVERED)" : "Delivered at (DELIVERED only)"}</span><input type="datetime-local" disabled={order.status !== "DELIVERED"} value={deliveredAt} onChange={event => setDeliveredAt(event.target.value)} /></label><label className="admin-checkbox-label"><input type="checkbox" checked={defect} onChange={event => setDefect(event.target.checked)} /><span>{bn ? "Quality defect রিপোর্ট হয়েছে" : "Quality defect reported"}</span></label></> : null}
        {action === "refund" ? <><label><span>{bn ? "Refund amount (BDT)" : "Refund amount (BDT)"}</span><input type="number" min=".01" step=".01" value={refundAmount} onChange={event => setRefundAmount(event.target.value)} required /></label><label><span>{bn ? "Transaction ID (না দিলে secure ID তৈরি হবে)" : "Transaction ID (secure ID generated if blank)"}</span><input minLength={6} maxLength={80} value={transactionId} onChange={event => setTransactionId(event.target.value)} /></label></> : null}
        <label><span>{action === "refund" ? (bn ? "Refund reason" : "Refund reason") : (bn ? "Mandatory audit note" : "Mandatory audit note")}</span><textarea minLength={3} maxLength={1000} rows={3} required value={note} onChange={event => setNote(event.target.value)} /></label>
        {typeof action === "object" && action ? <div className="admin-decision-summary admin-decision-summary--reject"><strong>{bn ? "Refund reversal" : "Refund reversal"}</strong><span>#{action.refundId}</span></div> : null}
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={close} disabled={saving}>{bn ? "বাতিল" : "Cancel"}</button><button className={action === "reverse-payment" || typeof action === "object" ? "admin-button admin-button--danger" : "admin-button admin-button--primary"} type="submit" disabled={saving || note.trim().length < 3 || (action === "refund" && Number(refundAmount) <= 0) || trackingRequired}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "নিশ্চিত করুন" : "Confirm")}</button></div>
      </form>
    </AdminModal>
    {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
  </div>;
}
