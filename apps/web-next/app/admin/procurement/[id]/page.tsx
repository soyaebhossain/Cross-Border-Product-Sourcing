"use client";

import Link from "next/link";
import type { Route } from "next";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AdminModal } from "../../../../components/admin-modal";
import {
  addGoodsReceipt,
  addSupplierPayment,
  getPurchaseOrder,
  PO_STATUS_LABELS,
  reverseSupplierPayment,
  setPurchaseOrderStatus,
  type PurchaseOrder,
  type PurchaseOrderStatus,
} from "../../../../lib/admin-erp-api";
import { formatAmount, formatBdt, formatDateTime } from "../../../../lib/format";
import { useLocale } from "../../../../lib/locale-context";
import { useAdminAccess } from "../../../../lib/use-admin-access";

type Dialog =
  | { kind: "status"; status: PurchaseOrderStatus }
  | { kind: "receipt" }
  | { kind: "payment" }
  | { kind: "reverse"; paymentId: number }
  | null;

const NEXT_STEP: Record<PurchaseOrderStatus, { en: string; bn: string }> = {
  DRAFT: { en: "Send this purchase order to the supplier.", bn: "এই purchase order সাপ্লায়ারকে পাঠান।" },
  SENT: { en: "Wait for the supplier to confirm, then mark it confirmed. The customer order then moves to Purchased.", bn: "সাপ্লায়ার নিশ্চিত করলে confirmed করুন। তখন customer order ‘Purchased’ হবে।" },
  CONFIRMED: { en: "Record goods as they arrive, with the quality-check result.", bn: "পণ্য এলে QC ফলাফলসহ গ্রহণ রেকর্ড করুন।" },
  RECEIVED: { en: "Pay the remaining balance, then close the purchase order.", bn: "বাকি পাওনা পরিশোধ করে purchase order বন্ধ করুন।" },
  CLOSED: { en: "This purchase order is complete.", bn: "এই purchase order সম্পন্ন হয়েছে।" },
  CANCELLED: { en: "This purchase order was cancelled.", bn: "এই purchase order বাতিল করা হয়েছে।" },
};

