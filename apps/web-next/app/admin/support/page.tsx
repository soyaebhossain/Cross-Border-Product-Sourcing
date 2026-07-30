"use client";

import Link from "next/link";
import {
  AdminOperationsList,
  type AdminOperationsColumn,
  type AdminOperationsQuery,
} from "../../../components/admin-operations-list";
import {
  listAdminSupportTickets,
  type SupportTicket,
} from "../../../lib/customer-api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";
import { useAdminAccess } from "../../../lib/use-admin-access";

function loadSupportTickets(query: AdminOperationsQuery) {
  return listAdminSupportTickets({
    q: query.q,
    status: query.status,
    limit: query.limit,
    offset: query.offset,
  });
}

export default function AdminSupportPage() {
  const { locale, intlLocale } = useLocale();
  const { isAdmin } = useAdminAccess();
  const bn = locale === "bn";
  const columns: AdminOperationsColumn<SupportTicket>[] = [
    {
      key: "ticket",
      label: bn ? "টিকিট" : "Ticket",
      cell: row => <div className="admin-primary-cell"><strong>{row.subject}</strong><small>{row.public_id}</small></div>,
      exportValue: row => `${row.public_id} ${row.subject}`,
      sortValue: row => row.public_id,
    },
    {
      key: "customer",
      label: bn ? "কাস্টমার" : "Customer",
      cell: row => isAdmin ? <Link href={`/admin/users/${row.user_id}`}>User #{row.user_id}</Link> : `User #${row.user_id}`,
      exportValue: row => row.user_id,
      sortValue: row => row.user_id,
    },
    {
      key: "context",
      label: bn ? "বিষয়" : "Context",
      cell: row => <div className="admin-primary-cell"><strong>{row.category}</strong><small>{row.order_id ? <Link href={`/admin/orders/${row.order_id}`}>Order #{row.order_id}</Link> : (bn ? "অর্ডার সংযুক্ত নয়" : "No linked order")}</small></div>,
      exportValue: row => `${row.category} ${row.order_id || ""}`,
      sortValue: row => row.category,
    },
    {
      key: "priority",
      label: bn ? "অগ্রাধিকার" : "Priority",
      cell: row => <span className={`admin-status admin-status--${row.priority.toLowerCase()}`}>{row.priority}</span>,
      exportValue: row => row.priority,
      sortValue: row => row.priority,
    },
    {
      key: "status",
      label: bn ? "স্ট্যাটাস" : "Status",
      cell: row => <span className={`admin-status admin-status--${row.status.toLowerCase()}`}>{row.status.replaceAll("_", " ")}</span>,
      exportValue: row => row.status,
      sortValue: row => row.status,
    },
    {
      key: "updated",
      label: bn ? "সর্বশেষ আপডেট" : "Last updated",
      cell: row => formatDateTime(row.updated_at || row.created_at, intlLocale),
      exportValue: row => row.updated_at || row.created_at,
      sortValue: row => row.updated_at || row.created_at,
    },
  ];

  return <AdminOperationsList<SupportTicket>
    resourceName="support-tickets"
    eyebrow={bn ? "কাস্টমার সার্ভিস" : "Customer service"}
    title={bn ? "সাপোর্ট টিকিট" : "Support tickets"}
    description={bn ? "কাস্টমারের প্রশ্ন, অর্ডার সমস্যা ও সাপোর্ট কথোপকথন এক জায়গা থেকে পরিচালনা করুন।" : "Manage customer questions, order issues and support conversations from one queue."}
    columns={columns}
    load={loadSupportTickets}
    searchPlaceholder={bn ? "টিকিট ID বা subject খুঁজুন" : "Search ticket ID or subject"}
    filters={[{
      key: "status",
      label: bn ? "স্ট্যাটাস" : "Status",
      options: ["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER", "RESOLVED", "CLOSED"].map(value => ({ value, label: value.replaceAll("_", " ") })),
    }]}
    detailHref={row => `/admin/support/${row.id}`}
  />;
}
