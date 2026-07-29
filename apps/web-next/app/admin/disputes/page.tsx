"use client";

import Link from "next/link";
import {
  AdminOperationsList,
  type AdminOperationsColumn,
  type AdminOperationsQuery,
} from "../../../components/admin-operations-list";
import {
  listAdminDisputes,
  type CustomerDispute,
} from "../../../lib/customer-api";
import { formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";
import { useAdminAccess } from "../../../lib/use-admin-access";

function loadDisputes(query: AdminOperationsQuery) {
  return listAdminDisputes({
    q: query.q,
    status: query.status,
    limit: query.limit,
    offset: query.offset,
  });
}

export default function AdminDisputesPage() {
  const { locale, intlLocale } = useLocale();
  const { isAdmin } = useAdminAccess();
  const bn = locale === "bn";
  const columns: AdminOperationsColumn<CustomerDispute>[] = [
    {
      key: "dispute",
      label: bn ? "বিরোধ" : "Dispute",
      cell: row => <div className="admin-primary-cell"><strong>{row.public_id}</strong><small>{row.type.replaceAll("_", " ")}</small></div>,
      exportValue: row => `${row.public_id} ${row.type}`,
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
      key: "order",
      label: bn ? "অর্ডার" : "Order",
      cell: row => <Link href={`/admin/orders/${row.order_id}`}>#{row.order_id}</Link>,
      exportValue: row => row.order_id,
      sortValue: row => row.order_id,
    },
    {
      key: "summary",
      label: bn ? "অভিযোগ" : "Issue",
      cell: row => <span className="admin-detail-cell" title={row.description}>{row.description}</span>,
      exportValue: row => row.description,
      sortValue: row => row.description,
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

  return <AdminOperationsList<CustomerDispute>
    resourceName="disputes"
    eyebrow={bn ? "সমাধান ও জবাবদিহি" : "Resolution & accountability"}
    title={bn ? "কাস্টমার বিরোধ" : "Customer disputes"}
    description={bn ? "অর্ডার-সংযুক্ত অভিযোগ পর্যালোচনা করুন, সিদ্ধান্তের note রাখুন এবং কাস্টমারকে অবহিত করুন।" : "Review order-linked complaints, record a reasoned decision and notify the customer."}
    columns={columns}
    load={loadDisputes}
    searchPlaceholder={bn ? "Dispute ID বা অভিযোগ খুঁজুন" : "Search dispute ID or description"}
    filters={[{
      key: "status",
      label: bn ? "স্ট্যাটাস" : "Status",
      options: ["OPEN", "UNDER_REVIEW", "RESOLVED", "REJECTED", "CANCELLED"].map(value => ({ value, label: value.replaceAll("_", " ") })),
    }]}
    detailHref={row => `/admin/disputes/${row.id}`}
  />;
}
