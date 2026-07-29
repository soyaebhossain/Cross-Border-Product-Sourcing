"use client";

import { useState } from "react";
import { AdminModal } from "../../../components/admin-modal";
import {
  AdminOperationsList,
  type AdminOperationsColumn,
  type AdminOperationsQuery,
} from "../../../components/admin-operations-list";
import {
  dispatchAdminOutbox,
  listAdminOutbox,
  type NotificationDelivery,
  requeueAdminOutbox,
} from "../../../lib/customer-api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";
import { useAdminAccess } from "../../../lib/use-admin-access";

function loadOutbox(query: AdminOperationsQuery) {
  return listAdminOutbox({
    status: query.status,
    channel: query.channel,
    limit: query.limit,
    offset: query.offset,
  });
}

function matchesLoadedOutbox(row: NotificationDelivery, rawQuery: string) {
  const query = rawQuery.trim().toLocaleLowerCase();
  return [
    row.id,
    row.channel,
    row.destination_masked,
    row.status,
    row.provider_message_id,
    row.error_code,
    row.error_detail,
  ].some(value => String(value ?? "").toLocaleLowerCase().includes(query));
}

function RequeueAction({
  row,
  reload,
  notify,
}: {
  row: NotificationDelivery;
  reload: () => Promise<void>;
  notify: (message: string, kind?: "success" | "error") => void;
}) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const { locale } = useLocale();
  const bn = locale === "bn";
  const submit = async () => {
    setSaving(true);
    try {
      await requeueAdminOutbox(row.id);
      setOpen(false);
      notify(bn ? `Delivery #${row.id} আবার queue করা হয়েছে।` : `Delivery #${row.id} was requeued.`);
      await reload();
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : (bn ? "Delivery requeue করা যায়নি।" : "Delivery could not be requeued."), "error");
    } finally {
      setSaving(false);
    }
  };
  return <>
    <button className="admin-row-button" type="button" onClick={() => setOpen(true)}>{bn ? "পুনরায় queue" : "Requeue"}</button>
    <AdminModal open={open} onClose={() => !saving && setOpen(false)} title={bn ? "ব্যর্থ delivery পুনরায় queue করবেন?" : "Requeue failed delivery?"} description={`#${row.id} · ${row.channel} · ${row.destination_masked || "No destination"}`}>
      <div className="admin-modal__form">
        <div className="admin-decision-summary"><strong>{row.error_code || "FAILED"}</strong><span>{bn ? "নতুন dispatch attempt audit log-এ দেখা যাবে।" : "A new dispatch attempt will remain traceable."}</span></div>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setOpen(false)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" type="button" disabled={saving} onClick={() => void submit()}>{saving ? (bn ? "Queue হচ্ছে…" : "Requeuing…") : (bn ? "নিশ্চিত করুন" : "Confirm requeue")}</button></div>
      </div>
    </AdminModal>
  </>;
}

function DispatchAction({
  reload,
  notify,
}: {
  reload: () => Promise<void>;
  notify: (message: string, kind?: "success" | "error") => void;
}) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const { locale } = useLocale();
  const bn = locale === "bn";
  const submit = async () => {
    setSaving(true);
    try {
      const result = await dispatchAdminOutbox();
      const summary = Object.entries(result).map(([key, value]) => `${key}: ${value}`).join(" · ");
      setOpen(false);
      notify(summary || (bn ? "একটি queued delivery dispatch করা হয়েছে।" : "One queued delivery was dispatched."));
      await reload();
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : (bn ? "Dispatch চালানো যায়নি।" : "Dispatch could not be run."), "error");
    } finally {
      setSaving(false);
    }
  };
  return <>
    <button className="admin-button admin-button--primary" type="button" onClick={() => setOpen(true)}>{bn ? "পরবর্তী delivery পাঠান" : "Dispatch next delivery"}</button>
    <AdminModal open={open} onClose={() => !saving && setOpen(false)} title={bn ? "পরবর্তী queued delivery পাঠাবেন?" : "Dispatch the next queued delivery?"} description={bn ? "একবারে একটি delivery claim করে configured provider-এ পাঠানো হবে।" : "One delivery will be claimed and sent through its configured provider."}>
      <div className="admin-modal__form">
        <div className="admin-decision-summary"><strong>1</strong><span>{bn ? "Provider credential না থাকলে real FAILED status ও safe error code সংরক্ষিত হবে।" : "If a provider is not configured, a real FAILED status and safe error code will be recorded."}</span></div>
        <div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" disabled={saving} onClick={() => setOpen(false)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" type="button" disabled={saving} onClick={() => void submit()}>{saving ? (bn ? "পাঠানো হচ্ছে…" : "Dispatching…") : (bn ? "Dispatch নিশ্চিত করুন" : "Confirm dispatch")}</button></div>
      </div>
    </AdminModal>
  </>;
}

