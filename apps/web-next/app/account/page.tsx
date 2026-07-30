"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getMyOrders, getSavedQuotes, type OrderSummary, type SavedQuote } from "../../lib/api";
import { formatBdt, formatDateTime } from "../../lib/format";
import { useLocale } from "../../lib/locale-context";

export default function AccountOverviewPage() {
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [quotes, setQuotes] = useState<SavedQuote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [orderRows, quoteRows] = await Promise.all([getMyOrders(), getSavedQuotes()]);
      setOrders(orderRows);
      setQuotes(quoteRows);
    } catch {
      setError(bn ? "অ্যাকাউন্টের তথ্য লোড করা যায়নি।" : "Your account data could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [bn]);

  useEffect(() => { void load(); }, [load]);

  const summary = useMemo(() => {
    const active = orders.filter(order => !["DELIVERED", "CANCELLED"].includes(order.status)).length;
    const awaitingPayment = orders.filter(order => {
      const decision = order.manual_payment?.decision || (order.manual_payment?.verified ? "APPROVED" : "PENDING");
      return decision === "PENDING" || decision === "REJECTED";
    }).length;
    const usableQuotes = quotes.filter(quote => !quote.expires_at || new Date(quote.expires_at).getTime() >= Date.now()).length;
    return { active, awaitingPayment, usableQuotes };
  }, [orders, quotes]);

  if (loading) return <div className="empty-state" aria-live="polite">{bn ? "অ্যাকাউন্ট লোড হচ্ছে…" : "Loading your account…"}</div>;

  if (error) {
    return <div className="empty-state" role="alert"><strong>{error}</strong><button className="button button--ghost" type="button" onClick={load}>{bn ? "আবার চেষ্টা করুন" : "Retry"}</button></div>;
  }

  return (
    <div className="account-overview">
      <header className="account-page-header">
        <div>
          <p className="eyebrow">{bn ? "অ্যাকাউন্ট ওভারভিউ" : "Account overview"}</p>
          <h1>{bn ? "আপনার সোর্সিং এক জায়গায়" : "Your sourcing in one place"}</h1>
          <p>{bn ? "অর্ডার, পেমেন্ট এবং সংরক্ষিত কোটের সর্বশেষ অবস্থা দেখুন।" : "Track the latest state of orders, payments and saved quotes."}</p>
        </div>
        <Link className="button button--primary" href="/products">{bn ? "নতুন পণ্য খুঁজুন" : "Source a product"}</Link>
      </header>

      <section className="account-stat-grid" aria-label={bn ? "অ্যাকাউন্ট সারাংশ" : "Account summary"}>
        <article><span>{bn ? "সক্রিয় অর্ডার" : "Active orders"}</span><strong>{new Intl.NumberFormat(intlLocale).format(summary.active)}</strong><Link href="/account/orders">{bn ? "অর্ডার দেখুন" : "View orders"} →</Link></article>
        <article><span>{bn ? "পেমেন্ট মনোযোগ প্রয়োজন" : "Payments needing attention"}</span><strong>{new Intl.NumberFormat(intlLocale).format(summary.awaitingPayment)}</strong><Link href="/account/orders?payment=attention">{bn ? "পর্যালোচনা করুন" : "Review"} →</Link></article>
        <article><span>{bn ? "সক্রিয় সেভড কোট" : "Active saved quotes"}</span><strong>{new Intl.NumberFormat(intlLocale).format(summary.usableQuotes)}</strong><Link href="/account/saved-quotes">{bn ? "তুলনা করুন" : "Compare quotes"} →</Link></article>
      </section>

      <section className="account-panel">
        <div className="account-panel__header"><div><h2>{bn ? "সাম্প্রতিক অর্ডার" : "Recent orders"}</h2><p>{bn ? "সর্বশেষ তিনটি অর্ডারের অবস্থা" : "Status of your three most recent orders"}</p></div><Link href="/account/orders">{bn ? "সব দেখুন" : "View all"} →</Link></div>
        {orders.length ? <div className="account-list">{orders.slice(0, 3).map(order => (
          <Link className="account-list__row" href={`/account/orders/${order.id}`} key={order.id}>
            <div><strong>{bn ? "অর্ডার" : "Order"} #{order.id}</strong><span>{formatDateTime(order.created_at, intlLocale)}</span></div>
            <span className={`admin-status admin-status--${order.status.toLowerCase()}`}>{order.status.replaceAll("_", " ")}</span>
            <strong>{formatBdt(order.total_bdt, intlLocale)}</strong>
          </Link>
        ))}</div> : <div className="empty-state"><strong>{bn ? "এখনও কোনো অর্ডার নেই।" : "No orders yet."}</strong><p>{bn ? "একটি কোট সংরক্ষণ করে অর্ডার শুরু করুন।" : "Save a quote to start an order."}</p></div>}
      </section>
    </div>
  );
}
