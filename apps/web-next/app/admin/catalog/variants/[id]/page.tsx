"use client";

import Link from "next/link";
import type { Route } from "next";
import { useParams } from "next/navigation";
import { AdminRecordDetail } from "../../../../../components/admin-record-detail";
import { getAdminVariant } from "../../../../../lib/admin-api";
import { useLocale } from "../../../../../lib/locale-context";

export default function AdminVariantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { locale } = useLocale();
  const bn = locale === "bn";
  return <AdminRecordDetail
    entity="variants"
    id={id}
    backHref={"/admin/catalog/variants" as Route}
    backLabel={bn ? "ভ্যারিয়েন্ট তালিকা" : "Variant list"}
    eyebrow={bn ? "ক্যাটালগ রেকর্ড" : "Catalog record"}
    load={getAdminVariant}
    heading={record => record.variant_name || record.sku || `Variant #${record.id}`}
    subheading={record => `${record.product_name || "Product"} · #${record.id}`}
    sections={record => [
      {
        title: bn ? "ভ্যারিয়েন্ট তথ্য" : "Variant details",
        values: [
          { label: bn ? "পণ্য" : "Product", value: <Link href={`/admin/catalog/${record.product_id}` as Route}>{record.product_name || `Product #${record.product_id}`}</Link> },
          { label: "SKU", value: record.sku || "—" },
          { label: bn ? "নাম" : "Name", value: record.variant_name || "—" },
          { label: bn ? "অফার" : "Offers", value: record.offer_count },
          { label: bn ? "অবস্থা" : "Status", value: <span className={`admin-status admin-status--${record.is_active ? "active" : "inactive"}`}>{record.is_active ? "ACTIVE" : "ARCHIVED"}</span> },
        ],
      },
      {
        title: bn ? "মাত্রা ও ওজন" : "Dimensions and weight",
        values: [
          { label: bn ? "ওজন" : "Weight", value: `${record.weight_kg} kg` },
          { label: bn ? "দৈর্ঘ্য" : "Length", value: `${record.length_cm} cm` },
          { label: bn ? "প্রস্থ" : "Width", value: `${record.width_cm} cm` },
          { label: bn ? "উচ্চতা" : "Height", value: `${record.height_cm} cm` },
        ],
      },
    ]}
  />;
}
