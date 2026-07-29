"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import { getOrderById, resolveImageUrl, type OrderDetail } from "../../../../lib/api";
import {
  listPaymentAttempts,
  retryCustomerPayment,
  type PaymentAttempt,
} from "../../../../lib/customer-api";
import { formatBdt, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

const fulfilmentStages = ["PENDING", "CONFIRMED", "PURCHASED", "IN_TRANSIT", "CUSTOMS", "LOCAL_DISPATCH", "DELIVERED"];

export default function OrderDetailsPage() {
  const params = useParams();
  const orderId = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : undefined;
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [paymentAttempts, setPaymentAttempts] = useState<PaymentAttempt[]>([]);
  const [retryOpen, setRetryOpen] = useState(false);
  const [retryFields, setRetryFields] = useState({ channel: "bKash" as "bKash" | "Nagad" | "Rocket" | "Bank", trx_id: "", screenshot_url: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [toast, setToast] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    if (!orderId) return;
    setLoading(true);
    setError("");
    setActionError("");
    try {
      const [orderResult, attemptsResult] = await Promise.allSettled([getOrderById(orderId), listPaymentAttempts(orderId)]);
      if (orderResult.status === "rejected") throw orderResult.reason;
      setOrder(orderResult.value);
      if (attemptsResult.status === "fulfilled") {
        setPaymentAttempts(attemptsResult.value);
      } else {
        setPaymentAttempts([]);
        setActionError(bn ? "পেমেন্ট চেষ্টার ইতিহাস লোড করা যায়নি; অর্ডারের বাকি তথ্য ব্যবহার করা যাবে।" : "Payment attempt history could not be loaded; the rest of the order remains available.");
      }
    } catch {
      setError(bn ? "এই অর্ডার লোড করা যায়নি।" : "This order could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [bn, orderId]);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <div className="empty-state" aria-live="polite">{bn ? "অর্ডারের তথ্য লোড হচ্ছে…" : "Loading order information…"}</div>;
  if (error || !order) return <div className="empty-state" role="alert"><strong>{error || (bn ? "অর্ডার পাওয়া যায়নি।" : "Order not found.")}</strong><button className="button button--ghost" type="button" onClick={load}>{bn ? "আবার চেষ্টা করুন" : "Retry"}</button></div>;

  const paymentDecision = order.manual_payment?.decision || (order.manual_payment?.verified ? "APPROVED" : "PENDING");
  const cancelled = order.status === "CANCELLED";
  const canRetryPayment = order.status === "PENDING" && ["REJECTED", "REVERSED"].includes(paymentDecision);

  const submitPaymentRetry = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!orderId) return;
    setSaving(true);
    setActionError("");
    try {
      await retryCustomerPayment(Number(orderId), {
        channel: retryFields.channel,
        trx_id: retryFields.trx_id.trim(),
        screenshot_url: retryFields.screenshot_url.trim() || undefined,
      });
      setRetryOpen(false);
      setRetryFields({ channel: "bKash", trx_id: "", screenshot_url: "" });
      setToast(bn ? "নতুন পেমেন্ট প্রমাণ জমা হয়েছে এবং যাচাইয়ের অপেক্ষায় আছে।" : "New payment proof was submitted for verification.");
      window.setTimeout(() => setToast(""), 4000);
      await load();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : (bn ? "পেমেন্ট পুনরায় জমা দেওয়া যায়নি।" : "Payment could not be resubmitted."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="account-page">
      <header className="account-page-header">
        <div><Link className="account-back-link" href="/account/orders">← {bn ? "সব অর্ডার" : "All orders"}</Link><p className="eyebrow">{bn ? "অর্ডার বিস্তারিত" : "Order details"}</p><h1>{bn ? "অর্ডার" : "Order"} #{order.id}</h1><p>{formatDateTime(order.created_at, intlLocale)} · {order.country_id || "—"} · {order.mode || "—"}</p></div>
        <button className="button button--ghost" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button>
      </header>

      {actionError ? <div className="account-alert account-alert--danger" role="alert"><span>{actionError}</span><button type="button" onClick={() => setActionError("")}>{bn ? "বন্ধ" : "Dismiss"}</button></div> : null}
      {cancelled ? <div className="account-alert account-alert--danger" role="status"><strong>{bn ? "অর্ডারটি বাতিল হয়েছে" : "This order was cancelled"}</strong><span>{order.history?.findLast?.(entry => entry.status === "CANCELLED")?.note || (bn ? "বিস্তারিত জানতে history দেখুন।" : "See the history for details.")}</span></div> : null}
      {["REJECTED", "REVERSED"].includes(paymentDecision) ? <div className="account-alert account-alert--danger" role="alert"><strong>{paymentDecision === "REVERSED" ? (bn ? "পেমেন্ট সিদ্ধান্ত reversal করা হয়েছে" : "Payment decision was reversed") : (bn ? "পেমেন্ট প্রমাণ গ্রহণ করা হয়নি" : "Payment proof was not accepted")}</strong><span>{order.manual_payment?.decision_reason || (bn ? "নতুন transaction দিয়ে আবার জমা দিন বা সাপোর্টে যোগাযোগ করুন।" : "Resubmit with a new transaction or contact support.")}</span>{canRetryPayment ? <button className="button button--ghost" type="button" onClick={() => { setActionError(""); setRetryOpen(true); }}>{bn ? "পেমেন্ট পুনরায় জমা" : "Resubmit payment"}</button> : null}</div> : null}

      <section className="account-detail-grid">
        <article className="account-panel">
          <div className="account-panel__header"><div><h2>{bn ? "অর্ডার সারাংশ" : "Order summary"}</h2><p>{bn ? "Locked quote snapshot অনুযায়ী মূল্য" : "Amounts from the locked quote snapshot"}</p></div><span className={`admin-status admin-status--${order.status.toLowerCase()}`}>{order.status.replaceAll("_", " ")}</span></div>
          <dl className="account-definition-list">
            <div><dt>{bn ? "মোট" : "Total"}</dt><dd>{formatBdt(order.total_bdt, intlLocale)}</dd></div>
            <div><dt>{bn ? "শিপিং" : "Shipping"}</dt><dd>{formatBdt(order.shipping_bdt, intlLocale)}</dd></div>
            <div><dt>{bn ? "অগ্রিম" : "Advance"}</dt><dd>{formatBdt(order.advance_bdt, intlLocale)}</dd></div>
            <div><dt>{bn ? "বাকি" : "Remaining"}</dt><dd>{formatBdt(order.remaining_bdt, intlLocale)}</dd></div>
            <div><dt>{bn ? "সেভড কোট" : "Saved quote"}</dt><dd>{order.saved_quote_id ? `#${order.saved_quote_id}` : "—"}</dd></div>
            <div><dt>{bn ? "ডেলিভারি" : "Delivery"}</dt><dd>{order.delivery_type || "—"}</dd></div>
          </dl>
        </article>

        <article className="account-panel">
          <div className="account-panel__header"><div><h2>{bn ? "পেমেন্ট" : "Payment"}</h2><p>{bn ? "ম্যানুয়াল পেমেন্ট যাচাই" : "Manual payment verification"}</p></div><span className={`admin-status admin-status--${paymentDecision.toLowerCase()}`}>{paymentDecision}</span></div>
          {order.manual_payment ? <dl className="account-definition-list">
            <div><dt>{bn ? "চ্যানেল" : "Channel"}</dt><dd>{order.manual_payment.channel}</dd></div>
            <div><dt>{bn ? "Transaction ID" : "Transaction ID"}</dt><dd>{order.manual_payment.trx_id}</dd></div>
            <div><dt>{bn ? "সিদ্ধান্তের সময়" : "Decision time"}</dt><dd>{formatDateTime(order.manual_payment.decided_at || order.manual_payment.verified_at, intlLocale)}</dd></div>
            <div><dt>{bn ? "প্রমাণ" : "Proof"}</dt><dd>{order.manual_payment.screenshot_url ? <a href={resolveImageUrl(order.manual_payment.screenshot_url) || "#"} target="_blank" rel="noreferrer">{bn ? "নতুন ট্যাবে দেখুন" : "Open in new tab"}</a> : "—"}</dd></div>
          </dl> : <div className="empty-state">{bn ? "কোনো পেমেন্ট প্রমাণ জমা হয়নি।" : "No payment proof has been submitted."}</div>}
        </article>
      </section>

      <section className="account-panel">
        <div className="account-panel__header"><div><h2>{bn ? "পেমেন্ট চেষ্টার ইতিহাস" : "Payment attempt history"}</h2><p>{bn ? "প্রতিটি submission এবং verifier decision append-only record হিসেবে রাখা হয়।" : "Every submission and verifier decision is retained as an append-only record."}</p></div>{canRetryPayment ? <button className="button button--primary" type="button" onClick={() => { setActionError(""); setRetryOpen(true); }}>{bn ? "নতুন প্রমাণ জমা" : "Submit new proof"}</button> : null}</div>
        {paymentAttempts.length ? <div className="account-attempt-list">{paymentAttempts.map(attempt => {
          const decision = attempt.decisions.at(-1);
          return <article key={attempt.id}>
            <div><strong>#{attempt.attempt_number} · {attempt.channel}</strong><span className={`admin-status admin-status--${(decision?.decision || "pending").toLowerCase()}`}>{decision?.decision || "PENDING"}</span></div>
            <dl className="account-definition-list">
              <div><dt>Transaction ID</dt><dd>{attempt.trx_id}</dd></div>
              <div><dt>{bn ? "জমার সময়" : "Submitted"}</dt><dd>{formatDateTime(attempt.created_at, intlLocale)}</dd></div>
              <div><dt>{bn ? "সিদ্ধান্তের কারণ" : "Decision reason"}</dt><dd>{decision?.reason || "—"}</dd></div>
              <div><dt>{bn ? "প্রমাণ" : "Proof"}</dt><dd>{attempt.screenshot_url ? <a href={resolveImageUrl(attempt.screenshot_url) || attempt.screenshot_url} target="_blank" rel="noreferrer">{bn ? "দেখুন" : "Open"}</a> : "—"}</dd></div>
            </dl>
            {attempt.decisions.length > 1 ? <div className="account-attempt-decisions">{attempt.decisions.map(item => <small key={item.id}>{item.decision} · {formatDateTime(item.created_at, intlLocale)}{item.reason ? ` · ${item.reason}` : ""}</small>)}</div> : null}
          </article>;
        })}</div> : <div className="empty-state">{bn ? "কোনো পেমেন্ট attempt record নেই।" : "No payment attempt records are available."}</div>}
      </section>

      <section className="account-panel">
        <div className="account-panel__header"><div><h2>{bn ? "অর্ডারের পণ্য" : "Order items"}</h2><p>{bn ? "অর্ডার তৈরির সময়ের snapshot" : "Snapshot captured when the order was created"}</p></div></div>
        {order.items?.length ? <div className="account-items-table" role="table">
          <div role="row" className="account-items-table__head"><span role="columnheader">{bn ? "পণ্য" : "Product"}</span><span role="columnheader">{bn ? "ভ্যারিয়েন্ট" : "Variant"}</span><span role="columnheader">{bn ? "পরিমাণ" : "Quantity"}</span></div>
          {order.items.map((item, index) => <div role="row" key={`${item.variant_id}-${index}`}><strong role="cell">{item.product_name || `Variant #${item.variant_id}`}</strong><span role="cell">{item.variant_name || "—"}</span><span role="cell">{new Intl.NumberFormat(intlLocale).format(item.qty)}</span></div>)}
        </div> : <div className="empty-state">{bn ? "কোনো item snapshot পাওয়া যায়নি।" : "No item snapshot is available."}</div>}
      </section>

      <section className="account-panel">
        <div className="account-panel__header"><div><h2>{bn ? "ডেলিভারি টাইমলাইন" : "Delivery timeline"}</h2><p>{order.shipment?.tracking_number ? `${bn ? "ট্র্যাকিং" : "Tracking"}: ${order.shipment.tracking_number}` : (bn ? "অপারেশন টিম আপডেট করলে এখানে দেখা যাবে।" : "Updates appear here as the operations team records them.")}</p></div></div>
        <ol className="account-timeline">
          {fulfilmentStages.map(stage => {
            const entries = order.history?.filter(entry => entry.status === stage) || [];
            const entry = entries.at(-1);
            const reached = Boolean(entry);
            return <li key={stage} className={reached ? "account-timeline__step account-timeline__step--reached" : "account-timeline__step"}><span aria-hidden /><div><strong>{stage.replaceAll("_", " ")}</strong><small>{entry ? formatDateTime(entry.created_at, intlLocale) : (bn ? "অপেক্ষমাণ" : "Pending")}</small>{entry?.note ? <p>{entry.note}</p> : null}</div></li>;
          })}
        </ol>
        {order.shipment?.events?.length ? <div className="account-shipment-events"><h3>{bn ? "শিপমেন্ট ইভেন্ট" : "Shipment events"}</h3>{order.shipment.events.map((event, index) => <div key={`${event.created_at}-${index}`}><strong>{event.status.replaceAll("_", " ")}</strong><span>{event.note || "—"}</span><small>{formatDateTime(event.created_at, intlLocale)}</small></div>)}</div> : null}
      </section>

      <AdminModal open={retryOpen} onClose={() => !saving && setRetryOpen(false)} title={bn ? "পেমেন্ট পুনরায় জমা দিন" : "Resubmit payment"} description={bn ? "আগের attempt পরিবর্তন হবে না; নতুন transaction আলাদা audit record হবে।" : "The previous attempt is not changed; this transaction becomes a new audit record."}>
        <form className="admin-modal__form" onSubmit={submitPaymentRetry}>
          <label><span>{bn ? "চ্যানেল" : "Channel"}</span><select value={retryFields.channel} onChange={event => setRetryFields(current => ({ ...current, channel: event.target.value as typeof retryFields.channel }))}>{["bKash", "Nagad", "Rocket", "Bank"].map(channel => <option key={channel} value={channel}>{channel}</option>)}</select></label>
          <label><span>Transaction ID</span><input required minLength={3} maxLength={80} autoComplete="off" value={retryFields.trx_id} onChange={event => setRetryFields(current => ({ ...current, trx_id: event.target.value }))} /></label>
          <label><span>{bn ? "Payment proof HTTPS URL (ঐচ্ছিক)" : "Payment proof HTTPS URL (optional)"}</span><input type="url" maxLength={500} pattern="https://.*" placeholder="https://…" value={retryFields.screenshot_url} onChange={event => setRetryFields(current => ({ ...current, screenshot_url: event.target.value }))} /><small>{bn ? "নিরাপত্তার জন্য কেবল valid HTTPS URL গ্রহণ করা হয়।" : "Only a valid HTTPS URL is accepted for security."}</small></label>
          {actionError ? <div className="admin-alert admin-alert--error">{actionError}</div> : null}
          <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setRetryOpen(false)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving}>{saving ? (bn ? "জমা হচ্ছে…" : "Submitting…") : (bn ? "যাচাইয়ের জন্য জমা দিন" : "Submit for verification")}</button></div>
        </form>
      </AdminModal>
      {toast ? <div className="admin-toast admin-toast--success" role="status">{toast}</div> : null}
    </div>
  );
}
