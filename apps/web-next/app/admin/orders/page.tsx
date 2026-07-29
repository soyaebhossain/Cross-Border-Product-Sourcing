"use client";

import { useState } from "react";
import { AdminDataPage, type AdminColumn } from "../../../components/admin-data-page";
import { AdminModal } from "../../../components/admin-modal";
import { updateOrderStatus, type AdminOrderRow } from "../../../lib/api";
import { formatCurrency, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

const statuses = ["PENDING", "CONFIRMED", "PURCHASED", "IN_TRANSIT", "CUSTOMS", "LOCAL_DISPATCH", "DELIVERED", "CANCELLED"];

function customerLabel(row: AdminOrderRow) {
  if (typeof row.customer === "string") return row.customer;
  return row.customer?.username || row.customer?.email || row.customer?.phone || row.customer_name || `User #${row.user_id}`;
}

function OrderActions({ row, reload, notify }: { row: AdminOrderRow; reload: () => Promise<void>; notify: (message: string, kind?: "success" | "error") => void }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState(row.status);
  const [note, setNote] = useState("");
  const [tracking, setTracking] = useState(row.tracking_number || "");
  const [saving, setSaving] = useState(false);
  const { locale } = useLocale();
  const bn = locale === "bn";

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await updateOrderStatus(row.id, status, note, tracking, note);
      notify(bn ? `অর্ডার #${row.id} আপডেট হয়েছে।` : `Order #${row.id} was updated.`);
      setOpen(false);
      await reload();
    } catch {
      notify(bn ? "এই status পরিবর্তনটি অনুমোদিত নয় বা update ব্যর্থ হয়েছে।" : "This status transition is not allowed or the update failed.", "error");
    } finally {
      setSaving(false);
    }
  };

  return <>
    <button className="admin-row-button" type="button" onClick={() => setOpen(true)}>{bn ? "আপডেট" : "Update"}</button>
    <AdminModal open={open} onClose={() => !saving && setOpen(false)} title={`${bn ? "অর্ডার" : "Order"} #${row.id}`} description={bn ? "Status পরিবর্তনের কারণ audit log-এ সংরক্ষিত হবে।" : "The reason for this status change will be recorded in the audit log."}>
      <form className="admin-modal__form" onSubmit={submit}>
        <label><span>{bn ? "নতুন status" : "New status"}</span><select value={status} onChange={event => setStatus(event.target.value)}>{statuses.map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
        <label><span>{bn ? "ট্র্যাকিং নম্বর" : "Tracking number"} <small>({bn ? "প্রযোজ্য হলে" : "when applicable"})</small></span><input value={tracking} onChange={event => setTracking(event.target.value)} placeholder="e.g. DHL-123456" /></label>
        <label><span>{bn ? "অপারেশন নোট" : "Operations note"}</span><textarea value={note} onChange={event => setNote(event.target.value)} required minLength={3} rows={3} placeholder={bn ? "পরিবর্তনের কারণ লিখুন" : "Reason for this change"} /></label>
        <div className="admin-modal__actions"><button type="button" className="admin-button admin-button--secondary" onClick={() => setOpen(false)} disabled={saving}>{bn ? "বাতিল" : "Cancel"}</button><button type="submit" className="admin-button admin-button--primary" disabled={saving || (status === row.status && !tracking)}>{saving ? (bn ? "সেভ হচ্ছে…" : "Saving…") : (bn ? "পরিবর্তন নিশ্চিত করুন" : "Confirm update")}</button></div>
      </form>
    </AdminModal>
  </>;
}

export default function AdminOrdersPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const columns: AdminColumn<AdminOrderRow>[] = [
    { key: "order", label: bn ? "অর্ডার" : "Order", cell: row => <div className="admin-primary-cell"><strong>#{row.id}</strong><small>{customerLabel(row)}</small></div>, exportValue: row => row.id, sortValue: row => row.id },
    { key: "created", label: bn ? "তারিখ" : "Created", cell: row => formatDateTime(row.created_at, intlLocale), exportValue: row => row.created_at, sortValue: row => row.created_at },
    { key: "route", label: bn ? "রুট" : "Route", cell: row => `${row.country || row.country_code || "—"} · ${row.mode || "—"}`, exportValue: row => `${row.country || row.country_code || ""} ${row.mode || ""}`, sortValue: row => row.country || row.country_code },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => <span className={`admin-status admin-status--${row.status.toLowerCase()}`}>{row.status.replaceAll("_", " ")}</span>, exportValue: row => row.status, sortValue: row => row.status },
    { key: "payment", label: bn ? "পেমেন্ট" : "Payment", cell: row => { const decision = row.payment?.decision || row.payment_status || (row.payment_verified ? "APPROVED" : row.payment ? "PENDING" : "NO PROOF"); return <span className={`admin-status admin-status--${decision.toLowerCase().replaceAll(" ", "_")}`}>{decision}</span>; }, exportValue: row => row.payment?.decision || row.payment_status || (row.payment_verified ? "APPROVED" : "PENDING"), sortValue: row => row.payment?.decision || row.payment_status },
    { key: "total", label: bn ? "মোট" : "Total", numeric: true, cell: row => formatCurrency(row.total_bdt, "BDT", intlLocale), exportValue: row => row.total_bdt, sortValue: row => Number(row.total_bdt) },
  ];
  return <AdminDataPage<AdminOrderRow>
    resource="orders"
    eyebrow={bn ? "অর্ডার অপারেশন" : "Order operations"}
    title={bn ? "অর্ডার ম্যানেজমেন্ট" : "Order management"}
    description={bn ? "বৈধ workflow অনুসারে status, tracking এবং fulfilment update করুন।" : "Update status, tracking and fulfilment through a controlled workflow."}
    searchPlaceholder={bn ? "অর্ডার নম্বর বা customer খুঁজুন" : "Search order number or customer"}
    columns={columns}
    filters={[
      { key: "status", label: bn ? "স্ট্যাটাস" : "Status", options: statuses.map(value => ({ value, label: value.replaceAll("_", " ") })) },
      { key: "country", label: bn ? "দেশ" : "Country", options: ["CN", "IN", "SG", "TH"].map(value => ({ value, label: value })) },
    ]}
    showDateRange
    detailHref={row => `/admin/orders/${row.id}`}
    actions={(row, reload, notify) => <OrderActions row={row} reload={reload} notify={notify} />}
  />;
}
