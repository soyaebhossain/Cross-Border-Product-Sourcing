"use client";

import { AdminDataPage, type AdminColumn } from "../../../components/admin-data-page";
import type { AdminAuditRow } from "../../../lib/api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

export default function AdminAuditPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const columns: AdminColumn<AdminAuditRow>[] = [
    { key: "time", label: bn ? "সময়" : "Time", cell: row => formatDateTime(row.created_at, intlLocale), exportValue: row => row.created_at, sortValue: row => row.created_at },
    { key: "actor", label: bn ? "অ্যাক্টর" : "Actor", cell: row => <div className="admin-primary-cell"><strong>{row.actor || (row.actor_user_id ? `User #${row.actor_user_id}` : row.actor_id ? `User #${row.actor_id}` : "System")}</strong><small>{row.actor_role || row.ip_address || "—"}</small></div>, exportValue: row => row.actor || row.actor_user_id || row.actor_id, sortValue: row => row.actor || row.actor_user_id || row.actor_id },
    { key: "action", label: bn ? "অ্যাকশন" : "Action", cell: row => <span className="admin-status admin-status--neutral">{row.action.replaceAll("_", " ")}</span>, exportValue: row => row.action, sortValue: row => row.action },
    { key: "entity", label: bn ? "রেকর্ড" : "Record", cell: row => `${row.entity_type || row.entity || "—"}${row.entity_id ? ` #${row.entity_id}` : ""}`, exportValue: row => `${row.entity_type || row.entity || ""} ${row.entity_id || ""}`, sortValue: row => row.entity_type || row.entity },
    { key: "detail", label: bn ? "বিস্তারিত" : "Details", cell: row => <span className="admin-detail-cell" title={row.note || row.detail || undefined}>{row.note || row.detail || (row.request_id ? `Request ${row.request_id}` : "—")}</span>, exportValue: row => row.note || row.detail || row.request_id },
  ];
  return <AdminDataPage<AdminAuditRow>
    resource="audit"
    eyebrow={bn ? "নিরাপত্তা ও জবাবদিহি" : "Security & accountability"}
    title={bn ? "অডিট লগ" : "Audit log"}
    description={bn ? "Payment, order ও administrative পরিবর্তনের অপরিবর্তনীয় ইতিহাস।" : "A traceable history of payment, order and administrative changes."}
    searchPlaceholder={bn ? "অ্যাক্টর, অ্যাকশন বা রেকর্ড খুঁজুন" : "Search actor, action or record"}
    columns={columns}
    filters={[{ key: "action", label: bn ? "অ্যাকশন" : "Action", options: [
      { value: "PAYMENT_APPROVED", label: "Payment approved" },
      { value: "PAYMENT_REJECTED", label: "Payment rejected" },
      { value: "ORDER_STATUS_CHANGED", label: "Order status changed" },
      { value: "LOGIN", label: "Login" },
    ] }]}
  />;
}
