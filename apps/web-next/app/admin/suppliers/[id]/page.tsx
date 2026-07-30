"use client";

import Link from "next/link";
import type { Route } from "next";
import { useParams } from "next/navigation";
import { AdminRecordDetail } from "../../../../components/admin-record-detail";
import { getAdminSupplier } from "../../../../lib/admin-api";
import { useLocale } from "../../../../lib/locale-context";

export default function AdminSupplierDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { locale } = useLocale();
  const bn = locale === "bn";
  return <AdminRecordDetail
    entity="suppliers"
    id={id}
    backHref={"/admin/suppliers" as Route}
    backLabel={bn ? "সাপ্লায়ার তালিকা" : "Supplier list"}
    eyebrow={bn ? "সাপ্লাই নেটওয়ার্ক" : "Supply network"}
    load={getAdminSupplier}
    heading={record => record.name}
    subheading={record => `${record.country.code} · ${record.country.name} · #${record.id}`}
    sections={record => [
      {
        title: bn ? "সাপ্লায়ার তথ্য" : "Supplier details",
        values: [
          { label: bn ? "নাম" : "Name", value: record.name },
          { label: bn ? "দেশ" : "Country", value: `${record.country.code} · ${record.country.name}` },
          { label: bn ? "রেটিং" : "Rating", value: `${Number(record.rating).toFixed(2)} / 5.00` },
          { label: bn ? "অফার" : "Offers", value: <Link href={`/admin/suppliers/offers?q=${encodeURIComponent(record.name)}` as Route}>{record.offer_count}</Link> },
          { label: bn ? "অবস্থা" : "Status", value: <span className={`admin-status admin-status--${record.is_active ? "active" : "inactive"}`}>{record.is_active ? "ACTIVE" : "ARCHIVED"}</span> },
        ],
      },
      {
        title: bn ? "অপারেশন নোট" : "Operations note",
        values: [{ label: bn ? "সাপ্লায়ার নোট" : "Supplier note", value: record.note || "—" }],
      },
    ]}
  />;
}
