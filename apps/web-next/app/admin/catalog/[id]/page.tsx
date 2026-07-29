"use client";

import Link from "next/link";
import type { Route } from "next";
import { useParams } from "next/navigation";
import { AdminRecordDetail } from "../../../../components/admin-record-detail";
import { getAdminProduct } from "../../../../lib/admin-api";
import { useLocale } from "../../../../lib/locale-context";

export default function AdminProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { locale } = useLocale();
  const bn = locale === "bn";
  return <AdminRecordDetail
    entity="products"
    id={id}
    backHref={"/admin/catalog" as Route}
    backLabel={bn ? "পণ্য তালিকা" : "Product list"}
    eyebrow={bn ? "ক্যাটালগ রেকর্ড" : "Catalog record"}
    load={getAdminProduct}
    heading={record => record.name}
    subheading={record => `${record.model || record.slug} · #${record.id}`}
    sections={record => [
      {
        title: bn ? "পণ্যের পরিচয়" : "Product identity",
        values: [
          { label: bn ? "নাম" : "Name", value: record.name },
          { label: "Slug", value: record.slug },
          { label: "Model", value: record.model || "—" },
          { label: bn ? "ক্যাটাগরি" : "Category", value: <Link href={`/admin/catalog/categories/${record.category.id}` as Route}>{record.category.name}</Link> },
          { label: bn ? "অবস্থা" : "Status", value: <span className={`admin-status admin-status--${record.is_active ? "active" : "inactive"}`}>{record.is_active ? "ACTIVE" : "ARCHIVED"}</span> },
        ],
      },
      {
        title: bn ? "ক্যাটালগ কনটেন্ট" : "Catalog content",
        values: [
          { label: bn ? "বর্ণনা" : "Description", value: record.description || "—" },
          { label: bn ? "ছবি" : "Image", value: record.image ? <a href={record.image} target="_blank" rel="noreferrer">{bn ? "ছবি খুলুন" : "Open image"}</a> : "—" },
          { label: bn ? "ভ্যারিয়েন্ট" : "Variants", value: record.variants.length },
        ],
      },
      {
        title: bn ? "ভ্যারিয়েন্ট তালিকা" : "Variant records",
        description: bn ? "প্রতিটি ভ্যারিয়েন্টের SKU, ওজন ও অফার coverage।" : "SKU, weight and offer coverage for each variant.",
        values: record.variants.length ? record.variants.map(variant => ({
          label: variant.variant_name || variant.sku || `Variant #${variant.id}`,
          value: <Link href={`/admin/catalog/variants/${variant.id}` as Route}>{variant.sku || `#${variant.id}`} · {variant.weight_kg} kg · {variant.offer_count} offers</Link>,
        })) : [{ label: bn ? "ভ্যারিয়েন্ট" : "Variants", value: bn ? "কোনো ভ্যারিয়েন্ট নেই" : "No variants" }],
      },
    ]}
  />;
}
