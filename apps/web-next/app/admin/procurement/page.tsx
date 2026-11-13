"use client";

import Link from "next/link";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { createPurchaseOrder, getErpSummary, listPurchaseOrders, PO_STATUS_LABELS, type ErpSummary, type PurchaseOrder } from "../../../lib/admin-erp-api";
import { formatAmount, formatBdt, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

export default function AdminProcurementPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const router = useRouter();
  const [rows, setRows] = useState<PurchaseOrder[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [summary, setSummary] = useState<ErpSummary | null>(null);
  const [orderNumber, setOrderNumber] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, nextSummary] = await Promise.all([listPurchaseOrders({ q, status, page }), getErpSummary().catch(() => null)]);
      setRows(list.items);
      setTotal(list.total);
      setPages(list.pages || 1);
      setSummary(nextSummary);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "Purchase order লোড করা যায়নি।" : "Purchase orders could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [bn, page, q, status]);

  useEffect(() => { void load(); }, [load]);

  const raise = async (event: React.FormEvent) => {
    event.preventDefault();
    const orderId = Number(orderNumber);
    if (!Number.isInteger(orderId) || orderId < 1) return;
    setCreating(true);
    setError("");
    try {
      const created = await createPurchaseOrder(orderId);
      router.push(`/admin/procurement/${created.id}` as Route);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "Purchase order তৈরি করা যায়নি।" : "The purchase order could not be created."));
      setCreating(false);
    }
  };

  const number = (value: number) => new Intl.NumberFormat(intlLocale).format(value);
  return <div className="admin-page">
    <header className="admin-page-header">
      <div><p className="admin-eyebrow">{bn ? "প্রকিউরমেন্ট" : "Procurement"}</p><h1>{bn ? "সাপ্লায়ার purchase order" : "Supplier purchase orders"}</h1><p>{bn ? "নিশ্চিত হওয়া customer order-এর জন্য সাপ্লায়ারের কাছে order দিন, পণ্য গ্রহণ ও QC রেকর্ড করুন।" : "Place orders with suppliers for confirmed customer orders, then record goods received and quality checks."}</p></div>
      <form className="admin-toolbar" onSubmit={raise}>
        <label className="admin-filter"><span>{bn ? "Customer order নম্বর" : "Customer order no."}</span><input type="number" min="1" required value={orderNumber} onChange={event => setOrderNumber(event.target.value)} placeholder="#" /></label>
        <button className="admin-button admin-button--primary" disabled={creating}>{creating ? (bn ? "তৈরি হচ্ছে…" : "Creating…") : (bn ? "Purchase order তৈরি করুন" : "Raise purchase order")}</button>
      </form>
    </header>

    {summary ? <section className="admin-kpi-grid" aria-label={bn ? "প্রকিউরমেন্ট সারাংশ" : "Procurement summary"}>
      <article className="admin-kpi"><div><span>{bn ? "PO-র অপেক্ষায় order" : "Orders awaiting a PO"}</span></div><strong>{number(summary.orders_awaiting_purchase)}</strong><small><Link href={"/admin/orders" as Route}>{bn ? "নিশ্চিত order দেখুন" : "View confirmed orders"}</Link></small></article>
      <article className="admin-kpi"><div><span>{bn ? "খোলা purchase order" : "Open purchase orders"}</span></div><strong>{number(summary.open_purchase_orders)}</strong><small>{bn ? `পাঠানো ${number(summary.purchase_orders.SENT)} · নিশ্চিত ${number(summary.purchase_orders.CONFIRMED)}` : `${number(summary.purchase_orders.SENT)} sent · ${number(summary.purchase_orders.CONFIRMED)} confirmed`}</small></article>
      <article className="admin-kpi"><div><span>{bn ? "পণ্য গ্রহণ হয়েছে, বন্ধ হয়নি" : "Received, not closed"}</span></div><strong>{number(summary.purchase_orders.RECEIVED)}</strong><small>{bn ? "পাওনা মিটিয়ে বন্ধ করুন" : "Settle the payable to close"}</small></article>
      <article className="admin-kpi"><div><span>{bn ? "সাপ্লায়ারের পাওনা" : "Owed to suppliers"}</span></div><strong>{formatBdt(summary.payables_outstanding_bdt, intlLocale)}</strong><small><Link href={"/admin/finance/payables" as Route}>{bn ? "পাওনার তালিকা" : "Open payables"}</Link></small></article>
    </section> : null}

    {error ? <div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "অপারেশন ব্যর্থ" : "Operation failed"}</strong><span>{error}</span></div> : null}

    <section className="admin-card admin-list-card">
      <div className="admin-list-toolbar">
        <label className="admin-search"><span className="sr-only">{bn ? "খুঁজুন" : "Search"}</span><input value={q} onChange={event => { setQ(event.target.value); setPage(1); }} placeholder={bn ? "PO নম্বর, সাপ্লায়ার বা order নম্বর" : "PO number, supplier or order number"} /></label>
        <label className="admin-filter"><span>{bn ? "অবস্থা" : "Status"}</span><select value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}><option value="">{bn ? "সব" : "All"}</option>{Object.entries(PO_STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{bn ? label.bn : label.en}</option>)}</select></label>
      </div>
      <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr><th>{bn ? "PO" : "PO"}</th><th>{bn ? "সাপ্লায়ার" : "Supplier"}</th><th>{bn ? "Customer order" : "Customer order"}</th><th>{bn ? "অবস্থা" : "Status"}</th><th>{bn ? "মোট" : "Total"}</th><th>{bn ? "বাকি পাওনা" : "Outstanding"}</th><th>{bn ? "গ্রহণ" : "Received"}</th><th>{bn ? "তৈরি" : "Raised"}</th></tr></thead>
        <tbody>{rows.map(row => {
          const label = PO_STATUS_LABELS[row.status];
          return <tr key={row.id}>
            <td><Link className="admin-primary-cell" href={`/admin/procurement/${row.id}` as Route}><strong>{row.po_number}</strong></Link></td>
            <td>{row.supplier.name}</td>
            <td><Link href={`/admin/orders/${row.order_id}` as Route}>#{row.order_id}</Link></td>
            <td><span className={`admin-status admin-status--${label.tone}`}>{bn ? label.bn : label.en}</span></td>
            <td>{row.currency} {formatAmount(row.total_origin, intlLocale)}</td>
            <td>{row.currency} {formatAmount(row.outstanding_origin, intlLocale)}</td>
            <td>{number(row.received_qty)} / {number(row.ordered_qty)}</td>
            <td>{formatDateTime(row.created_at, intlLocale)}</td>
          </tr>;
        })}</tbody>
      </table></div>
      {!rows.length && !loading ? <div className="admin-empty"><strong>{bn ? "কোনো purchase order নেই" : "No purchase orders yet"}</strong><span>{bn ? "উপরে একটি নিশ্চিত customer order-এর নম্বর দিয়ে প্রথম purchase order তৈরি করুন।" : "Enter the number of a confirmed customer order above to raise the first one."}</span></div> : null}
      <footer className="admin-pagination"><span>{number(total)} {bn ? "রেকর্ড" : "records"}</span><div><button type="button" disabled={page <= 1} onClick={() => setPage(current => Math.max(1, current - 1))}>{bn ? "আগের" : "Previous"}</button><span>{bn ? "পৃষ্ঠা" : "Page"} {page} / {pages}</span><button type="button" disabled={page >= pages} onClick={() => setPage(current => current + 1)}>{bn ? "পরের" : "Next"}</button></div></footer>
    </section>
  </div>;
}