export default function AdminNotificationsPage() {
  const { locale, intlLocale } = useLocale();
  const { isAdmin, loading: accessLoading } = useAdminAccess();
  const bn = locale === "bn";
  const columns: AdminOperationsColumn<NotificationDelivery>[] = [
    {
      key: "delivery",
      label: bn ? "Delivery" : "Delivery",
      cell: row => <div className="admin-primary-cell"><strong>#{row.id}</strong><small>{row.destination_masked || (bn ? "গন্তব্য নেই" : "No destination")}</small></div>,
      exportValue: row => `${row.id} ${row.destination_masked || ""}`,
      sortValue: row => row.id,
    },
    {
      key: "channel",
      label: bn ? "চ্যানেল" : "Channel",
      cell: row => <span className="admin-status admin-status--neutral">{row.channel}</span>,
      exportValue: row => row.channel,
      sortValue: row => row.channel,
    },
    {
      key: "status",
      label: bn ? "স্ট্যাটাস" : "Status",
      cell: row => <span className={`admin-status admin-status--${row.status.toLowerCase()}`}>{row.status}</span>,
      exportValue: row => row.status,
      sortValue: row => row.status,
    },
    {
      key: "attempts",
      label: bn ? "চেষ্টা" : "Attempts",
      numeric: true,
      cell: row => new Intl.NumberFormat(intlLocale).format(row.attempts),
      exportValue: row => row.attempts,
      sortValue: row => row.attempts,
    },
    {
      key: "activity",
      label: bn ? "সর্বশেষ চেষ্টা" : "Last attempt",
      cell: row => <div className="admin-primary-cell"><strong>{formatDateTime(row.last_attempt_at || row.sent_at || row.created_at, intlLocale)}</strong><small>{row.next_attempt_at ? `${bn ? "পরবর্তী" : "Next"} ${formatDateTime(row.next_attempt_at, intlLocale)}` : "—"}</small></div>,
      exportValue: row => row.last_attempt_at || row.sent_at || row.created_at,
      sortValue: row => row.last_attempt_at || row.sent_at || row.created_at,
    },
    {
      key: "result",
      label: bn ? "Provider ফলাফল" : "Provider result",
      cell: row => <div className="admin-primary-cell"><strong>{row.provider_message_id || row.error_code || "—"}</strong><small>{row.error_detail || (row.sent_at ? (bn ? "Delivery সফল" : "Delivered") : "—")}</small></div>,
      exportValue: row => `${row.provider_message_id || ""} ${row.error_code || ""} ${row.error_detail || ""}`,
      sortValue: row => row.error_code || row.provider_message_id,
    },
  ];

  return <AdminOperationsList<NotificationDelivery>
    resourceName="notification-outbox"
    eyebrow={bn ? "স্বয়ংক্রিয় যোগাযোগ" : "Automated communications"}
    title={bn ? "Notification outbox" : "Notification outbox"}
    description={bn ? "Email, SMS ও WhatsApp delivery-এর real queue, provider ফলাফল এবং retry lifecycle পর্যবেক্ষণ করুন।" : "Monitor the real email, SMS and WhatsApp queue, provider outcomes and retry lifecycle."}
    columns={columns}
    load={loadOutbox}
    searchPlaceholder={bn ? "এই পৃষ্ঠায় delivery ID, destination বা error ফিল্টার করুন" : "Filter this page by delivery ID, destination or error"}
    localSearch={matchesLoadedOutbox}
    filters={[
      { key: "status", label: bn ? "স্ট্যাটাস" : "Status", options: ["QUEUED", "PROCESSING", "SENT", "FAILED"].map(value => ({ value, label: value })) },
      { key: "channel", label: bn ? "চ্যানেল" : "Channel", options: ["email", "sms", "whatsapp"].map(value => ({ value, label: value.toUpperCase() })) },
    ]}
    detailHref={row => `/admin/notifications/${row.id}`}
    headerAction={(reload, notify) => isAdmin
      ? <DispatchAction reload={reload} notify={notify} />
      : <span className="admin-read-only">{accessLoading ? (bn ? "অ্যাক্সেস যাচাই হচ্ছে…" : "Checking access…") : (bn ? "Operator · শুধু পর্যবেক্ষণ" : "Operator · monitoring only")}</span>}
    actions={(row, reload, notify) => isAdmin && row.status === "FAILED" ? <RequeueAction row={row} reload={reload} notify={notify} /> : null}
  />;
}
