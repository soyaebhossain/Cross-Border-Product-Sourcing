"use client";

import Link from "next/link";
import { useState } from "react";
import { AdminArchiveAction } from "../../../../components/admin-archive-action";
import { AdminDataPage, type AdminColumn } from "../../../../components/admin-data-page";
import { AdminModal } from "../../../../components/admin-modal";
import { bulkArchiveAdminEntities, createAdminCategory, updateAdminCategory, type AdminCategory } from "../../../../lib/admin-api";
import { useLocale } from "../../../../lib/locale-context";

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default function AdminCategoriesPage() {
  const [version, setVersion] = useState(0);
  const [editing, setEditing] = useState<AdminCategory | "new" | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { locale } = useLocale();
  const bn = locale === "bn";
  const openNew = () => { setEditing("new"); setName(""); setSlug(""); setNote(""); setError(""); };
  const openEdit = (row: AdminCategory) => { setEditing(row); setName(row.name); setSlug(row.slug); setNote(""); setError(""); };
  const close = () => { if (!saving) setEditing(null); };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      if (editing === "new") await createAdminCategory({ name: name.trim(), slug: slugify(slug) });
      else if (editing) await updateAdminCategory(editing.id, { name: name.trim(), slug: slugify(slug), note });
      setEditing(null); setVersion(value => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Category could not be saved."); }
    finally { setSaving(false); }
  };
  const columns: AdminColumn<AdminCategory>[] = [
    { key: "name", label: bn ? "ক্যাটাগরি" : "Category", cell: row => <div className="admin-primary-cell"><strong>{row.name}</strong><small>/{row.slug}</small></div>, exportValue: row => row.name, sortValue: row => row.name },
    { key: "products", label: bn ? "পণ্য" : "Products", numeric: true, cell: row => row.product_count, exportValue: row => row.product_count, sortValue: row => row.product_count },
    { key: "status", label: bn ? "স্ট্যাটাস" : "Status", cell: row => <span className={`admin-status admin-status--${row.is_active ? "active" : "inactive"}`}>{row.is_active ? "ACTIVE" : "ARCHIVED"}</span>, exportValue: row => row.is_active ? "Active" : "Archived", sortValue: row => row.is_active ? 1 : 0 },
  ];
  return <>
    <nav className="admin-subnav" aria-label={bn ? "Catalog section" : "Catalog sections"}><Link href="/admin/catalog">{bn ? "পণ্য" : "Products"}</Link><Link className="admin-subnav--active" href="/admin/catalog/categories">{bn ? "ক্যাটাগরি" : "Categories"}</Link><Link href="/admin/catalog/variants">{bn ? "ভ্যারিয়েন্ট" : "Variants"}</Link></nav>
    <AdminDataPage<AdminCategory> key={version} resource="categories" eyebrow={bn ? "Catalog taxonomy" : "Catalog taxonomy"} title={bn ? "ক্যাটাগরি" : "Categories"} description={bn ? "Soft archive সহ category taxonomy পরিচালনা করুন।" : "Manage catalog taxonomy with audited soft-archive controls."} searchPlaceholder={bn ? "নাম বা slug খুঁজুন" : "Search name or slug"} columns={columns} filters={[{ key: "active", label: bn ? "স্ট্যাটাস" : "Status", options: [{ value: "true", label: "Active" }, { value: "false", label: "Archived" }] }]} headerAction={<button className="admin-button admin-button--primary" type="button" onClick={openNew}>{bn ? "ক্যাটাগরি যোগ করুন" : "Add category"}</button>} detailHref={row => `/admin/catalog/categories/${row.id}`} actions={(row, reload, notify) => <><button className="admin-row-button" type="button" onClick={() => openEdit(row)}>{bn ? "Edit" : "Edit"}</button><AdminArchiveAction entity="categories" id={row.id} isActive={row.is_active} reload={reload} notify={notify} /></>} bulkActions={[{ label: bn ? "Selected archive" : "Archive selected", kind: "danger", run: (ids, auditNote) => bulkArchiveAdminEntities("categories", ids, true, auditNote).then(() => undefined) }, { label: bn ? "Selected restore" : "Restore selected", run: (ids, auditNote) => bulkArchiveAdminEntities("categories", ids, false, auditNote).then(() => undefined) }]} />
    <AdminModal open={editing !== null} onClose={close} title={editing === "new" ? (bn ? "ক্যাটাগরি যোগ করুন" : "Add category") : (bn ? "ক্যাটাগরি edit" : "Edit category")} description={bn ? "Slug lowercase letters, number ও hyphen ব্যবহার করবে।" : "Use lowercase letters, numbers and hyphens for the slug."}><form className="admin-modal__form" onSubmit={submit}><label><span>{bn ? "নাম" : "Name"}</span><input minLength={2} maxLength={120} required value={name} onChange={event => { setName(event.target.value); if (editing === "new") setSlug(slugify(event.target.value)); }} /></label><label><span>Slug</span><input pattern="[a-z0-9]+(?:-[a-z0-9]+)*" minLength={2} maxLength={120} required value={slug} onChange={event => setSlug(event.target.value)} /></label>{editing !== "new" ? <label><span>{bn ? "Mandatory audit note" : "Mandatory audit note"}</span><textarea minLength={3} required rows={3} value={note} onChange={event => setNote(event.target.value)} /></label> : null}{error ? <div className="admin-alert admin-alert--error" role="alert">{error}</div> : null}<div className="admin-modal__actions"><button className="admin-button admin-button--secondary" type="button" onClick={close}>{bn ? "বাতিল" : "Cancel"}</button><button className="admin-button admin-button--primary" disabled={saving || !name.trim() || !slugify(slug) || (editing !== "new" && note.trim().length < 3)}>{saving ? (bn ? "সংরক্ষণ হচ্ছে…" : "Saving…") : (bn ? "সংরক্ষণ" : "Save")}</button></div></form></AdminModal>
  </>;
}
