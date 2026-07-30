"use client";

import { AdminDataPage, type AdminColumn } from "../../../components/admin-data-page";
import type { AdminQuoteRow } from "../../../lib/api";
import { formatCurrency, formatDateTime } from "../../../lib/format";
import { useLocale } from "../../../lib/locale-context";

function customerLabel(row: AdminQuoteRow) {
  if (typeof row.customer === "string") return row.customer;
  return row.customer?.username || row.customer?.email || row.customer?.phone || (row.user_id ? `User #${row.user_id}` : "Customer");
}

export default function AdminQuotesPage() {
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  const columns: AdminColumn<AdminQuoteRow>[] = [
    { key: "quote", label: bn ? "কোট" : "Quote", cell: row => <div className="admin-primary-cell"><strong>#{row.id}</strong><small>{customerLabel(row)}</small></div>, exportValue: row => row.id, sortValue: row => row.id },
    { key: "created", label: bn ? "তৈরি হয়েছে" : "Created", cell: row => formatDateTime(row.created_at, intlLocale), exportValue: row => row.created_at, sortValue: row => row.created_at },
    { key: "product", label: bn ? "পণ্য" : "Product", cell: row => <div className="admin-primary-cell"><strong>{row.product_name}</strong><small>{row.variant_name || "Standard"} · Qty {row.qty}</small></div>, exportValue: row => `${row.product_name} ${row.variant_name || ""}`, sortValue: row => row.product_name },
    { key: "route", label: bn ? "রুট" : "Route", cell: row => `${row.country || row.country_code || "—"} · ${row.mode || "—"}`, exportValue: row => `${row.country || row.country_code || ""} ${row.mode || ""}`, sortValue: row => row.country || row.country_code },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => <span className={`admin-status admin-status--${(row.status || "saved").toLowerCase()}`}>{row.status || "SAVED"}</span>, exportValue: row => row.status || "SAVED", sortValue: row => row.status || "SAVED" },
    { key: "expiry", label: bn ? "মেয়াদ" : "Expires", cell: row => row.expires_at ? formatDateTime(row.expires_at, intlLocale) : "—", exportValue: row => row.expires_at, sortValue: row => row.expires_at },
    { key: "value", label: bn ? "ল্যান্ডেড কস্ট" : "Landed cost", numeric: true, cell: row => formatCurrency(row.total_bdt, "BDT", intlLocale), exportValue: row => row.total_bdt, sortValue: row => Number(row.total_bdt) },
  ];
  return <AdminDataPage<AdminQuoteRow>
    resource="quotes"
    eyebrow={bn ? "সেলস পাইপলাইন" : "Sales pipeline"}
    title={bn ? "সেভড কোট" : "Saved quotes"}
    description={bn ? "Customer-এর সংরক্ষিত sourcing decision, value ও expiry পর্যবেক্ষণ করুন।" : "Monitor customer sourcing decisions, quoted value and expiry."}
    searchPlaceholder={bn ? "কোট, customer বা পণ্য খুঁজুন" : "Search quote, customer or product"}
    columns={columns}
    filters={[{ key: "status", label: bn ? "স্ট্যাটাস" : "Status", options: ["SAVED", "APPROVED", "ORDERED", "EXPIRED"].map(value => ({ value, label: value })) }]}
    detailHref={row => `/admin/quotes/${row.id}`}
  />;
}
