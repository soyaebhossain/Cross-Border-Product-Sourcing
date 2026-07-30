"use client";

import Link from "next/link";
import type { Route } from "next";
import { useParams } from "next/navigation";
import { AdminRecordDetail } from "../../../../../components/admin-record-detail";
import { getAdminOffer } from "../../../../../lib/admin-api";
import { formatAmount, formatDateTime } from "../../../../../lib/format";
import { useLocale } from "../../../../../lib/locale-context";

export default function AdminOfferDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { locale, intlLocale } = useLocale();
  const bn = locale === "bn";
  return <AdminRecordDetail
    entity="offers"
    id={id}
    backHref={"/admin/suppliers/offers" as Route}
    backLabel={bn ? "অফার তালিকা" : "Offer list"}
    eyebrow={bn ? "সাপ্লায়ার অফার" : "Supplier offer"}
    load={getAdminOffer}
    heading={record => `${record.variant.product_name} · ${record.supplier.name}`}
    subheading={record => `Offer #${record.id} · ${formatDateTime(record.updated_at, intlLocale)}`}
    sections={record => [
      {
        title: bn ? "অফারের উৎস" : "Offer source",
        values: [
          { label: bn ? "পণ্য" : "Product", value: <Link href={`/admin/catalog/${record.variant.product_id}` as Route}>{record.variant.product_name}</Link> },
          { label: bn ? "ভ্যারিয়েন্ট" : "Variant", value: <Link href={`/admin/catalog/variants/${record.variant.id}` as Route}>{record.variant.name || record.variant.sku || `#${record.variant.id}`}</Link> },
          { label: bn ? "সাপ্লায়ার" : "Supplier", value: <Link href={`/admin/suppliers/${record.supplier.id}` as Route}>{record.supplier.name}</Link> },
          { label: bn ? "দেশ" : "Country", value: `${record.country.code} · ${record.country.name}` },
          { label: bn ? "সোর্স" : "Source", value: record.source_url ? <a href={record.source_url} target="_blank" rel="noreferrer">{bn ? "উৎস খুলুন" : "Open source"}</a> : "—" },
        ],
      },
      {
        title: bn ? "বাণিজ্যিক শর্ত" : "Commercial terms",
        values: [
          { label: bn ? "মূল্য" : "Origin price", value: `${record.currency} ${formatAmount(record.price_origin, intlLocale)}` },
          { label: bn ? "মোড" : "Mode", value: record.mode },
          { label: bn ? "স্টক" : "Stock", value: record.stock },
          { label: "MOQ", value: record.moq },
          { label: bn ? "অবস্থা" : "Status", value: <span className={`admin-status admin-status--${record.is_active ? "active" : "inactive"}`}>{record.is_active ? "ACTIVE" : "ARCHIVED"}</span> },
        ],
      },
    ]}
  />;
}
