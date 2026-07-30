"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminArchiveAction } from "../../../components/admin-archive-action";
import { AdminDataPage, type AdminColumn } from "../../../components/admin-data-page";
import { AdminModal } from "../../../components/admin-modal";
import { bulkArchiveAdminEntities, createAdminProduct, getAdminProduct, updateAdminProduct } from "../../../lib/admin-api";
import { getLiveCategories, type AdminProductRow, type Category } from "../../../lib/api";
import { useLocale } from "../../../lib/locale-context";

type Fields = { name: string; slug: string; category_id: string; model: string; description: string; image: string };
const blank: Fields = { name: "", slug: "", category_id: "", model: "", description: "", image: "" };
function slugify(value: string) { return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
function categoryName(category: AdminProductRow["category"]) { return typeof category === "string" ? category : category?.name || "Uncategorised"; }

export default function AdminCatalogPage() {
  const [version, setVersion] = useState(0);
  const [categories, setCategories] = useState<Category[]>([]);
  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [fields, setFields] = useState<Fields>(blank);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { locale } = useLocale();
  const bn = locale === "bn";
  useEffect(() => { getLiveCategories().then(setCategories).catch(() => setCategories([])); }, [version]);
  const set = (key: keyof Fields, value: string) => setFields(current => ({ ...current, [key]: value }));
  const openNew = () => { setEditingId("new"); setFields({ ...blank, category_id: categories[0] ? String(categories[0].id) : "" }); setNote(""); setError(""); };
  const openEdit = async (row: AdminProductRow) => {
    setSaving(true); setError("");
    try {
      const item = await getAdminProduct(row.id);
      setFields({ name: item.name, slug: item.slug, category_id: String(item.category.id), model: item.model || "", description: item.description || "", image: item.image || "" });
      setEditingId(item.id); setNote("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Product detail could not be loaded."); }
    finally { setSaving(false); }
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    const payload = { name: fields.name.trim(), slug: slugify(fields.slug), category_id: Number(fields.category_id), model: fields.model.trim() || undefined, description: fields.description.trim() || undefined, image: fields.image.trim() || undefined };
    try {
      if (editingId === "new") await createAdminProduct(payload);
      else if (editingId) await updateAdminProduct(editingId, { ...payload, note });
      setEditingId(null); setVersion(value => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Product could not be saved."); }
    finally { setSaving(false); }
  };
  const columns: AdminColumn<AdminProductRow>[] = [
    { key: "product", label: bn ? "পণ্য" : "Product", cell: row => <div className="admin-primary-cell"><strong>{row.name}</strong><small>{row.model || row.slug || `ID ${row.id}`}</small></div>, exportValue: row => `${row.name} ${row.model || ""}`, sortValue: row => row.name },
    { key: "category", label: bn ? "ক্যাটাগরি" : "Category", cell: row => categoryName(row.category), exportValue: row => categoryName(row.category), sortValue: row => categoryName(row.category) },
    { key: "variants", label: bn ? "ভ্যারিয়েন্ট" : "Variants", numeric: true, cell: row => row.variant_count ?? (Array.isArray(row.variants) ? row.variants.length : row.variants ?? 0), exportValue: row => row.variant_count ?? (Array.isArray(row.variants) ? row.variants.length : row.variants), sortValue: row => row.variant_count ?? (Array.isArray(row.variants) ? row.variants.length : Number(row.variants)) },
    { key: "offers", label: bn ? "অফার" : "Offers", numeric: true, cell: row => row.offer_count ?? row.offers ?? 0, exportValue: row => row.offer_count ?? row.offers, sortValue: row => row.offer_count ?? row.offers },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => <span className={`admin-status admin-status--${row.is_active === false ? "inactive" : "active"}`}>{row.is_active === false ? "ARCHIVED" : "ACTIVE"}</span>, exportValue: row => row.is_active === false ? "Archived" : "Active", sortValue: row => row.is_active === false ? 0 : 1 },
  ];
  return <>
    <nav className="admin-subnav" aria-label={bn ? "Catalog section" : "Catalog sections"}><Link className="admin-subnav--active" href="/admin/catalog">{bn ? "পণ্য" : "Products"}</Link><Link href="/admin/catalog/categories">{bn ? "ক্যাটাগরি" : "Categories"}</Link><Link href="/admin/catalog/variants">{bn ? "ভ্যারিয়েন্ট" : "Variants"}</Link></nav>
    <AdminDataPage<AdminProductRow> key={version} resource="products" eyebrow={bn ? "Marketplace operations" : "Marketplace operations"} title={bn ? "পণ্য" : "Products"} description={bn ? "পণ্য, category coverage, variant ও supplier-offer readiness পরিচালনা করুন।" : "Manage products, category coverage, variants and supplier-offer readiness."} searchPlaceholder={bn ? "পণ্য, model বা SKU" : "Search product, model or SKU"} columns={columns} filters={[{ key: "category", label: bn ? "ক্যাটাগরি" : "Category", options: categories.map(category => ({ value: category.slug, label: category.name })) }, { key: "active", label: bn ? "স্ট্যাটাস" : "Status", options: [{ value: "true", label: "Active" }, { value: "false", label: "Archived" }] }]} headerAction={<button className="admin-button admin-button--primary" type="button" onClick={openNew} disabled={!categories.length}>{bn ? "পণ্য যোগ করুন" : "Add product"}</button>} detailHref={row => `/admin/catalog/${row.id}`} actions={(row, reload, notify) => <><button className="admin-row-button" type="button" onClick={() => void openEdit(row)}>Edit</button><AdminArchiveAction entity="products" id={row.id} isActive={row.is_active !== false} reload={reload} notify={notify} /></>} bulkActions={[{ label: bn ? "Selected archive" : "Archive selected", kind: "danger", run: (ids, auditNote) => bulkArchiveAdminEntities("products", ids, true, auditNote).then(() => undefined) }, { label: bn ? "Selected restore" : "Restore selected", run: (ids, auditNote) => bulkArchiveAdminEntities("products", ids, false, auditNote).then(() => undefined) }]} />
    <AdminModal open={editingId !== null} onClose={() => !saving && setEditingId(null)} title={editingId === "new" ? (bn ? "পণ্য যোগ করুন" : "Add product") : (bn ? "পণ্য edit" : "Edit product")} description={bn ? "Public catalog-এ active category-এর অধীনে পণ্য দেখা যাবে।" : "Products appear publicly only under an active category."}><form className="admin-modal__form" onSubmit={submit}><label><span>{bn ? "নাম" : "Name"}</span><input minLength={2} maxLength={200} required value={fields.name} onChange={event => { set("name", event.target.value); if (editingId === "new") set("slug", slugify(event.target.value)); }} /></label><label><span>Slug</span><input pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required value={fields.slug} onChange={event => set("slug", event.target.value)} /></label><label><span>{bn ? "ক্যাটাগরি" : "Category"}</span><select required value={fields.category_id} onChange={event => set("category_id", event.target.value)}>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label><span>Model</span><input maxLength={120} value={fields.model} onChange={event => set("model", event.target.value)} /></label><label><span>{bn ? "Image URL/path" : "Image URL/path"}</span><input maxLength={500} value={fields.image} onChange={event => set("image", event.target.value)} /></label><label><span>{bn ? "Description" : "Description"}</span><textarea maxLength={10000} rows={4} value={fields.description} onChange={event => set("description", event.target.value)} /></label>{editingId !== "new" ? <label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} required rows={3} value={note} onChange={event => setNote(event.target.value)} /></label> : null}{error ? <div className="admin-alert admin-alert--error">{error}</div> : null}<div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={() => setEditingId(null)}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving || !fields.category_id || !fields.name.trim() || !slugify(fields.slug) || (editingId !== "new" && note.trim().length < 3)}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button></div></form></AdminModal>
  </>;
}
