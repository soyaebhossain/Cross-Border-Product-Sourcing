"use client";

import { useState } from "react";
import { AdminDataPage, type AdminColumn } from "../../../components/admin-data-page";
import { AdminModal } from "../../../components/admin-modal";
import { decideOrderPayment, resolveImageUrl, type AdminPaymentRow } from "../../../lib/api";
import { formatCurrency, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

function customerLabel(row: AdminPaymentRow) {
  if (typeof row.customer === "string") return row.customer;
  return row.customer?.username || row.customer?.email || row.customer?.phone || (row.user_id ? `User #${row.user_id}` : row.trx_id);
}

function PaymentActions({ row, reload, notify }: { row: AdminPaymentRow; reload: () => Promise<void>; notify: (message: string, kind?: "success" | "error") => void }) {
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const { locale } = useLocale();
  const bn = locale === "bn";
  const pending = !row.verified && !["APPROVED", "REJECTED", "VERIFIED", "REVERSED"].includes((row.decision || row.status || "").toUpperCase());

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!decision) return;
    setSaving(true);
    try {
      await decideOrderPayment(row.order_id, decision, reason);
      notify(decision === "approve" ? (bn ? `অর্ডার #${row.order_id}-এর পেমেন্ট approve হয়েছে।` : `Payment for order #${row.order_id} was approved.`) : (bn ? `অর্ডার #${row.order_id}-এর পেমেন্ট reject হয়েছে।` : `Payment for order #${row.order_id} was rejected.`));
      setDecision(null);
      setReason("");
      await reload();
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : (bn ? "Payment decision সংরক্ষণ করা যায়নি।" : "The payment decision could not be saved."), "error");
    } finally {
      setSaving(false);
    }
  };

  return <div className="admin-inline-actions">
    {row.screenshot_url ? <a className="admin-row-button" href={resolveImageUrl(row.screenshot_url) || "#"} target="_blank" rel="noreferrer">{bn ? "প্রমাণ" : "Proof"}</a> : null}
    {pending ? <><button className="admin-row-button admin-row-button--approve" type="button" onClick={() => setDecision("approve")}>{bn ? "অনুমোদন" : "Approve"}</button><button className="admin-row-button admin-row-button--danger" type="button" onClick={() => setDecision("reject")}>{bn ? "প্রত্যাখ্যান" : "Reject"}</button></> : null}
    <AdminModal open={decision !== null} onClose={() => !saving && setDecision(null)} title={decision === "approve" ? (bn ? "পেমেন্ট অনুমোদন করবেন?" : "Approve this payment?") : (bn ? "পেমেন্ট প্রত্যাখ্যান করবেন?" : "Reject this payment?")} description={`${bn ? "অর্ডার" : "Order"} #${row.order_id} · ${row.channel} · ${row.trx_id}`}>
      <form className="admin-modal__form" onSubmit={submit}>
        <div className={`admin-decision-summary admin-decision-summary--${decision}`}><strong>{formatCurrency(row.advance_bdt)}</strong><span>{decision === "approve" ? (bn ? "অর্ডারটি payment-confirmed হবে।" : "The order will be marked payment-confirmed.") : (bn ? "Customer-কে কারণ জানানো যাবে।" : "The reason can be shown to the customer.")}</span></div>
        <label><span>{decision === "reject" ? (bn ? "প্রত্যাখ্যানের কারণ (আবশ্যিক)" : "Rejection reason (required)") : (bn ? "যাচাই নোট (আবশ্যিক)" : "Verification note (required)")}</span><textarea rows={3} value={reason} required minLength={3} maxLength={1000} onChange={event => setReason(event.target.value)} /></label>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setDecision(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className={`admin-button ${decision === "reject" ? "admin-button--danger" : "admin-button--primary"}`} type="submit" disabled={saving || reason.trim().length < 3}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "নিশ্চিত করুন" : "Confirm decision")}</button></div>
      </form>
    </AdminModal>
  </div>;
}

export default function AdminPaymentsPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const columns: AdminColumn<AdminPaymentRow>[] = [
    { key: "order", label: bn ? "অর্ডার" : "Order", cell: row => <div className="admin-primary-cell"><strong>#{row.order_id}</strong><small>{customerLabel(row)}</small></div>, exportValue: row => row.order_id, sortValue: row => row.order_id },
    { key: "submitted", label: bn ? "জমা হয়েছে" : "Submitted", cell: row => formatDateTime(row.submitted_at || row.created_at, intlLocale), exportValue: row => row.submitted_at || row.created_at, sortValue: row => row.submitted_at || row.created_at },
    { key: "channel", label: bn ? "চ্যানেল" : "Channel", cell: row => <div className="admin-primary-cell"><strong>{row.channel}</strong><small>Trx {row.trx_id}</small></div>, exportValue: row => `${row.channel} ${row.trx_id}`, sortValue: row => row.channel },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => { const status = row.decision || row.status || (row.verified ? "APPROVED" : "PENDING"); return <span className={`admin-status admin-status--${status.toLowerCase()}`}>{status}</span>; }, exportValue: row => row.decision || row.status || (row.verified ? "APPROVED" : "PENDING"), sortValue: row => row.decision || row.status || (row.verified ? "APPROVED" : "PENDING") },
    { key: "amount", label: bn ? "অগ্রিম" : "Advance", numeric: true, cell: row => formatCurrency(row.advance_bdt, "BDT", intlLocale), exportValue: row => row.advance_bdt, sortValue: row => Number(row.advance_bdt) },
  ];
  return <AdminDataPage<AdminPaymentRow>
    resource="payments"
    eyebrow={bn ? "ফাইন্যান্স অপারেশন" : "Finance operations"}
    title={bn ? "পেমেন্ট রিভিউ" : "Payment review"}
    description={bn ? "Transaction ID ও payment proof যাচাই করে সিদ্ধান্ত নিন। প্রতিটি সিদ্ধান্ত audit করা হয়।" : "Verify transaction IDs and payment proof. Every decision is recorded for audit."}
    searchPlaceholder={bn ? "অর্ডার বা transaction ID খুঁজুন" : "Search order or transaction ID"}
    columns={columns}
    getRowId={row => String(row.id ?? row.order_id)}
    filters={[{ key: "decision", label: bn ? "স্ট্যাটাস" : "Status", defaultValue: "PENDING", options: ["PENDING", "APPROVED", "REJECTED", "REVERSED"].map(value => ({ value, label: value })) }]}
    detailHref={row => row.id ? `/admin/payments/${row.id}` : `/admin/orders/${row.order_id}`}
    actions={(row, reload, notify) => <PaymentActions row={row} reload={reload} notify={notify} />}
  />;
}
