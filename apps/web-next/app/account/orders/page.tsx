"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getMyOrders, type OrderSummary } from "../../../lib/api";
import { formatBdt, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

const statuses = ["", "PENDING", "CONFIRMED", "PURCHASED", "IN_TRANSIT", "CUSTOMS", "LOCAL_DISPATCH", "DELIVERED", "CANCELLED"];

export default function OrdersPage() {
  const searchParams = useSearchParams();
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const paymentAttention = searchParams.get("payment") === "attention";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOrders(await getMyOrders());
    } catch {
      setError(bn ? "আপনার অর্ডার লোড করা যায়নি।" : "Your orders could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [bn]);

  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => orders.filter(order => {
    const paymentDecision = order.manual_payment?.decision || (order.manual_payment?.verified ? "APPROVED" : "PENDING");
    if (paymentAttention && !["PENDING", "REJECTED"].includes(paymentDecision)) return false;
    if (status && order.status !== status) return false;
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return true;
    return [order.id, order.status, order.country_id, order.mode, order.manual_payment?.trx_id].some(value => String(value || "").toLocaleLowerCase().includes(needle));
  }), [orders, paymentAttention, query, status]);

  return (
    <div className="account-page">
      <header className="account-page-header">
        <div><p className="eyebrow">{bn ? "অর্ডার ট্র্যাকিং" : "Order tracking"}</p><h1>{bn ? "আমার অর্ডার" : "My orders"}</h1><p>{bn ? "স্ট্যাটাস, পেমেন্ট ও ডেলিভারির অগ্রগতি দেখুন।" : "Review status, payment and delivery progress."}</p></div>
        <Link className="button button--primary" href="/account/saved-quotes">{bn ? "সেভড কোট থেকে অর্ডার" : "Order from a saved quote"}</Link>
      </header>

      <form className="account-filter-bar" onSubmit={event => event.preventDefault()}>
        <label><span className="sr-only">{bn ? "অর্ডার খুঁজুন" : "Search orders"}</span><input className="input-field" value={query} onChange={event => setQuery(event.target.value)} placeholder={bn ? "অর্ডার, রুট বা transaction ID" : "Order, route or transaction ID"} /></label>
        <label><span className="sr-only">{bn ? "স্ট্যাটাস" : "Status"}</span><select className="input-field" value={status} onChange={event => setStatus(event.target.value)}>{statuses.map(value => <option value={value} key={value}>{value ? value.replaceAll("_", " ") : (bn ? "সব স্ট্যাটাস" : "All statuses")}</option>)}</select></label>
        {paymentAttention ? <Link className="nav-pill nav-pill--active" href="/account/orders">{bn ? "পেমেন্ট ফিল্টার সরান ×" : "Clear payment filter ×"}</Link> : null}
        <button className="button button--ghost" type="button" onClick={load} disabled={loading}>{bn ? "রিফ্রেশ" : "Refresh"}</button>
      </form>

      {loading ? <div className="empty-state" aria-live="polite">{bn ? "অর্ডার লোড হচ্ছে…" : "Loading your orders…"}</div>
        : error ? <div className="empty-state" role="alert"><strong>{error}</strong><button className="button button--ghost" type="button" onClick={load}>{bn ? "আবার চেষ্টা করুন" : "Retry"}</button></div>
        : !filtered.length ? <div className="empty-state"><strong>{orders.length ? (bn ? "এই ফিল্টারে কোনো অর্ডার নেই।" : "No orders match these filters.") : (bn ? "এখনও কোনো অর্ডার নেই।" : "No orders yet.")}</strong><p>{bn ? "একটি কোট সংরক্ষণ করে অর্ডার করুন।" : "Save a quote and place an order to see it here."}</p></div>
        : <div className="account-order-list">{filtered.map(order => {
          const decision = order.manual_payment?.decision || (order.manual_payment?.verified ? "APPROVED" : "PENDING");
          return <article key={order.id} className="account-order-card">
            <div className="account-order-card__top">
              <div><small>{formatDateTime(order.created_at, intlLocale)}</small><h2>{bn ? "অর্ডার" : "Order"} #{order.id}</h2><p>{order.country_id || "—"} · {order.mode || "—"} · {order.delivery_type || "—"}</p></div>
              <strong>{formatBdt(order.total_bdt, intlLocale)}</strong>
            </div>
            <div className="account-order-card__status">
              <span className={`admin-status admin-status--${order.status.toLowerCase()}`}>{order.status.replaceAll("_", " ")}</span>
              <span className={`admin-status admin-status--${decision.toLowerCase()}`}>{bn ? "পেমেন্ট" : "Payment"}: {decision}</span>
            </div>
            <dl><div><dt>{bn ? "অগ্রিম" : "Advance"}</dt><dd>{formatBdt(order.advance_bdt, intlLocale)}</dd></div><div><dt>{bn ? "বাকি" : "Remaining"}</dt><dd>{formatBdt(order.remaining_bdt, intlLocale)}</dd></div></dl>
            <Link className="button button--ghost" href={`/account/orders/${order.id}`}>{bn ? "বিস্তারিত ও ট্র্যাকিং" : "Details and tracking"} →</Link>
          </article>;
        })}</div>}
    </div>
  );
}