export default function PurchaseOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const { isAdmin } = useAdminAccess();
  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");

  const load = useCallback(async () => {
    try {
      setPo(await getPurchaseOrder(params.id));
      setLoadError("");
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : (bn ? "Purchase order লোড করা যায়নি।" : "The purchase order could not be loaded."));
    }
  }, [bn, params.id]);

  useEffect(() => { void load(); }, [load]);

  const open = (next: Dialog, initial: Record<string, string> = {}) => { setDialog(next); setFields(initial); setError(""); };
  const setField = (key: string, value: string) => setFields(current => ({ ...current, [key]: value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!po || !dialog) return;
    setSaving(true);
    setError("");
    try {
      let updated: PurchaseOrder;
      if (dialog.kind === "status") updated = await setPurchaseOrderStatus(po.id, dialog.status, fields.note || "");
      else if (dialog.kind === "receipt") updated = await addGoodsReceipt(po.id, { received_qty: Number(fields.received), accepted_qty: Number(fields.received) - Number(fields.rejected || 0), rejected_qty: Number(fields.rejected || 0), qc_note: fields.note || undefined });
      else if (dialog.kind === "payment") updated = await addSupplierPayment(po.id, { amount_origin: Number(fields.amount), method: fields.method || "Bank transfer", reference: fields.reference || undefined, note: fields.note || "" });
      else updated = await reverseSupplierPayment(dialog.paymentId, fields.note || "");
      setPo(updated);
      setDialog(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (bn ? "পরিবর্তন সংরক্ষণ করা যায়নি।" : "The change could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  if (loadError) return <div className="admin-page"><div className="admin-alert admin-alert--error" role="alert"><strong>{bn ? "লোড ব্যর্থ" : "Could not load"}</strong><span>{loadError}</span></div></div>;
  if (!po) return <div className="admin-auth-check" aria-live="polite"><span className="admin-spinner" aria-hidden />{bn ? "Purchase order লোড হচ্ছে…" : "Loading purchase order…"}</div>;

  const label = PO_STATUS_LABELS[po.status];
  const remainingUnits = po.ordered_qty - po.received_qty;
  const canPay = ["SENT", "CONFIRMED", "RECEIVED"].includes(po.status) && Number(po.outstanding_origin) > 0;
  const money = (value: string) => `${po.currency} ${formatAmount(value, intlLocale)}`;
  const statusButtonLabel = (status: PurchaseOrderStatus) => ({
    SENT: bn ? "সাপ্লায়ারকে পাঠানো হয়েছে" : "Mark sent to supplier",
    CONFIRMED: bn ? "সাপ্লায়ার নিশ্চিত করেছে" : "Mark supplier confirmed",
    CLOSED: bn ? "Purchase order বন্ধ করুন" : "Close purchase order",
    CANCELLED: bn ? "বাতিল করুন" : "Cancel",
    DRAFT: "", RECEIVED: "",
  }[status]);

  return <div className="admin-page">
    <header className="admin-page-header">
      <div>
        <p className="admin-eyebrow"><Link href={"/admin/procurement" as Route}>← {bn ? "সব purchase order" : "All purchase orders"}</Link></p>
        <h1>{po.po_number} <span className={`admin-status admin-status--${label.tone}`}>{bn ? label.bn : label.en}</span></h1>
        <p>{po.supplier.name} · {bn ? "Customer order" : "Customer order"} <Link href={`/admin/orders/${po.order_id}` as Route}>#{po.order_id}</Link>{po.order_status ? ` (${po.order_status})` : ""}</p>
      </div>
      <div className="admin-toolbar">
        {po.allowed_statuses.filter(status => status !== "CANCELLED").map(status => <button key={status} className="admin-button admin-button--primary" type="button" onClick={() => open({ kind: "status", status })}>{statusButtonLabel(status)}</button>)}
        {po.status === "CONFIRMED" && remainingUnits > 0 ? <button className="admin-button admin-button--primary" type="button" onClick={() => open({ kind: "receipt" }, { received: String(remainingUnits), rejected: "0" })}>{bn ? "পণ্য গ্রহণ রেকর্ড করুন" : "Record goods received"}</button> : null}
        {canPay ? <button className="admin-button admin-button--secondary" type="button" onClick={() => open({ kind: "payment" }, { amount: po.outstanding_origin, method: "Bank transfer" })}>{bn ? "সাপ্লায়ার পেমেন্ট রেকর্ড করুন" : "Record supplier payment"}</button> : null}
        {po.allowed_statuses.includes("CANCELLED") ? <button className="admin-button admin-button--danger" type="button" onClick={() => open({ kind: "status", status: "CANCELLED" })}>{statusButtonLabel("CANCELLED")}</button> : null}
      </div>
    </header>

    <div className="admin-ops-note"><strong>{bn ? "পরের ধাপ: " : "Next step: "}</strong>{bn ? NEXT_STEP[po.status].bn : NEXT_STEP[po.status].en}</div>

    <section className="admin-kpi-grid" aria-label={bn ? "Purchase order সারাংশ" : "Purchase order summary"}>
      <article className="admin-kpi"><div><span>{bn ? "মোট মূল্য" : "Order value"}</span></div><strong>{money(po.total_origin)}</strong><small>{formatBdt(po.total_bdt, intlLocale)} · 1 {po.currency} = ৳{formatAmount(po.fx_rate_to_bdt, intlLocale)}</small></article>
      <article className="admin-kpi"><div><span>{bn ? "পরিশোধিত" : "Paid"}</span></div><strong>{money(po.paid_origin)}</strong><small>{formatBdt(po.paid_bdt, intlLocale)}</small></article>
      <article className="admin-kpi"><div><span>{bn ? "বাকি পাওনা" : "Outstanding"}</span></div><strong>{money(po.outstanding_origin)}</strong><small>{formatBdt(po.outstanding_bdt, intlLocale)}</small></article>
      <article className="admin-kpi"><div><span>{bn ? "পণ্য গ্রহণ" : "Units received"}</span></div><strong>{po.received_qty} / {po.ordered_qty}</strong><small>{po.rejected_qty ? (bn ? `${po.rejected_qty}টি QC-তে বাতিল` : `${po.rejected_qty} rejected at quality check`) : (bn ? "কোনো পণ্য বাতিল হয়নি" : "No units rejected")}</small></article>
    </section>

    <section className="admin-card admin-list-card admin-ops-section">
      <div className="admin-list-toolbar"><strong>{bn ? "পণ্যের তালিকা" : "Line items"}</strong></div>
      <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr><th>{bn ? "পণ্য" : "Product"}</th><th>{bn ? "পরিমাণ" : "Qty"}</th><th>{bn ? "একক মূল্য" : "Unit cost"}</th><th>{bn ? "মোট" : "Line total"}</th></tr></thead>
        <tbody>{(po.items || []).map(item => <tr key={item.id}><td><div className="admin-primary-cell"><strong>{item.product_name}</strong><small>{item.variant_name}</small></div></td><td>{item.qty}</td><td>{money(item.unit_cost_origin)}</td><td>{money(item.line_total_origin)}</td></tr>)}</tbody>
      </table></div>
    </section>

    <section className="admin-card admin-list-card admin-ops-section">
      <div className="admin-list-toolbar"><strong>{bn ? "পণ্য গ্রহণ ও QC" : "Goods receipts and quality checks"}</strong></div>
      {(po.receipts || []).length ? <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr><th>{bn ? "তারিখ" : "Date"}</th><th>{bn ? "গ্রহণ" : "Received"}</th><th>{bn ? "গৃহীত" : "Accepted"}</th><th>{bn ? "বাতিল" : "Rejected"}</th><th>{bn ? "QC নোট" : "QC note"}</th></tr></thead>
        <tbody>{(po.receipts || []).map(receipt => <tr key={receipt.id}><td>{formatDateTime(receipt.received_at, intlLocale)}</td><td>{receipt.received_qty}</td><td>{receipt.accepted_qty}</td><td>{receipt.rejected_qty}</td><td>{receipt.qc_note || "—"}</td></tr>)}</tbody>
      </table></div> : <div className="admin-empty"><strong>{bn ? "এখনো কোনো পণ্য গ্রহণ হয়নি" : "Nothing received yet"}</strong></div>}
    </section>

    <section className="admin-card admin-list-card admin-ops-section">
      <div className="admin-list-toolbar"><strong>{bn ? "সাপ্লায়ার পেমেন্ট" : "Supplier payments"}</strong></div>
      {(po.payments || []).length ? <div className="admin-table-wrap"><table className="admin-data-table">
        <thead><tr><th>{bn ? "তারিখ" : "Date"}</th><th>{bn ? "পরিমাণ" : "Amount"}</th><th>BDT</th><th>{bn ? "পদ্ধতি" : "Method"}</th><th>{bn ? "রেফারেন্স" : "Reference"}</th><th>{bn ? "অবস্থা" : "Status"}</th><th><span className="sr-only">{bn ? "অ্যাকশন" : "Actions"}</span></th></tr></thead>
        <tbody>{(po.payments || []).map(payment => <tr key={payment.id}>
          <td>{formatDateTime(payment.paid_at, intlLocale)}</td><td>{money(payment.amount_origin)}</td><td>{formatBdt(payment.amount_bdt, intlLocale)}</td><td>{payment.method}</td><td>{payment.reference || "—"}</td>
          <td><span className={`admin-status admin-status--${payment.status === "POSTED" ? "approved" : "cancelled"}`}>{payment.status === "POSTED" ? (bn ? "পোস্ট হয়েছে" : "Posted") : (bn ? "ফেরত নেওয়া" : "Reversed")}</span>{payment.reversal_reason ? <small> {payment.reversal_reason}</small> : null}</td>
          <td className="admin-actions-cell">{isAdmin && payment.status === "POSTED" && po.status !== "CLOSED" ? <button className="admin-row-button admin-row-button--danger" type="button" onClick={() => open({ kind: "reverse", paymentId: payment.id })}>{bn ? "ফেরত নিন" : "Reverse"}</button> : null}</td>
        </tr>)}</tbody>
      </table></div> : <div className="admin-empty"><strong>{bn ? "এখনো কোনো পেমেন্ট নেই" : "No payments recorded yet"}</strong></div>}
    </section>

    <AdminModal
      open={dialog !== null}
      onClose={() => !saving && setDialog(null)}
      title={dialog?.kind === "receipt" ? (bn ? "পণ্য গ্রহণ রেকর্ড করুন" : "Record goods received") : dialog?.kind === "payment" ? (bn ? "সাপ্লায়ার পেমেন্ট রেকর্ড করুন" : "Record supplier payment") : dialog?.kind === "reverse" ? (bn ? "পেমেন্ট ফেরত নেবেন?" : "Reverse this payment?") : dialog?.kind === "status" ? statusButtonLabel(dialog.status) : ""}
      description={bn ? "প্রতিটি পরিবর্তন audit log-এ আপনার নামসহ থাকবে।" : "Every change is written to the audit log under your name."}
    >
      <form className="admin-modal__form" onSubmit={submit}>
        {dialog?.kind === "receipt" ? <>
          <label><span>{bn ? `গ্রহণ করা পরিমাণ (বাকি ${remainingUnits})` : `Units received (${remainingUnits} still expected)`}</span><input type="number" min="1" max={remainingUnits} required value={fields.received || ""} onChange={event => setField("received", event.target.value)} /></label>
          <label><span>{bn ? "QC-তে বাতিল পরিমাণ" : "Units rejected at quality check"}</span><input type="number" min="0" max={fields.received || remainingUnits} required value={fields.rejected || "0"} onChange={event => setField("rejected", event.target.value)} /></label>
        </> : null}
        {dialog?.kind === "payment" ? <>
          <label><span>{bn ? `পরিমাণ (${po.currency}), বাকি ${po.outstanding_origin}` : `Amount (${po.currency}), ${po.outstanding_origin} outstanding`}</span><input type="number" min="0.01" max={po.outstanding_origin} step="0.01" required value={fields.amount || ""} onChange={event => setField("amount", event.target.value)} /></label>
          <label><span>{bn ? "পদ্ধতি" : "Method"}</span><select value={fields.method || "Bank transfer"} onChange={event => setField("method", event.target.value)}><option>Bank transfer</option><option>Letter of credit</option><option>Alipay</option><option>PayPal</option><option>Other</option></select></label>
          <label><span>{bn ? "ব্যাংক বা লেনদেন রেফারেন্স" : "Bank or transaction reference"}</span><input maxLength={120} value={fields.reference || ""} onChange={event => setField("reference", event.target.value)} /></label>
        </> : null}
        <label><span>{dialog?.kind === "receipt" ? (bn ? "QC নোট (বাতিল থাকলে আবশ্যিক)" : "QC note (required when units are rejected)") : dialog?.kind === "reverse" ? (bn ? "ফেরত নেওয়ার কারণ (আবশ্যিক)" : "Reason for reversal (required)") : (bn ? "নোট (আবশ্যিক)" : "Note (required)")}</span><textarea minLength={dialog?.kind === "receipt" ? 0 : 3} maxLength={1000} rows={3} required={dialog?.kind !== "receipt" || Number(fields.rejected || 0) > 0} value={fields.note || ""} onChange={event => setField("note", event.target.value)} /></label>
        {error ? <div className="admin-alert admin-alert--error" role="alert">{error}</div> : null}
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setDialog(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className={`admin-button ${dialog?.kind === "reverse" || (dialog?.kind === "status" && dialog.status === "CANCELLED") ? "admin-button--danger" : "admin-button--primary"}`} disabled={saving}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "নিশ্চিত করুন" : "Confirm")}</button></div>
      </form>
    </AdminModal>
  </div>;
}
