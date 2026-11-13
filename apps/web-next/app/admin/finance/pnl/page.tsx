"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useState } from "react";
import { getOrderPnl, type OrderPnl } from "../../../../lib/admin-erp-api";
import { formatBdt, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";

export default function OrderProfitAndLossPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const [rows, setRows] = useState<OrderPnl[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    getOrderPnl(page)
      .then(result => { setRows(result.items); setPages(result.pages || 1); setTotal(result.total); setError(""); })
      .catch(reason => setError(reason instanceof Error ? reason.message : "The report could not be loaded."))
      .finally(() => setLoading(false));
  }, [page]);

  const margin = (value: string | null) => {
    if (value === null) return <span>—</span>;
    return <strong className={Number(value) < 0 ? "admin-negative" : "admin-positive"}>{formatBdt(value, intlLocale)}</strong>;
  };

  return <div className="admin-page">
    <header className="admin-page-header">
      <div><p className="admin-eyebrow">{bn ? "ফাইন্যান্স" : "Finance"}</p><h1>{bn ? "Order-প্রতি লাভ-ক্ষতি" : "Order profit and loss"}</h1><p>{bn ? "প্রতিটি order-এর আয়, সাপ্লায়ারের খরচ ও margin। কোন সংখ্যা আসল আর কোনটা quote থেকে নেওয়া তা আলাদা করে দেখানো।" : "Revenue, supplier cost and margin per order, with actual figures kept separate from quoted ones."}</p></div>
      <div className="admin-toolbar"><button className="admin-button admin-button--secondary" type="button" onClick={() => window.print()}>{bn ? "প্রিন্ট / PDF" : "Print / PDF"}</button></div>
    </header>

    <div className="admin-ops-note">
      {bn
        ? "আনুমানিক margin = আয় − সাপ্লায়ারের খরচ − quote-এর শিপিং − quote-এর শুল্ক ও VAT। Purchase order থাকলে সাপ্লায়ারের খরচ সেখান থেকে আসে, না থাকলে quote থেকে। চূড়ান্ত margin শুধু তখনই দেখায় যখন order-এ আসল মোট খরচ বসানো হয়েছে।"
        : "Estimated margin = revenue − supplier cost − quoted shipping − quoted duty and VAT. Supplier cost comes from the purchase order when one exists, otherwise from the quote. Realized margin appears only once the actual total cost has been entered on the order."}
    </div>

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Could not load"}</strong><span>{error}</span></div> : null}

    <section className="admin-card admin-list-card admin-ops-section">
      <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr><th>{bn ? "Order" : "Order"}</th><th>{bn ? "আয়" : "Revenue"}</th><th>{bn ? "গ্রাহক থেকে পাওয়া" : "Cash collected"}</th><th>{bn ? "সাপ্লায়ারের খরচ" : "Supplier cost"}</th><th>{bn ? "সাপ্লায়ারকে দেওয়া" : "Paid to supplier"}</th><th>{bn ? "শিপিং + শুল্ক (quote)" : "Shipping + duty (quoted)"}</th><th>{bn ? "আনুমানিক margin" : "Estimated margin"}</th><th>{bn ? "চূড়ান্ত margin" : "Realized margin"}</th></tr></thead>
        <tbody>{rows.map(row => <tr key={row.order_id}>
          <td><div className="admin-primary-cell"><Link href={`/admin/orders/${row.order_id}` as Route}><strong>#{row.order_id}</strong></Link><small>{row.status} · {formatDateTime(row.created_at, intlLocale)}</small></div></td>
          <td>{formatBdt(row.revenue_bdt, intlLocale)}</td>
          <td>{formatBdt(row.net_verified_cash_bdt, intlLocale)}</td>
          <td><div className="admin-primary-cell"><strong>{formatBdt(row.supplier_cost_bdt, intlLocale)}</strong><small>{row.supplier_cost_basis === "purchase_order" ? row.purchase_orders.join(", ") : (bn ? "quote থেকে, PO নেই" : "from quote, no PO yet")}</small></div></td>
          <td>{formatBdt(row.supplier_paid_bdt, intlLocale)}</td>
          <td>{formatBdt(Number(row.quoted_shipping_bdt) + Number(row.quoted_duty_vat_bdt), intlLocale)}</td>
          <td>{margin(row.estimated_margin_bdt)}</td>
          <td>{margin(row.realized_margin_bdt)}</td>
        </tr>)}</tbody>
      </table></div>
      {!rows.length && !loading ? <div className="admin-empty"><strong>{bn ? "এখনো কোনো নিশ্চিত order নেই" : "No confirmed orders yet"}</strong><span>{bn ? "Payment অনুমোদিত হয়ে order নিশ্চিত হলে এখানে দেখাবে।" : "Orders appear here once their payment is approved."}</span></div> : null}
      <footer className="admin-pagination"><span>{total} {bn ? "টি order" : "orders"}</span><div><button type="button" disabled={page <= 1} onClick={() => setPage(current => Math.max(1, current - 1))}>{bn ? "আগের" : "Previous"}</button><span>{bn ? "পৃষ্ঠা" : "Page"} {page} / {pages}</span><button type="button" disabled={page >= pages} onClick={() => setPage(current => current + 1)}>{bn ? "পরের" : "Next"}</button></div></footer>
    </section>
  </div>;
}
