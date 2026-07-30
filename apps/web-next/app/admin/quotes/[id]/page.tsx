"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { getAdminQuoteDetail, type AdminQuoteDetail } from "../../../../lib/admin-api";
import { formatCurrency, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

export default function AdminQuoteDetailPage() {
  const params = useParams<{ id: string }>();
  const [quote, setQuote] = useState<AdminQuoteDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const load = useCallback(async () => { setLoading(true); setError(""); try { setQuote(await getAdminQuoteDetail(params.id)); } catch (reason) { setError(reason instanceof Error ? reason.message : "Quote could not be loaded."); } finally { setLoading(false); } }, [params.id]);
  useEffect(() => { void load(); }, [load]);
  if (loading) return <div className="admin-auth-check"><span className="admin-spinner" />{bn ? "কোট লোড হচ্ছে…" : "Loading quote…"}</div>;
  if (!quote) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert">{error || "Quote not found."}</div></div>;
  const breakdown = quote.snapshot?.breakdown;
  return <div className="admin-page">
    <header className="admin-page-header"><div><Link className="account-back-link" href="/admin/quotes">← {bn ? "কোট তালিকা" : "Quote list"}</Link><p className="admin-eyebrow">{bn ? "Locked quote snapshot" : "Locked quote snapshot"}</p><h1>{bn ? "সেভড কোট" : "Saved quote"} #{quote.id}</h1><p>{formatDateTime(quote.created_at, intlLocale)} · {quote.country} · {quote.mode}</p></div><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></header>
    <section className="admin-detail-grid"><article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "কোট" : "Quote"}</h2><p>{bn ? "Customer ও lifecycle" : "Customer and lifecycle"}</p></div><span className={`admin-status admin-status--${quote.status.toLowerCase()}`}>{quote.status}</span></div><dl className="account-definition-list">
      <div><dt>{bn ? "Customer" : "Customer"}</dt><dd><Link href={`/admin/users/${quote.customer.id}`}>{quote.customer.username || quote.customer.email || `User #${quote.customer.id}`}</Link></dd></div><div><dt>{bn ? "পণ্য" : "Product"}</dt><dd>{quote.product_name}</dd></div><div><dt>{bn ? "ভ্যারিয়েন্ট" : "Variant"}</dt><dd>{quote.variant_name || `#${quote.variant_id}`}</dd></div><div><dt>{bn ? "পরিমাণ" : "Quantity"}</dt><dd>{quote.qty}</dd></div><div><dt>{bn ? "Delivery" : "Delivery"}</dt><dd>{quote.delivery_type}</dd></div><div><dt>{bn ? "Expiry" : "Expiry"}</dt><dd>{formatDateTime(quote.expires_at, intlLocale)}</dd></div>
    </dl></article><article className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "Price snapshot" : "Price snapshot"}</h2><p>{bn ? "Checkout recalculation নয়" : "Not recalculated at checkout"}</p></div></div><dl className="account-definition-list">
      <div><dt>{bn ? "Product cost" : "Product cost"}</dt><dd>{formatCurrency(breakdown?.product_cost_bdt || breakdown?.origin_price_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Shipping" : "Shipping"}</dt><dd>{formatCurrency(breakdown?.shipping_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Duty + VAT" : "Duty + VAT"}</dt><dd>{formatCurrency(breakdown?.duty_vat_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "Service fee" : "Service fee"}</dt><dd>{formatCurrency(breakdown?.service_fee_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "মোট" : "Total"}</dt><dd>{formatCurrency(breakdown?.total_bdt, "BDT", intlLocale)}</dd></div><div><dt>{bn ? "অগ্রিম" : "Advance"}</dt><dd>{formatCurrency(breakdown?.advance_bdt, "BDT", intlLocale)}</dd></div>
    </dl></article></section>
    <section className="admin-card"><div className="admin-card__header"><div><h2>{bn ? "Linked orders" : "Linked orders"}</h2><p>{bn ? "Duplicate-order integrity" : "Duplicate-order integrity"}</p></div></div>{quote.order_ids.length ? <div className="admin-inline-actions">{quote.order_ids.map(id => <Link className="admin-button admin-button--secondary" href={`/admin/orders/${id}`} key={id}>{bn ? "অর্ডার" : "Order"} #{id}</Link>)}</div> : <div className="admin-empty">{bn ? "এই কোট থেকে অর্ডার হয়নি।" : "No order has been created from this quote."}</div>}</section>
  </div>;
}
