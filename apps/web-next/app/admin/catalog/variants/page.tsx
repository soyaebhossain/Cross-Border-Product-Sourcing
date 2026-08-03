"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminArchiveAction } from "../../../../components/admin-archive-action";
import { AdminDataPage, type AdminColumn } from "../../../../components/admin-data-page";
import { AdminModal } from "../../../../components/admin-modal";
import { bulkArchiveAdminEntities, createAdminVariant, updateAdminVariant, type AdminVariant } from "../../../../lib/admin-api";
import { getAdminList, type AdminProductRow } from "../../../../lib/api";
import { useLocale } from "../../../../lib/locale-context";

type Fields = { product_id: string; sku: string; variant_name: string; weight_kg: string; length_cm: string; width_cm: string; height_cm: string };
const empty: Fields = { product_id: "", sku: "", variant_name: "", weight_kg: "0", length_cm: "0", width_cm: "0", height_cm: "0" };

export default function AdminVariantsPage() {
  const [version, setVersion] = useState(0);
  const [products, setProducts] = useState<AdminProductRow[]>([]);
  const [editing, setEditing] = useState<AdminVariant | "new" | null>(null);
  const [fields, setFields] = useState<Fields>(empty);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { locale } = useLocale();
  const bn = locale === "bn";
  useEffect(() => { getAdminList<AdminProductRow>("products", { page_size: 100 }).then(result => setProducts(result.items)).catch(() => setProducts([])); }, [version]);
  const openNew = () => { setEditing("new"); setFields({ ...empty, product_id: products[0] ? String(products[0].id) : "" }); setNote(""); setError(""); };
  const openEdit = (row: AdminVariant) => { setEditing(row); setFields({ product_id: String(row.product_id), sku: row.sku || "", variant_name: row.variant_name || "", weight_kg: row.weight_kg, length_cm: row.length_cm, width_cm: row.width_cm, height_cm: row.height_cm }); setNote(""); setError(""); };
  const set = (key: keyof Fields, value: string) => setFields(current => ({ ...current, [key]: value }));
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    const dimensions = { sku: fields.sku.trim() || undefined, variant_name: fields.variant_name.trim() || undefined, weight_kg: Number(fields.weight_kg), length_cm: Number(fields.length_cm), width_cm: Number(fields.width_cm), height_cm: Number(fields.height_cm) };
    try {
      if (editing === "new") await createAdminVariant({ product_id: Number(fields.product_id), ...dimensions });
      else if (editing) await updateAdminVariant(editing.id, { ...dimensions, note });
      setEditing(null); setVersion(value => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Variant could not be saved."); }
    finally { setSaving(false); }
  };
  const columns: AdminColumn<AdminVariant>[] = [
    { key: "variant", label: bn ? "ভ্যারিয়েন্ট" : "Variant", cell: row => <div className="admin-primary-cell"><strong>{row.variant_name || `Variant #${row.id}`}</strong><small>{row.sku || "No SKU"}</small></div>, exportValue: row => `${row.variant_name || ""} ${row.sku || ""}`, sortValue: row => row.variant_name || row.sku },
    { key: "product", label: bn ? "পণ্য" : "Product", cell: row => row.product_name || `#${row.product_id}`, exportValue: row => row.product_name, sortValue: row => row.product_name },
    { key: "weight", label: bn ? "ওজন" : "Weight", numeric: true, cell: row => `${Number(row.weight_kg).toFixed(3)} kg`, exportValue: row => row.weight_kg, sortValue: row => Number(row.weight_kg) },
    { key: "offers", label: bn ? "অফার" : "Offers", numeric: true, cell: row => row.offer_count, exportValue: row => row.offer_count, sortValue: row => row.offer_count },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => <span className={`admin-status admin-status--${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "ACTIVE" : "ARCHIVED"}</span>, exportValue: row => row.is_active ? "Active" : "Archived", sortValue: row => row.is_active ? 1 : 0 },
  ];
  return <>
    <nav className="admin-subnav" aria-label={bn ? "Catalog section" : "Catalog sections"}><Link href="/admin/catalog">{bn ? "পণ্য" : "Products"}</Link><Link href="/admin/catalog/categories">{bn ? "ক্যাটাগরি" : "Categories"}</Link><Link className="admin-subnav--active" href="/admin/catalog/variants">{bn ? "ভ্যারিয়েন্ট" : "Variants"}</Link><Link href="/admin/catalog/media">{bn ? "ছবি" : "Product media"}</Link></nav>
    <AdminDataPage<AdminVariant> key={version} resource="variants" eyebrow={bn ? "SKU ও logistics" : "SKU and logistics"} title={bn ? "ভ্যারিয়েন্ট" : "Product variants"} description={bn ? "SKU, dimension, weight এবং offer coverage পরিচালনা করুন।" : "Manage SKU, dimensions, weight and offer coverage."} searchPlaceholder={bn ? "SKU, variant বা product" : "Search SKU, variant or product"} columns={columns} filters={[{ key: "active", label: bn ? "স্ট্যাটাস" : "Status", options: [{ value: "true", label: "Active" }, { value: "false", label: "Archived" }] }]} headerAction={<button className="admin-button admin-button--primary" type="button" onClick={openNew} disabled={!products.length}>{bn ? "ভ্যারিয়েন্ট যোগ করুন" : "Add variant"}</button>} detailHref={row => `/admin/catalog/variants/${row.id}`} actions={(row, reload, notify) => <><button className="admin-row-button" type="button" onClick={() => openEdit(row)}>Edit</button><AdminArchiveAction entity="variants" id={row.id} isActive={row.is_active} reload={reload} notify={notify} /></>} bulkActions={[{ label: bn ? "Selected archive" : "Archive selected", kind: "danger", run: (ids, auditNote) => bulkArchiveAdminEntities("variants", ids, true, auditNote).then(() => undefined) }, { label: bn ? "Selected restore" : "Restore selected", run: (ids, auditNote) => bulkArchiveAdminEntities("variants", ids, false, auditNote).then(() => undefined) }]} />
    <AdminModal open={editing !== null} onClose={() => !saving && setEditing(null)} title={editing === "new" ? (bn ? "ভ্যারিয়েন্ট যোগ করুন" : "Add variant") : (bn ? "ভ্যারিয়েন্ট edit" : "Edit variant")} description={bn ? "সঠিক dimension landed cost ও shipping calculation-এ ব্যবহার হয়।" : "Accurate dimensions drive landed-cost and shipping calculations."}><form className="admin-modal__form" onSubmit={submit}>{editing === "new" ? <label><span>{bn ? "পণ্য" : "Product"}</span><select required value={fields.product_id} onChange={event => set("product_id", event.target.value)}>{products.map(product => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label> : null}<label><span>SKU</span><input maxLength={80} value={fields.sku} onChange={event => set("sku", event.target.value)} /></label><label><span>{bn ? "ভ্যারিয়েন্ট নাম" : "Variant name"}</span><input maxLength={120} value={fields.variant_name} onChange={event => set("variant_name", event.target.value)} /></label><div className="admin-form-grid">{(["weight_kg", "length_cm", "width_cm", "height_cm"] as const).map(key => <label key={key}><span>{key.replace("_", " ")}</span><input type="number" min="0" step=".001" value={fields[key]} onChange={event => set(key, event.target.value)} required /></label>)}</div>{editing !== "new" ? <label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} required rows={3} value={note} onChange={event => setNote(event.target.value)} /></label> : null}{error ? <div className="admin-alert admin-alert--error">{error}</div> : null}<div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setEditing(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving || !fields.product_id || (editing !== "new" && note.trim().length < 3)}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button></div></form></AdminModal>
  </>;
}
