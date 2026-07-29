"use client";

import type { Route } from "next";
import { useParams } from "next/navigation";
import { AdminRecordDetail } from "../../../../../components/admin-record-detail";
import { getAdminCategory } from "../../../../../lib/admin-api";
import { useLocale } from "../../../../../lib/locale-context";

export default function AdminCategoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { locale } = useLocale();
  const bn = locale === "bn";
  return <AdminRecordDetail
    entity="categories"
    id={id}
    backHref={"/admin/catalog/categories" as Route}
    backLabel={bn ? "ক্যাটাগরি তালিকা" : "Category list"}
    eyebrow={bn ? "ক্যাটালগ কাঠামো" : "Catalog structure"}
    load={getAdminCategory}
    heading={record => record.name}
    subheading={record => `${record.slug} · #${record.id}`}
    sections={record => [{
      title: bn ? "ক্যাটাগরি তথ্য" : "Category details",
      values: [
        { label: bn ? "নাম" : "Name", value: record.name },
        { label: "Slug", value: record.slug },
        { label: bn ? "পণ্যের সংখ্যা" : "Products", value: record.product_count },
        { label: bn ? "অবস্থা" : "Status", value: <span className={`admin-status admin-status--${record.is_active ? "active" : "inactive"}`}>{record.is_active ? "ACTIVE" : "ARCHIVED"}</span> },
      ],
    }]}
  />;
}
